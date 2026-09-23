#!/usr/bin/env bash
# Full suite across all benchmark regions CONCURRENTLY.
#
# Each region is one independent repetition running the full 9-instance-type
# matrix (see docs/METHODOLOGY.md rule 4a). Regions run in parallel, so wall
# clock is set by a single region's pass while cost is the sum across regions.
#
# Usage:
#   bash scripts/run-all.sh                      # prompts with a cost estimate first
#   bash scripts/run-all.sh --yes                # non-interactive
#   bash scripts/run-all.sh --regions us-east-1,us-east-2
#   bash scripts/run-all.sh --skip-teardown      # leave clusters running (COSTS MONEY)
#
# Each region gets its OWN terraform state directory under .runs/<region>/ so
# concurrent regions cannot corrupt a shared state file, and its own kubeconfig
# so concurrent kubectl calls cannot race on the current context.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

SKIP_TEARDOWN=false
ASSUME_YES=false
REGIONS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-teardown) SKIP_TEARDOWN=true; shift ;;
    --yes|-y) ASSUME_YES=true; shift ;;
    --regions) REGIONS="${2//,/ }"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

START=$(date +%s)
log() { echo; echo "=============================================="; echo "  $1"; echo "=============================================="; }

log "STEP 1/6: Fetching instance specs, pricing and vCPU quotas"
python3 scripts/fetch_specs.py

# Only regions offering all nine instance types in one shared AZ may serve as a
# repetition. A region missing an arm would turn the comparison into a
# cross-region one, which is not a CPU comparison at all.
if [[ -z "$REGIONS" ]]; then
  REGIONS=$(python3 -c "import json;print(' '.join(r for r,v in json.load(open('specs.json'))['regions'].items() if v['usable_as_repetition']))")
fi
[[ -n "$REGIONS" ]] || { echo "No usable benchmark regions found."; exit 1; }
N_REGIONS=$(echo "$REGIONS" | wc -w | tr -d ' ')
echo
echo "Regions (one repetition each, run concurrently): $REGIONS"

log "STEP 2/6: Generating manifests per region"
for rg in $REGIONS; do
  BENCH_REGION="$rg" python3 scripts/generate.py
done
python3 scripts/validate_manifests.py

log "COST ESTIMATE"
python3 scripts/estimate.py

if [[ "$ASSUME_YES" != "true" ]]; then
  echo
  echo "This provisions an EKS cluster and ~30 nodes in EACH of the regions above."
  read -r -p "Proceed and incur this cost? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || { echo "Aborted."; exit 1; }
fi

# Share the provider plugin cache so N concurrent inits do not each download
# their own copy of the AWS provider.
mkdir -p logs

