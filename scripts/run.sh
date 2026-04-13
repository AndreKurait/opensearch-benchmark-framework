#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

WORKLOAD="${1:?Usage: $0 <workload> (geonames|pmc|nyc_taxis|http_logs)}"
CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: python3 scripts/generate.py"; exit 1; }

JOBS_FILE="k8s/generated/osb-jobs-${WORKLOAD}.yaml"
[[ -f "$JOBS_FILE" ]] || { echo "No jobs file for workload '$WORKLOAD'"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
COUNT=$(echo "$PERMS" | wc -l)

echo "==> Running $WORKLOAD benchmark across $COUNT permutations"

# Clean indices on all clusters
echo "==> Cleaning indices..."
for pk in $PERMS; do
  NS="os-${pk}"
  kubectl exec -n "$NS" "${pk}-master-0" -- python3 -c "
import urllib.request
try: urllib.request.urlopen(urllib.request.Request('http://localhost:9200/_all',method='DELETE'))
except: pass" 2>/dev/null &
done
wait

# Clean old results and jobs for this workload
kubectl delete cm -n default -l workload="$WORKLOAD" 2>/dev/null || true
kubectl delete jobs -n default -l workload="$WORKLOAD" 2>/dev/null || true

# Launch
kubectl apply -f "$JOBS_FILE"
echo "==> $COUNT jobs launched"

# Poll
while true; do
  cms=$(kubectl get cm -n default -l workload="$WORKLOAD" --no-headers 2>/dev/null | wc -l)
  run=$(kubectl get pods -n default -l workload="$WORKLOAD" --no-headers 2>/dev/null | grep -c Running || true)
  echo "  [$(date -u '+%H:%M')] CMs:$cms/$COUNT Running:$run"
  [[ $cms -ge $COUNT ]] && break
  sleep 120
done
echo "==> $WORKLOAD complete"
