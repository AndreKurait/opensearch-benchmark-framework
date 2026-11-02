#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# ── Full benchmark suite: provision → deploy → run all workloads → report → teardown ──
# Usage: bash scripts/run-all.sh [--skip-infra] [--skip-teardown] [--workloads "geonames pmc"]

SKIP_INFRA=false
SKIP_TEARDOWN=false
WORKLOADS=""

while (( $# )); do
  case "$1" in
    --skip-infra) SKIP_INFRA=true ;;
    --skip-teardown) SKIP_TEARDOWN=true ;;
    --workloads)
      [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || { echo "--workloads requires a space-separated list" >&2; exit 1; }
      shift; WORKLOADS="$1" ;;
    --workloads=*) WORKLOADS="${1#*=}" ;;
    --help|-h) echo 'Usage: bash scripts/run-all.sh [--skip-infra] [--skip-teardown] [--workloads "geonames pmc"]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

# Default workloads from config
if [[ -z "$WORKLOADS" ]]; then
  python3 scripts/generate.py >/dev/null
  WORKLOADS=$(jq -r '.workloads | keys[]' k8s/generated/config.json)
fi

for workload in $WORKLOADS; do
  python3 - "$workload" <<'PY'
import sys
from scripts.generate import WORKLOADS
if sys.argv[1] not in WORKLOADS:
    raise SystemExit(f"Unknown workload: {sys.argv[1]}")
PY
done

START=$(date +%s)
log() { echo ""; echo "══════════════════════════════════════════════════"; echo "  $1"; echo "══════════════════════════════════════════════════"; }

# ── 1. Infrastructure ──
if [[ "$SKIP_INFRA" == "false" ]]; then
  log "STEP 1/5: Provisioning EKS cluster"
  cd terraform
  [[ -f terraform.tfvars ]] || cp terraform.tfvars.example terraform.tfvars
  terraform init -input=false
  terraform apply -auto-approve -input=false
  eval "$(terraform output -raw kubeconfig_cmd)"
  cd ..
else
  log "STEP 1/5: Skipping infrastructure (--skip-infra)"
  aws eks update-kubeconfig --region "$(cd terraform && terraform output -raw region)" --name "$(cd terraform && terraform output -raw cluster_name)"
fi

# ── 2. Generate manifests ──
log "STEP 2/5: Generating manifests"
python3 scripts/generate.py

# ── 3. Deploy OpenSearch clusters ──
log "STEP 3/5: Deploying 18 OpenSearch clusters"
bash scripts/deploy.sh

# ── 4. Run all workloads ──
log "STEP 4/5: Running workloads: $WORKLOADS"
for wl in $WORKLOADS; do
  log "  Running $wl..."
  bash scripts/run.sh "$wl"
  bash scripts/collect.sh "$wl"
  echo "  ✅ $wl complete"
done

# ── 5. Final report ──
log "STEP 5/5: Generating final report"
python3 scripts/report.py
echo ""
head -30 results/REPORT.md
echo "..."
echo ""
echo "Full report: results/REPORT.md"

# ── Teardown ──
if [[ "$SKIP_TEARDOWN" == "false" ]]; then
  log "TEARDOWN: Removing all resources"
  bash scripts/teardown.sh
  cd terraform && terraform destroy -auto-approve -input=false
else
  echo ""
  echo "Skipping teardown (--skip-teardown). Remember to run:"
  echo "  bash scripts/teardown.sh && cd terraform && terraform destroy -auto-approve"
fi

ELAPSED=$(( $(date +%s) - START ))
echo ""
echo "════════════════════════════════════════════════════"
echo "  DONE in $((ELAPSED / 60))m $((ELAPSED % 60))s"
echo "════════════════════════════════════════════════════"