# Resolve providers and modules ONCE, serially, in a scratch directory, then copy
# the resolved .terraform/ tree and its lock file into each region. Two problems
# this avoids:
#   1. N regions initialising against an empty registry cache each fetch every
#      provider themselves, saturating the link into connection resets and DNS
#      failures.
#   2. TF_PLUGIN_CACHE_DIR is not concurrency-safe and records checksums that do
#      not match a per-region lock file, giving "Required plugins are not
#      installed" on a directory that just initialised successfully.
# Copying a single consistent (providers + lock) pair sidesteps both: no region
# ever contacts the registry.
log "STEP 2b/6: Resolving Terraform providers once (serial)"
WARM="$ROOT/.runs/_warm"
rm -rf "$WARM"
mkdir -p "$WARM"
cp "$ROOT"/terraform/*.tf "$WARM/"
cat > "$WARM/terraform.tfvars" <<EOF
region       = "us-east-1"
cluster_name = "osb-bench-warm"
bench_az     = "us-east-1a"
EOF
( cd "$WARM" && terraform init -input=false ) || {
  echo "Provider resolution failed -- aborting before provisioning anything."
  exit 1
}
[[ -d "$WARM/.terraform" && -f "$WARM/.terraform.lock.hcl" ]] || {
  echo "Warm init produced no .terraform/ or lock file -- aborting."
  exit 1
}
echo "Providers resolved; regions will reuse them without contacting the registry."

# ── destroy_with_retry: terraform destroy that survives a transient outage ───
# The first multi-region attempt lost four clusters for 8.5h because destroy ran
# once, hit a DNS failure while the host's network flapped, and gave up. Destroy
# is idempotent, so retrying it is free; NOT retrying it costs money per hour.
destroy_with_retry() {
  local rg="$1" dir="$2" attempt
  for attempt in 1 2 3 4 5 6; do
    ( cd "$dir" && AWS_REGION="$rg" terraform destroy -auto-approve -input=false ) && {
      echo "[$rg] destroy complete (attempt $attempt)"
      return 0
    }
    echo "[$rg] destroy attempt $attempt failed; retrying in $((attempt * 60))s"
    sleep $((attempt * 60))
  done
  echo "[$rg] !! DESTROY FAILED 6x -- RESOURCES MAY STILL BE BILLING."
  echo "[$rg] !! run: cd $dir && terraform destroy -auto-approve"
  return 1
}

# ── run_region: one full repetition, start to finish, in one region ──────────
# Runs in a subshell per region. A failure costs ONE repetition, not the whole
# experiment. Teardown is trapped rather than left to the happy path: an
# abandoned 30-node cluster is by far the most expensive failure mode here.
run_region() {
  local rg="$1"
  local dir="$ROOT/.runs/$rg"
  local cluster="osb-bench-$rg"
  local az
  az=$(python3 -c "import json;print(json.load(open('$ROOT/k8s/generated/$rg/config.json'))['az'])")

  mkdir -p "$dir"
  cp "$ROOT"/terraform/*.tf "$dir/"
  # Reuse the providers/modules resolved serially in $WARM. Copying the lock file
  # together with the .terraform/ tree it was generated against keeps their
  # checksums consistent, so init is a no-op offline check.
  # rm first: cp -R onto an existing directory nests instead of replacing.
  rm -rf "$dir/.terraform"
  cp -R "$WARM/.terraform" "$dir/.terraform"
  cp "$WARM/.terraform.lock.hcl" "$dir/.terraform.lock.hcl"
  cat > "$dir/terraform.tfvars" <<EOF
region       = "$rg"
cluster_name = "$cluster"
bench_az     = "$az"
EOF

  export KUBECONFIG="$dir/kubeconfig"
  export BENCH_REGION="$rg"
  export AWS_REGION="$rg"

  echo "[$rg] provisioning in $az (cluster $cluster)"

  # Install the teardown trap BEFORE apply, not after. A failed or interrupted
  # apply still creates real resources: us-east-1 died on VpcLimitExceeded
  # mid-apply and left 26 orphans behind precisely because the trap was armed
  # only on the success path.
  # shellcheck disable=SC2064
  trap "echo '[$rg] tearing down'; cd '$ROOT'; BENCH_REGION='$rg' KUBECONFIG='$dir/kubeconfig' bash '$ROOT/scripts/teardown.sh' || true; destroy_with_retry '$rg' '$dir' || true" EXIT

  cd "$dir"
  # Retry init: the cache is warm, but a registry hiccup here costs the whole
  # repetition, and retrying is free compared to losing one of seven reps.
  for attempt in 1 2 3; do
    terraform init -input=false && break
    echo "[$rg] terraform init failed (attempt $attempt/3); retrying in $((attempt * 20))s"
    sleep $((attempt * 20))
    [[ "$attempt" == "3" ]] && { echo "[$rg] init failed 3x, giving up"; return 1; }
  done
  terraform apply -auto-approve -input=false

  aws eks update-kubeconfig --region "$rg" --name "$cluster"
  cd "$ROOT"

  bash scripts/deploy.sh
  for wl in $(jq -r '.workloads | keys[]' "k8s/generated/$rg/config.json"); do
    bash scripts/run.sh "$wl"
    for lk in $(jq -r '.load_levels | keys[]' "k8s/generated/$rg/config.json"); do
      bash scripts/collect.sh "$wl" "$lk" || true
    done
  done

  if [[ "$SKIP_TEARDOWN" == "true" ]]; then
    trap - EXIT
    echo "[$rg] Skipping teardown (--skip-teardown). THIS REGION IS STILL BILLING."
  fi
}

log "STEP 3/6-5/6: Provisioning, deploying and running $N_REGIONS regions concurrently"
echo "Per-region logs: logs/<region>.log"
declare -A PIDS=()
for rg in $REGIONS; do
  ( run_region "$rg" ) > "logs/$rg.log" 2>&1 &
  PIDS[$rg]=$!
  echo "  [$rg] started (pid ${PIDS[$rg]})"
done

FAILED=()
for rg in $REGIONS; do
  if wait "${PIDS[$rg]}"; then
    echo "  [$rg] COMPLETE"
  else
    echo "  [$rg] FAILED -- see logs/$rg.log"
    FAILED+=("$rg")
  fi
done

if (( ${#FAILED[@]} )); then
  echo
  echo "WARNING: ${#FAILED[@]} of $N_REGIONS repetitions failed: ${FAILED[*]}"
  echo "The report below uses only the repetitions that succeeded, so its error"
  echo "bars are correspondingly thinner. Check logs/ before quoting any number."
fi

log "STEP 6/6: Report"
python3 scripts/report.py || echo "report.py failed -- raw results are still in results/"
[[ -f results/REPORT.md ]] && head -40 results/REPORT.md
echo "..."
echo "Full report: results/REPORT.md"

# Teardown already ran inside each region's trap. Verify nothing survived it:
# a leaked cluster bills ~$60/hr per region until someone notices.
log "VERIFYING TEARDOWN"
for rg in $REGIONS; do
  left=0
  if [[ -d "$ROOT/.runs/$rg" ]]; then
    left=$( (cd "$ROOT/.runs/$rg" && terraform state list 2>/dev/null | wc -l) | tr -d ' ' )
  fi
  if [[ "${left:-0}" != "0" ]]; then
    echo "  [$rg] WARNING: $left resources still in state -- STILL BILLING."
    echo "          cd .runs/$rg && terraform destroy -auto-approve"
  else
    echo "  [$rg] clean"
  fi
done

ELAPSED=$(( $(date +%s) - START ))
echo
echo "DONE in $((ELAPSED / 3600))h $(((ELAPSED % 3600) / 60))m"
(( ${#FAILED[@]} == 0 )) || exit 1
