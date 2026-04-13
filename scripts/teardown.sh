#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Nothing to tear down"; exit 0; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")

echo "==> Deleting OSB jobs..."
kubectl delete jobs -n default -l bench=osb 2>/dev/null || true

echo "==> Uninstalling OpenSearch..."
for pk in $PERMS; do
  helm uninstall opensearch -n "os-${pk}" 2>/dev/null &
done
wait

echo "==> Deleting namespaces..."
for pk in $PERMS; do
  kubectl delete ns "os-${pk}" --wait=false 2>/dev/null &
done
wait

kubectl delete -f k8s/generated/nodepools.yaml 2>/dev/null || true
kubectl delete -f k8s/generated/storageclasses.yaml 2>/dev/null || true
kubectl delete -f k8s/generated/rbac.yaml 2>/dev/null || true

echo "==> Teardown complete. Run: cd terraform && terraform destroy -auto-approve"
