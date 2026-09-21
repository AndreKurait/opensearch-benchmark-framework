#!/usr/bin/env bash
# Collect one (workload, load level, rep) cell into results/ as raw artifacts.
#
# Raw CSV / log / probe output IS committed to git. The previous revision
# gitignored them, which made every published number unauditable -- nobody could
# check error rates, doc counts, or whether the workload params took effect.
set -euo pipefail
cd "$(dirname "$0")/.."

WORKLOAD="${1:?Usage: $0 <workload> <load> <rep>}"
LOAD="${2:?Usage: $0 <workload> <load> <rep>}"
REP="${3:?Usage: $0 <workload> <load> <rep>}"

CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: python3 scripts/generate.py"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
DIR="results/${WORKLOAD}/${LOAD}/r${REP}"
mkdir -p "$DIR"

echo "==> Collecting ${WORKLOAD}/${LOAD}/r${REP}"
OK=0
for pk in $PERMS; do
  CM="osb-${WORKLOAD}-${LOAD}-r${REP}-${pk}"
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
echo "==> Collected $OK permutations into $DIR"
