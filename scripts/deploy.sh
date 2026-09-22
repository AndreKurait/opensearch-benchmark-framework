#!/usr/bin/env bash
# Deploy one 3-node OpenSearch cluster per instance type, plus the shared,
# architecture-fixed load-generator node pool.
#
# Expects KUBECONFIG to already point at this region's cluster.
set -euo pipefail
cd "$(dirname "$0")/.."

REGION="${BENCH_REGION:?BENCH_REGION must be set}"
GEN="k8s/generated/${REGION}"
CONFIG="${GEN}/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: BENCH_REGION=$REGION python3 scripts/generate.py"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
COUNT=$(echo "$PERMS" | wc -l | tr -d ' ')
LOADGEN=$(jq -r '.loadgen_type' "$CONFIG")
AZ=$(jq -r '.az' "$CONFIG")

echo "==> [$REGION/$AZ] deploying $COUNT OpenSearch clusters (load generator: $LOADGEN)"

kubectl apply -f "${GEN}/storageclass.yaml"
kubectl apply -f "${GEN}/rbac.yaml"
kubectl apply -f "${GEN}/nodepools.yaml"

helm repo add opensearch https://opensearch-project.github.io/helm-charts/ >/dev/null 2>&1 || true
helm repo update opensearch 2>&1 | tail -1

for pk in $PERMS; do
  kubectl create namespace "os-${pk}" >/dev/null 2>&1 || true
  helm upgrade --install opensearch opensearch/opensearch \
    -n "os-${pk}" --version 3.5.0 \
    -f "${GEN}/opensearch/values-${pk}.yaml" \
    --wait=false >/dev/null &
done
wait
echo "==> [$REGION] helm installs submitted; Karpenter is provisioning nodes"

# Pre-warm the load-generator pool so the first benchmark cell is not waiting on
# a cold node launch (and so a provisioning failure surfaces now, not in an hour).
kubectl apply -f - >/dev/null <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: loadgen-warm
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels: {app: loadgen-warm}
  template:
    metadata:
      labels: {app: loadgen-warm}
    spec:
      nodeSelector: {bench/role: loadgen}
      tolerations:
        - key: bench/loadgen
          operator: Equal
          value: "true"
          effect: NoSchedule
      containers:
        - name: pause
          image: public.ecr.aws/eks-distro/kubernetes/pause:3.9
          resources:
            requests: {cpu: "24", memory: "8Gi"}
EOF

echo "==> [$REGION] waiting for $((COUNT * 3)) OpenSearch pods (this provisions $((COUNT * 3)) nodes)"
TARGET=$((COUNT * 3))
DEADLINE=$(( $(date +%s) + 2400 ))
while true; do
  ready=0
  for pk in $PERMS; do
    n=$(kubectl get pods -n "os-${pk}" --no-headers 2>/dev/null \
        | grep -c '1/1 *Running' || true)
    ready=$((ready + n))
  done
  lg=$(kubectl get nodes -l bench/role=loadgen --no-headers 2>/dev/null | wc -l | tr -d ' ')
  echo "  [$REGION $(date -u '+%H:%M:%S')] opensearch pods ready: $ready/$TARGET | loadgen nodes: $lg"
  [[ "$ready" -ge "$TARGET" ]] && break
  if (( $(date +%s) > DEADLINE )); then
    # Degrade, do not die. EKS Auto Mode's managed compute catalog refuses some
    # 8th-gen types in some AZs even though EC2 itself offers them there
    # (observed: m8a.8xlarge in us-west-2, c8a.8xlarge in eu-central-1 and
    # ap-northeast-1, all reporting NoCompatibleInstanceTypes). Previously that
    # made deploy exit 1, the trap fired, and an ENTIRE repetition was destroyed
    # over one missing arm -- two of four regions lost that way. The other eight
    # permutations were healthy and would have produced valid data.
    #
    # So: drop the permutations that never came up, record them, and benchmark
    # the rest. A cell backed by fewer repetitions is still usable as long as the
    # report says so; a destroyed region is not usable at all.
    echo "  !! [$REGION] timed out waiting for pods; showing pending pods:"
    kubectl get pods -A --field-selector=status.phase=Pending --no-headers 2>/dev/null | head -20

    AVAIL=""; MISSING=""
    for pk in $PERMS; do
      n=$(kubectl get pods -n "os-${pk}" --no-headers 2>/dev/null \
          | grep -c '1/1 *Running' || true)
      if [[ "${n:-0}" -ge 3 ]]; then AVAIL="$AVAIL $pk"; else MISSING="$MISSING $pk"; fi
    done
    NAVAIL=$(echo "$AVAIL" | wc -w | tr -d ' ')

    # Below this, the surviving matrix is too thin to be worth the spend: the
    # whole point is comparing Graviton against AMD against Intel, and a handful
    # of arms cannot support that.
    MIN_PERMS="${MIN_PERMS:-6}"
    if (( NAVAIL < MIN_PERMS )); then
      echo "  !! [$REGION] only $NAVAIL/$COUNT permutations came up (<$MIN_PERMS); abandoning region."
      exit 1
    fi

    echo "  !! [$REGION] DEGRADED: continuing with $NAVAIL/$COUNT permutations."
    echo "  !! [$REGION] unavailable (EKS Auto Mode would not launch them):$MISSING"
    # Recorded so run.sh/collect.sh target the surviving set and so the report can
    # state plainly which arms this repetition is missing.
    echo "$AVAIL" | tr ' ' '\n' | grep -v '^$' > "${GEN}/available.txt"
    printf '%s\n' $MISSING > "${GEN}/unavailable.txt"
    PERMS="$AVAIL"
    COUNT="$NAVAIL"
    break
  fi
  sleep 30
done

echo "==> [$REGION] waiting for cluster health on each permutation"
for pk in $PERMS; do
  for _ in $(seq 1 60); do
    s=$(kubectl exec -n "os-${pk}" "${pk}-master-0" -- \
        curl -s --max-time 10 'http://localhost:9200/_cluster/health' 2>/dev/null \
        | jq -r '.status' 2>/dev/null || echo "")
    [[ "$s" == "green" || "$s" == "yellow" ]] && break
    sleep 10
  done
  echo "  $pk: ${s:-unknown}"
done

echo "==> [$REGION] deploy complete"
