#!/usr/bin/env bash
# Run one workload across every load level and repetition.
#
# Indices are dropped between every repetition, so a cell's repetitions are not
# silently measuring a progressively warmer cache. Each (load, rep) cell is
# checkpointed, so an interrupted run resumes instead of restarting.
set -euo pipefail
cd "$(dirname "$0")/.."

WORKLOAD="${1:?Usage: $0 <workload>}"
CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: python3 scripts/generate.py"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
COUNT=$(echo "$PERMS" | wc -l | tr -d ' ')
REPS=$(jq -r '.reps' "$CONFIG")
LOADS=$(jq -r '.load_levels | keys_unsorted[]' "$CONFIG")
NLOADS=$(echo "$LOADS" | wc -l | tr -d ' ')

echo "==> Workload '$WORKLOAD': $COUNT permutations x $NLOADS load levels x $REPS reps"

drop_indices() {
  for pk in $PERMS; do
    kubectl exec -n "os-${pk}" "${pk}-master-0" -- \
      curl -s -XDELETE 'http://localhost:9200/_all' >/dev/null 2>&1 || true
  done
  # Give Lucene time to release segments before the next run starts.
  sleep 20
}

for LOAD in $LOADS; do
  for REP in $(seq 1 "$REPS"); do
    JOBS_FILE="k8s/generated/jobs/${WORKLOAD}-${LOAD}-r${REP}.yaml"
    [[ -f "$JOBS_FILE" ]] || { echo "  missing $JOBS_FILE, skipping"; continue; }

    if [[ -f "results/${WORKLOAD}/${LOAD}/r${REP}/.complete" ]]; then
      echo "==> [$LOAD rep $REP] already complete, skipping"
      continue
    fi

    echo "==> [$LOAD rep $REP] dropping indices on all $COUNT clusters"
    drop_indices

    kubectl delete jobs -n default -l "workload=$WORKLOAD,load=$LOAD,rep=$REP" \
      --ignore-not-found >/dev/null 2>&1 || true
    kubectl delete cm -n default -l "workload=$WORKLOAD,load=$LOAD,rep=$REP" \
      --ignore-not-found >/dev/null 2>&1 || true

    echo "==> [$LOAD rep $REP] launching $COUNT jobs"
    kubectl apply -f "$JOBS_FILE" >/dev/null

    DEADLINE=$(( $(date +%s) + 10800 ))   # 3h ceiling per cell
    while true; do
      cms=$(kubectl get cm -n default -l "workload=$WORKLOAD,load=$LOAD,rep=$REP" \
            --no-headers 2>/dev/null | wc -l | tr -d ' ')
      failed=$(kubectl get jobs -n default -l "workload=$WORKLOAD,load=$LOAD,rep=$REP" \
            -o jsonpath='{range .items[*]}{.status.failed}{"\n"}{end}' 2>/dev/null \
            | grep -c '^[1-9]' || true)
      running=$(kubectl get pods -n default -l "workload=$WORKLOAD,load=$LOAD,rep=$REP" \
            --no-headers 2>/dev/null | grep -c Running || true)
      echo "    [$(date -u '+%H:%M:%S')] results:$cms/$COUNT running:$running failed:$failed"
      [[ "$cms" -ge "$COUNT" ]] && break
      if (( $(date +%s) > DEADLINE )); then
        echo "    !! deadline exceeded; collecting whatever landed"
        break
      fi
      sleep 60
    done

    bash scripts/collect.sh "$WORKLOAD" "$LOAD" "$REP"
  done
done

echo "==> Generating report"
python3 scripts/report.py
echo "==> Done: results/REPORT.md"
