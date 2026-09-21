#!/usr/bin/env bash
# Full suite: fetch specs -> provision -> deploy -> run -> report -> teardown.
#
# Usage:
#   bash scripts/run-all.sh                      # prompts with a cost estimate first
#   bash scripts/run-all.sh --yes                # non-interactive
#   bash scripts/run-all.sh --skip-infra         # reuse an existing cluster
#   bash scripts/run-all.sh --skip-teardown      # leave the cluster running (COSTS MONEY)
#
# Matrix size is controlled by environment variables consumed by generate.py:
#   BENCH_SIZE=8xlarge BENCH_REPS=5 BENCH_LOADS=load-500,load-2000,saturate \
#   BENCH_WORKLOADS=geonames bash scripts/run-all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

SKIP_INFRA=false
SKIP_TEARDOWN=false
ASSUME_YES=false
REGION="${AWS_REGION:-us-east-1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-infra) SKIP_INFRA=true; shift ;;
    --skip-teardown) SKIP_TEARDOWN=true; shift ;;
    --yes|-y) ASSUME_YES=true; shift ;;
    --region) REGION="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

START=$(date +%s)
log() { echo; echo "=============================================="; echo "  $1"; echo "=============================================="; }

# ── 1. Specs (prices + core counts) straight from the AWS APIs ──
log "STEP 1/6: Fetching instance specs and on-demand pricing"
python3 scripts/fetch_specs.py --region "$REGION"

# ── 2. Manifests + cost gate ──
log "STEP 2/6: Generating manifests"
python3 scripts/generate.py

log "COST ESTIMATE"
python3 scripts/estimate.py

if [[ "$ASSUME_YES" != "true" ]]; then
  echo
  read -r -p "Proceed and incur this cost? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || { echo "Aborted."; exit 1; }
fi

# ── 3. Infrastructure ──
if [[ "$SKIP_INFRA" == "false" ]]; then
  log "STEP 3/6: Provisioning EKS cluster"
  pushd terraform >/dev/null
  [[ -f terraform.tfvars ]] || cp terraform.tfvars.example terraform.tfvars
  terraform init -input=false
  terraform apply -auto-approve -input=false
  eval "$(terraform output -raw kubeconfig_cmd)"
  popd >/dev/null
else
  log "STEP 3/6: Reusing existing cluster (--skip-infra)"
  pushd terraform >/dev/null
  eval "$(terraform output -raw kubeconfig_cmd)"
  popd >/dev/null
fi

# ── 4. Deploy ──
log "STEP 4/6: Deploying OpenSearch clusters"
bash scripts/deploy.sh

# ── 5. Run ──
WORKLOADS=$(jq -r '.workloads | keys[]' k8s/generated/config.json)
log "STEP 5/6: Running workloads: $(echo "$WORKLOADS" | tr '\n' ' ')"
for wl in $WORKLOADS; do
  bash scripts/run.sh "$wl"
done

# ── 6. Report ──
log "STEP 6/6: Report"
python3 scripts/report.py
head -40 results/REPORT.md
echo "..."
echo "Full report: results/REPORT.md"

if [[ "$SKIP_TEARDOWN" == "false" ]]; then
  log "TEARDOWN"
  bash scripts/teardown.sh
  pushd terraform >/dev/null
  terraform destroy -auto-approve -input=false
  popd >/dev/null
else
  echo
  echo "Skipping teardown (--skip-teardown). THE CLUSTER IS STILL BILLING."
  echo "  bash scripts/teardown.sh && cd terraform && terraform destroy -auto-approve"
fi

ELAPSED=$(( $(date +%s) - START ))
echo
echo "DONE in $((ELAPSED / 3600))h $(((ELAPSED % 3600) / 60))m"
