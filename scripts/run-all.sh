#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# ── Full benchmark suite: provision → deploy → run all workloads → report → teardown ──
# Usage: bash scripts/run-all.sh [--skip-infra] [--skip-teardown] [--workloads "geonames pmc"]

SKIP_INFRA=false
SKIP_TEARDOWN=false
WORKLOADS=""

for arg in "$@"; do
  case $arg in
    --skip-infra) SKIP_INFRA=true ;;
    --skip-teardown) SKIP_TEARDOWN=true ;;
    --workloads) shift; WORKLOADS="$1" ;;
    --workloads=*) WORKLOADS="${arg#*=}" ;;
  esac
  shift 2>/dev/null || true
done

# Default workloads from config
if [[ -z "$WORKLOADS" ]]; then
  python3 scripts/generate.py >/dev/null
  WORKLOADS=$(jq -r '.workloads | keys[]' k8s/generated/config.json)
fi

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
cat results/REPORT.md | head -30
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
