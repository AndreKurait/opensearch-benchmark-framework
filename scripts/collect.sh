#!/usr/bin/env bash
# Collect one (workload, load level) cell for ONE region into results/.
#
# The repetition directory is the region name, because region IS the repetition
# index in this design. results/<workload>/<load>/<region>/<perm>.{csv,log,probe,meta.json}
#
# Raw CSV / log / probe output IS committed to git. The previous revision
# gitignored them, which made every published number unauditable -- nobody could
# check error rates, doc counts, or whether the workload params took effect.
set -euo pipefail
cd "$(dirname "$0")/.."

WORKLOAD="${1:?Usage: BENCH_REGION=<region> $0 <workload> <load>}"
LOAD="${2:?Usage: BENCH_REGION=<region> $0 <workload> <load>}"
REGION="${BENCH_REGION:?BENCH_REGION must be set}"

CONFIG="k8s/generated/${REGION}/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: BENCH_REGION=$REGION python3 scripts/generate.py"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
DIR="results/${WORKLOAD}/${LOAD}/${REGION}"
mkdir -p "$DIR"

# Record which region/AZ/instance prices produced this cell, so the raw data is
# self-describing even if specs.json later changes.
jq '{region, az, size, loadgen_type, rep, ebs, fixed,
     prices: (.perm_details | map_values(.usd_per_hour))}' \
   "$CONFIG" > "$DIR/cell.meta.json"

echo "==> [$REGION] collecting ${WORKLOAD}/${LOAD}"
OK=0
for pk in $PERMS; do
  CM="osb-${WORKLOAD}-${LOAD}-${pk}"
  if ! kubectl get cm "$CM" -n default >/dev/null 2>&1; then
    echo "  $pk: MISSING (no ConfigMap $CM)"
    continue
  fi
  kubectl get cm "$CM" -n default -o jsonpath='{.data.csv}'   > "$DIR/${pk}.csv"
  kubectl get cm "$CM" -n default -o jsonpath='{.data.log}'   > "$DIR/${pk}.log"
  kubectl get cm "$CM" -n default -o jsonpath='{.data.probe}' > "$DIR/${pk}.probe"
  kubectl get cm "$CM" -n default -o jsonpath='{.data.meta}'  > "$DIR/${pk}.meta.json"

  ERR=$(grep -c 'DOCCOUNT_MISMATCH' "$DIR/${pk}.probe" || true)
  WARN=$(grep -c 'PARAM_WARNING_PRESENT' "$DIR/${pk}.log" || true)
  NOTE=""
  [[ "$ERR" != "0" ]]  && NOTE="${NOTE} doc-count-mismatch"
  [[ "$WARN" != "0" ]] && NOTE="${NOTE} param-ignored"
  echo "  $pk: $(wc -l < "$DIR/${pk}.csv" | tr -d ' ') csv lines${NOTE:+ !!$NOTE}"
  OK=$((OK + 1))
done

echo "$OK" > "$DIR/.complete"
echo "==> [$REGION] collected $OK permutations into $DIR"
