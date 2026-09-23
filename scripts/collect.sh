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

# Match the set that was actually benchmarked (see deploy.sh's degrade path), so a
# type EKS Auto Mode refused to launch is absent from the results rather than
# recorded as a MISSING failure it never had a chance to be.
if [[ -f "k8s/generated/${REGION}/available.txt" ]]; then
  PERMS=$(cat "k8s/generated/${REGION}/available.txt")
else
  PERMS=$(jq -r '.permutations[]' "$CONFIG")
fi
DIR="results/${WORKLOAD}/${LOAD}/${REGION}"
mkdir -p "$DIR"

# Record which region/AZ/instance prices produced this cell, so the raw data is
# self-describing even if specs.json later changes.
jq '{region, az, size, loadgen_type, rep, ebs, fixed,
     prices: (.perm_details | map_values(.usd_per_hour))}' \
   "$CONFIG" > "$DIR/cell.meta.json"

# Make the gap self-describing: a reader of the raw data must be able to tell
# "this type was never benchmarked here" apart from "this type performed badly".
if [[ -f "k8s/generated/${REGION}/unavailable.txt" ]]; then
  cp "k8s/generated/${REGION}/unavailable.txt" "$DIR/unavailable-types.txt"
fi

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
