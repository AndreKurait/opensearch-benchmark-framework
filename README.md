# OpenSearch Benchmark Framework

Automated price-performance benchmarking of OpenSearch on EKS across multiple EC2 instance types and EBS configurations.

## Latest Results

**AMD Turin (m8a/c8a/r8a) appears to be the best 8th-gen EBS-based instance family for OpenSearch workloads** — delivering 37% faster indexing, 25% higher search QPS, and 32% lower p50 search latency than Graviton4 at only 9-12% higher cost, while being both faster and 6% cheaper than Intel Emerald Rapids across all instance families tested (m/c/r).

👉 **[Full benchmark report](results/REPORT.md)**

## Architecture

```
EKS Auto Mode (Karpenter built-in)
├── 18 NodePools (9 instance types × 2 EBS tiers)
├── 18 OpenSearch clusters (3-node each, 54 nodes total)
├── 18 OSB Jobs (parallel, results → ConfigMaps)
└── Auto-teardown (nodes terminate when idle)
```

**Instance types:** m8g, m8a, m8i, c8g, c8a, c8i, r8g, r8a, r8i (all .2xlarge)
**EBS tiers:** gp3-default (125 MB/s, 3K IOPS) vs gp3-fast (1 GB/s, 10K IOPS)
**Workload:** OSB 2.1 geonames (11.4M docs, full query suite, no rate limiting)

## Quick Start

```bash
# Prerequisites: AWS CLI configured, Terraform >= 1.5, kubectl, helm, python3, pyyaml, jq
pip install pyyaml

# Clone and run everything (provision → deploy → benchmark → report → teardown)
git clone https://github.com/AndreKurait/opensearch-benchmark-framework.git
cd opensearch-benchmark-framework
bash scripts/run-all.sh

# Or step by step with options:
bash scripts/run-all.sh --skip-teardown                    # keep cluster running
bash scripts/run-all.sh --workloads "geonames pmc"         # specific workloads only
bash scripts/run-all.sh --skip-infra --workloads "pmc"     # reuse existing cluster
```

### Step-by-step (manual)

```bash
# 1. Create EKS cluster (~10 min)
cd terraform
cp terraform.tfvars.example terraform.tfvars  # edit region/name if needed
terraform init && terraform apply
eval "$(terraform output -raw kubeconfig_cmd)"
cd ..

# 2. Generate manifests & deploy (~5 min)
python3 scripts/generate.py
bash scripts/deploy.sh

# 3. Run workloads (each ~30-45 min, all 18 permutations in parallel)
bash scripts/run.sh geonames && bash scripts/collect.sh geonames
bash scripts/run.sh pmc      && bash scripts/collect.sh pmc

# 4. Tear down
bash scripts/teardown.sh
cd terraform && terraform destroy
```

## Customization

Edit `scripts/generate.py` to modify:

```python
# Add/remove instance types
INSTANCES = {
    "m8a": {"type": "m8a.2xlarge", "cpu": "AMD Turin", ...},
    # Add your own:
    "m8a4xl": {"type": "m8a.4xlarge", "cpu": "AMD Turin", ...},
}

# Add/remove EBS tiers
EBS_TIERS = {
    "gp3-default": {"throughput": 125, "iops": 3000, "size": "100Gi"},
    "gp3-fast":    {"throughput": 1000, "iops": 10000, "size": "100Gi"},
    # Add your own:
    "io2-high":    {"throughput": 1000, "iops": 64000, "size": "100Gi"},
}

# Change OSB image (e.g., to use ECR mirror)
export OSB_IMAGE=your-ecr-uri/osb:latest
```

Then regenerate: `python3 scripts/generate.py`

## How It Works

1. **EKS Auto Mode** provides Karpenter out of the box — no manual node group management
2. **One NodePool per permutation** with `do-not-disrupt` ensures nodes stay alive during benchmarks
3. **OpenSearch deployed via Helm** with per-family JVM tuning (c=2GB, m=4GB, r=8GB)
4. **OSB runs as K8s Jobs** on the benchmark nodes themselves — no port-forwarding
5. **Results saved to ConfigMaps** via K8s API from within the pod — no log scraping race conditions
6. **`target_throughput: 10000`** removes OSB's default rate limiting for true max-throughput measurement
7. **`search_clients` scaled per family** (c=2, m=4, r=8) to match available heap

## Project Structure

```
├── terraform/              # EKS Auto Mode cluster
│   ├── main.tf
│   ├── variables.tf
│   └── terraform.tfvars.example
├── scripts/
│   ├── generate.py         # Generates K8s manifests from permutation config
│   ├── report.py           # Parses OSB CSV → REPORT.md
│   ├── deploy.sh           # Deploy all clusters
│   ├── run.sh              # Run all benchmarks
│   ├── collect.sh          # Collect results
│   └── teardown.sh         # Tear down everything
├── k8s/generated/          # Generated manifests (gitignored)
├── results/                # Benchmark results (gitignored)
└── .github/workflows/ci.yml  # CI: secrets scan + lint + validate
```

## CI/CD

GitHub Actions runs on every push/PR:
- **Secrets scan** — checks for AWS account IDs, resource IDs, ARNs, access keys, private IPs
- **Lint** — Python syntax, shell syntax, Terraform validate
- **Dry run** — generates all 18 permutations and verifies output

## Cost

Running all 18 permutations (54 nodes) for ~1 hour costs approximately $15-20. Nodes auto-terminate via Karpenter when workloads are removed.

## License

MIT
