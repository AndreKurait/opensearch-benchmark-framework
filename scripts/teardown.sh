#!/usr/bin/env bash
# Remove everything this framework created inside the cluster.
# Scoped strictly to bench-owned namespaces / labelled objects -- it never
# touches resources it did not create. The EKS cluster and VPC are removed
# separately via `terraform destroy`.
set -euo pipefail
cd "$(dirname "$0")/.."

# Scoped to one region's generated manifests. Deleting by the wrong region's
# nodepool list would leave nodes running and billing, so the region is required
# rather than defaulted.
REGION="${BENCH_REGION:?BENCH_REGION must be set (which region to tear down)}"
GEN="k8s/generated/${REGION}"
CONFIG="${GEN}/config.json"
[[ -f "$CONFIG" ]] || { echo "[$REGION] Nothing to tear down"; exit 0; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")

echo "==> Deleting OSB jobs"
kubectl delete jobs -n default -l bench=osb --ignore-not-found >/dev/null 2>&1 || true

echo "==> Deleting loadgen warm-up deployment"
kubectl delete deployment loadgen-warm -n default --ignore-not-found >/dev/null 2>&1 || true

echo "==> Uninstalling OpenSearch releases"
for pk in $PERMS; do
  helm uninstall opensearch -n "os-${pk}" >/dev/null 2>&1 || true
done

echo "==> Deleting namespaces (this releases the EBS volumes)"
for pk in $PERMS; do
  kubectl delete ns "os-${pk}" --wait=false --ignore-not-found >/dev/null 2>&1 || true
done

echo "==> Waiting for PVCs to be released"
for _ in $(seq 1 30); do
  left=$(kubectl get pvc -A --no-headers 2>/dev/null | grep -c '^os-' || true)
  [[ "$left" == "0" ]] && break
  echo "  $left PVC(s) remaining"
  sleep 10
done

kubectl delete -f "${GEN}"/nodepools.yaml --ignore-not-found >/dev/null 2>&1 || true
kubectl delete -f "${GEN}"/storageclass.yaml --ignore-not-found >/dev/null 2>&1 || true
kubectl delete -f "${GEN}"/rbac.yaml --ignore-not-found >/dev/null 2>&1 || true

# The EBS CSI driver creates the StatefulSet volumes, so terraform has no record
# of them and `terraform destroy` leaves them behind. The first multi-region run
# orphaned ~21 TiB of gp3 this way (~$2.40/hr) which nothing would ever have
# reclaimed. Sweep them explicitly, scoped by the cluster ownership tag so this
# can only ever touch volumes this run created.
CLUSTER="osb-bench-${REGION}"
echo "==> Sweeping orphaned EBS volumes tagged to ${CLUSTER}"
orphans=$(aws ec2 describe-volumes --region "$REGION" \
  --filters "Name=tag-key,Values=kubernetes.io/cluster/${CLUSTER}" "Name=status,Values=available" \
  --query 'Volumes[].VolumeId' --output text 2>/dev/null || true)
if [[ -n "${orphans// /}" ]]; then
  for vol in $orphans; do
    echo "  deleting $vol"
    aws ec2 delete-volume --region "$REGION" --volume-id "$vol" >/dev/null 2>&1 \
      || echo "  !! could not delete $vol -- check manually"
  done
else
  echo "  none found"
fi

echo "==> [$REGION] Benchmark resources removed."
echo "    Results are preserved in results/ (committed to git)."
echo "    To remove the EKS cluster and VPC:  cd terraform && terraform destroy"
