#!/usr/bin/env bash
# Run one workload across every load level, for ONE region.
#
# The repetition index is the region: this script performs a single pass over the
# matrix, and the caller (run-multiregion.sh) runs seven of these concurrently,
# one per region. Repetitions therefore land on independent node sets in
# independent capacity pools, which is what makes the interquartile ranges in the
# report reflect real placement variance rather than just run-to-run jitter.
#
# Indices are dropped between load levels so a later level is not silently
# measuring a progressively warmer cache. Each cell is checkpointed, so an
# interrupted run resumes instead of restarting.
#
# Expects KUBECONFIG to already point at this region's cluster.
set -euo pipefail
cd "$(dirname "$0")/.."

WORKLOAD="${1:?Usage: BENCH_REGION=<region> $0 <workload>}"
REGION="${BENCH_REGION:?BENCH_REGION must be set}"

GEN="k8s/generated/${REGION}"
CONFIG="${GEN}/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: BENCH_REGION=$REGION python3 scripts/generate.py"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
COUNT=$(echo "$PERMS" | wc -l | tr -d ' ')
LOADS=$(jq -r '.load_levels | keys_unsorted[]' "$CONFIG")
NLOADS=$(echo "$LOADS" | wc -l | tr -d ' ')
AZ=$(jq -r '.az' "$CONFIG")

echo "==> [$REGION/$AZ] '$WORKLOAD': $COUNT permutations x $NLOADS load levels (rep=$REGION)"

drop_indices() {
  for pk in $PERMS; do
    kubectl exec -n "os-${pk}" "${pk}-master-0" -- \
      curl -s -XDELETE 'http://localhost:9200/_all' >/dev/null 2>&1 || true
  done
  # Give Lucene time to release segments before the next run starts.
  sleep 20
}

for LOAD in $LOADS; do
  JOBS_FILE="${GEN}/jobs/${WORKLOAD}-${LOAD}.yaml"
  [[ -f "$JOBS_FILE" ]] || { echo "  missing $JOBS_FILE, skipping"; continue; }

  if [[ -f "results/${WORKLOAD}/${LOAD}/${REGION}/.complete" ]]; then
    echo "==> [$REGION $LOAD] already complete, skipping"
    continue
  fi

  echo "==> [$REGION $LOAD] dropping indices on all $COUNT clusters"
  drop_indices

  kubectl delete jobs -n default -l "workload=$WORKLOAD,load=$LOAD" \
    --ignore-not-found >/dev/null 2>&1 || true
  kubectl delete cm -n default -l "workload=$WORKLOAD,load=$LOAD" \
    --ignore-not-found >/dev/null 2>&1 || true

  echo "==> [$REGION $LOAD] launching $COUNT jobs"
  kubectl apply -f "$JOBS_FILE" >/dev/null

  DEADLINE=$(( $(date +%s) + 10800 ))   # 3h ceiling per cell
  while true; do
    # Default every counter to 0 if kubectl fails. An empty string on the left of
    # -ge is a fatal "integer expression expected" under set -e, which would kill
    # a healthy 3h run over one transient API-server blip.
    cms=$(kubectl get cm -n default -l "workload=$WORKLOAD,load=$LOAD" \
          --no-headers 2>/dev/null | wc -l | tr -d ' ')
    cms=${cms:-0}
    failed=$(kubectl get jobs -n default -l "workload=$WORKLOAD,load=$LOAD" \
          -o jsonpath='{range .items[*]}{.status.failed}{"\n"}{end}' 2>/dev/null \
          | grep -c '^[1-9]' || true)
    running=$(kubectl get pods -n default -l "workload=$WORKLOAD,load=$LOAD" \
          --no-headers 2>/dev/null | grep -c Running || true)
    failed=${failed:-0}; running=${running:-0}
    echo "    [$REGION $(date -u '+%H:%M:%S')] results:$cms/$COUNT running:$running failed:$failed"
    [[ "$cms" -ge "$COUNT" ]] && break
    if (( $(date +%s) > DEADLINE )); then
      echo "    !! [$REGION] deadline exceeded; collecting whatever landed"
      break
    fi
    sleep 60
  done

  bash scripts/collect.sh "$WORKLOAD" "$LOAD"
done

echo "==> [$REGION] all load levels done"
