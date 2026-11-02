#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

WORKLOAD="${1:?Usage: $0 <workload> (geonames|pmc|nyc_taxis|http_logs)}"
TIMEOUT_SECONDS="${BENCHMARK_TIMEOUT_SECONDS:-7500}"
[[ "$TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]] || { echo "BENCHMARK_TIMEOUT_SECONDS must be a positive integer" >&2; exit 1; }
CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: python3 scripts/generate.py"; exit 1; }

JOBS_FILE="k8s/generated/osb-jobs-${WORKLOAD}.yaml"
[[ -f "$JOBS_FILE" ]] || { echo "No jobs file for workload '$WORKLOAD'"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
COUNT=$(echo "$PERMS" | wc -l)

echo "==> Running $WORKLOAD benchmark across $COUNT permutations"

# Stop prior writers before clearing their indices. Foreground deletion waits for pods.
kubectl delete jobs -n default -l "bench=osb,workload=$WORKLOAD" --ignore-not-found \
  --cascade=foreground --wait=true --timeout=120s

# Clean indices on all clusters
echo "==> Cleaning indices..."
cleanup_pids=()
cleanup_names=()
for pk in $PERMS; do
  NS="os-${pk}"
  kubectl --request-timeout=90s exec -n "$NS" "${pk}-master-0" -- python3 -c "
import json, urllib.request
with urllib.request.urlopen(urllib.request.Request('http://localhost:9200/_all', method='DELETE'), timeout=60) as response:
    if not json.load(response).get('acknowledged'):
        raise RuntimeError('Index deletion was not acknowledged')" &
  cleanup_pids+=("$!")
  cleanup_names+=("$pk")
done
cleanup_failed=false
for index in "${!cleanup_pids[@]}"; do
  if ! wait "${cleanup_pids[$index]}"; then
    echo "Index cleanup failed for ${cleanup_names[$index]}; no new benchmark jobs will be launched." >&2
    cleanup_failed=true
  fi
done
[[ "$cleanup_failed" == "false" ]] || exit 1

# Preserve old result ConfigMaps if cleanup fails; clear them only before a new run.
kubectl delete cm -n default -l "bench=osb,workload=$WORKLOAD" --ignore-not-found

# Launch
kubectl apply -f "$JOBS_FILE"
echo "==> $COUNT jobs launched"

# Poll
START=$SECONDS
while (( SECONDS - START < TIMEOUT_SECONDS )); do
  jobs=$(kubectl get jobs -n default -l "bench=osb,workload=$WORKLOAD" -o json --request-timeout=30s)
  failed=$(jq '[.items[] | select(any(.status.conditions[]?; .type == "Failed" and .status == "True"))] | length' <<<"$jobs")
  completed=$(jq '[.items[] | select(any(.status.conditions[]?; .type == "Complete" and .status == "True"))] | length' <<<"$jobs")
  if (( failed > 0 )); then
    echo "Benchmark failed: $failed Job(s). Inspect Job logs before collecting results." >&2
    exit 1
  fi
  echo "  [$(date -u '+%H:%M')] Completed:$completed/$COUNT"
  if (( completed == COUNT )); then
    echo "==> $WORKLOAD complete"
    exit 0
  fi
  sleep 30
done
echo "Timed out waiting for $WORKLOAD after ${TIMEOUT_SECONDS}s. Resources remain for inspection." >&2
exit 1
