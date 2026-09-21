#!/usr/bin/env bash
# Remove everything this framework created inside the cluster.
# Scoped strictly to bench-owned namespaces / labelled objects -- it never
# touches resources it did not create. The EKS cluster and VPC are removed
# separately via `terraform destroy`.
set -euo pipefail
cd "$(dirname "$0")/.."

CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Nothing to tear down"; exit 0; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")

echo "==> Deleting OSB jobs"
kubectl delete jobs -n default -l bench=osb --ignore-not-found >/dev/null 2>&1 || true

echo "==> Deleting loadgen warm-up deployment"
kubectl delete deployment loadgen-warm -n default --ignore-not-found >/dev/null 2>&1 || true

echo "==> Uninstalling OpenSearch releases"
for pk in $PERMS; do
  helm uninstall opensearch -n "os-${pk}" >/dev/null 2>&1 || true
done

echo "==> Deleting namespaces (this releases the EBS volumes)"
for pk in $PERMS; do
  kubectl delete ns "os-${pk}" --wait=false --ignore-not-found >/dev/null 2>&1 || true
done

echo "==> Waiting for PVCs to be released"
for _ in $(seq 1 30); do
  left=$(kubectl get pvc -A --no-headers 2>/dev/null | grep -c '^os-' || true)
  [[ "$left" == "0" ]] && break
  echo "  $left PVC(s) remaining"
  sleep 10
done

kubectl delete -f k8s/generated/nodepools.yaml --ignore-not-found >/dev/null 2>&1 || true
kubectl delete -f k8s/generated/storageclass.yaml --ignore-not-found >/dev/null 2>&1 || true
kubectl delete -f k8s/generated/rbac.yaml --ignore-not-found >/dev/null 2>&1 || true

echo "==> Benchmark resources removed."
echo "    Results are preserved in results/ (committed to git)."
echo "    To remove the EKS cluster and VPC:  cd terraform && terraform destroy"
