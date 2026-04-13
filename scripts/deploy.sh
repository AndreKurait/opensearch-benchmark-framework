#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

CONFIG="k8s/generated/config.json"
[[ -f "$CONFIG" ]] || { echo "Run: python3 scripts/generate.py"; exit 1; }

PERMS=$(jq -r '.permutations[]' "$CONFIG")
COUNT=$(echo "$PERMS" | wc -l)

echo "==> Deploying $COUNT OpenSearch clusters"

kubectl apply -f k8s/generated/storageclasses.yaml
kubectl apply -f k8s/generated/rbac.yaml
kubectl apply -f k8s/generated/nodepools.yaml

helm repo add opensearch https://opensearch-project.github.io/helm-charts/ 2>/dev/null || true
helm repo update opensearch 2>&1 | tail -1

for pk in $PERMS; do
  NS="os-${pk}"
  kubectl create namespace "$NS" 2>/dev/null || true
  helm upgrade --install opensearch opensearch/opensearch \
    -n "$NS" --version 3.5.0 \
    -f "k8s/generated/opensearch/values-${pk}.yaml" \
    --wait=false &
done
wait
echo "==> Helm installs submitted. Karpenter provisioning nodes..."

echo "==> Waiting for pods..."
for i in $(seq 1 60); do
  ready=$(kubectl get pods -A --no-headers 2>/dev/null | grep "os-" | grep -c "1/1.*Running" || true)
  total=$((COUNT * 3))
  echo "  [$(date -u '+%H:%M')] $ready/$total pods ready"
  [[ $ready -ge $total ]] && break
  sleep 30
done
echo "==> Deploy complete"
