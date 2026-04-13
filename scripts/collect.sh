#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

WORKLOAD="${1:?Usage: $0 <workload> (geonames|pmc|nyc_taxis|http_logs)}"
CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: python3 scripts/generate.py"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
DIR="results/${WORKLOAD}"
mkdir -p "$DIR"

echo "==> Collecting $WORKLOAD results"
for pk in $PERMS; do
  CM="osb-${WORKLOAD}-${pk}"
  kubectl get cm "$CM" -n default -o jsonpath='{.data.csv}' > "$DIR/${pk}.csv" 2>/dev/null || echo "MISSING" > "$DIR/${pk}.csv"
  kubectl get cm "$CM" -n default -o jsonpath='{.data.log}' > "$DIR/${pk}.log" 2>/dev/null || true
  lines=$(wc -l < "$DIR/${pk}.csv")
  echo "  $pk: $lines lines"
done

echo "==> Generating report..."
python3 scripts/report.py
echo "==> Done. See results/REPORT.md"
