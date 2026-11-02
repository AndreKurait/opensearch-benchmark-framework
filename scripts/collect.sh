#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

WORKLOAD="${1:?Usage: $0 <workload> (geonames|pmc|nyc_taxis|http_logs)}"
CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: python3 scripts/generate.py"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
DIR="results/${WORKLOAD}"
mkdir -p results
staging=$(mktemp -d "results/.collect.XXXXXX")
published=false
cleanup_staging() {
  if [[ -d "$staging/previous" && "$published" != "true" ]]; then
    echo "Original results retained at $staging/previous; restore them before retrying." >&2
  else
    rm -rf -- "$staging"
  fi
}
trap cleanup_staging EXIT
mkdir "$staging/next"
# Preserve notes and other files alongside the managed CSVs/logs.
if [[ -d "$DIR" ]]; then
  cp -a "$DIR/." "$staging/next/"
fi

echo "==> Collecting $WORKLOAD results"
for pk in $PERMS; do
  CM="osb-${WORKLOAD//_/-}-${pk}"
  status=$(kubectl get cm "$CM" -n default -o jsonpath='{.data.exit_code}')
  [[ "$status" == "0" ]] || { echo "$CM did not record a successful benchmark; refusing to overwrite results" >&2; exit 1; }
  kubectl get cm "$CM" -n default -o jsonpath='{.data.csv}' > "$staging/next/${pk}.csv"
  kubectl get cm "$CM" -n default -o jsonpath='{.data.log}' > "$staging/next/${pk}.log" 2>/dev/null || true
  lines=$(wc -l < "$staging/next/${pk}.csv")
  echo "  $pk: $lines lines"
done

# Publish a complete directory, never a partially collected set of permutations.
if [[ -d "$DIR" ]]; then
  mv -- "$DIR" "$staging/previous"
fi
if ! mv -- "$staging/next" "$DIR"; then
  if [[ -d "$staging/previous" ]]; then
    mv -- "$staging/previous" "$DIR" || true
  fi
  exit 1
fi
published=true

echo "==> Generating report..."
python3 scripts/report.py
echo "==> Done. See results/REPORT.md"
