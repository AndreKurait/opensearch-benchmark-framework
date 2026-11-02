> **Archived experiment — November 2026. The unfinished multi-region work and its result artifacts are preserved in [PR #1](https://github.com/AndreKurait/opensearch-benchmark-framework/pull/1) and `multi-region-repetitions`. These artifacts do not establish reproducible benchmark results; the provenance limitations below still apply.**

# OpenSearch Benchmark Framework

Automated price-performance benchmarking of OpenSearch on EKS across multiple EC2 instance types and EBS configurations.

## Status and historical results

This is an experimental benchmarking harness. The checked-in [historical report](results/REPORT.md)
contains a previous run's conclusions, but its raw CSVs, exact image/workload revisions, and repeated
measurements are not checked in. Those conclusions are not independently reproducible from this
repository and should not be generalized to other workloads, configurations, or current prices.

The report generator now shows individual observations, missing-data coverage, units, and available
p50/p99 latency. It does not substitute service time for latency, average unlike workloads, or declare
an overall winning CPU. Cumulative indexing time is shard work, not elapsed runtime.

## Architecture

```
EKS Auto Mode (Karpenter built-in)
├── 18 NodePools (9 instance types × 2 EBS tiers)
├── 18 OpenSearch clusters (3-node each, 54 nodes total)
├── 18 OSB Jobs (parallel, results → ConfigMaps)
└── Explicit teardown (NodePools disable consolidation during a run)
```

**Instance types:** m8g, m8a, m8i, c8g, c8a, c8i, r8g, r8a, r8i (all .2xlarge)
**EBS tiers:** gp3-default (125 MB/s, 3K IOPS) vs gp3-fast (1 GB/s, 10K IOPS)
**Workloads:** geonames, pmc, nyc_taxis, and http_logs. Query concurrency and heap vary by instance family.
The default benchmark image uses a mutable `latest` tag; set `OSB_IMAGE` to a tested digest when reproducing results.

## Quick Start

```bash
# Prerequisites: AWS CLI configured, Terraform >= 1.5, kubectl, helm, python3, pyyaml, jq
pip install pyyaml

# First inspect terraform/ and scripts/generate.py: this creates billable AWS resources.
# Run in a dedicated benchmark account/cluster; OpenSearch authentication is disabled.
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
6. **`target_throughput: 10000`** configures the workload target; this does not prove an unconstrained maximum
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
├── results/                # Historical report; new raw results are gitignored
└── .github/workflows/ci.yml  # CI: secrets scan + lint + validate
```

## CI/CD

GitHub Actions runs on every push/PR:
- **Secrets scan** — checks for AWS account IDs, resource IDs, ARNs, access keys, private IPs
- **Lint** — Python syntax, shell syntax, Terraform validate
- **Dry run** — generates all 18 permutations and verifies output
- **Offline regression tests** — generated job execution, failure propagation, CSV parsing, and reporting

Run the offline checks with `python3 -m unittest discover -s tests -v` after installing `pyyaml`. They do not contact AWS or Kubernetes.

## Cost and cleanup

The default matrix requests 54 OpenSearch nodes, plus benchmark pods and supporting infrastructure.
Prices in `scripts/generate.py` are configuration inputs without a recorded region/date; they are not
current quotes and exclude storage, EKS/Auto Mode, and networking fees. Review pricing and quotas before
running. The four default workloads can take substantially longer than one hour.

NodePool consolidation is disabled during benchmarks. `run-all.sh` tears down on a successful run unless
`--skip-teardown` is set. A failure or interruption leaves resources for inspection; run
`bash scripts/teardown.sh`, then `terraform -chdir=terraform destroy`, and verify cleanup in your account.
The teardown script is best effort and its final message is not proof that every resource was removed.

Jobs abort on benchmark errors, do not automatically retry against partially indexed data, and have a
two-hour deadline. `run.sh` checks Job success/failure with a bounded wait rather than treating the presence
of a ConfigMap as success. Collection requires the recorded successful exit code. Existing ConfigMaps
from older runs do not contain this marker and must not be mixed with new results.

Collection stages every permutation before publishing the workload's result directory, so a later
fetch or exit-status failure leaves the previous results intact. Job-status fetch failures retry
within the polling deadline. Explicit empty or whitespace-only `--workloads` values are rejected;
omitting the option still selects the default workloads.

Before launching a workload, `run.sh` waits for previous Jobs for that workload and their pods to stop,
then requires acknowledged index deletion on every target. Cleanup uses `python3` inside the OpenSearch
pods; a missing interpreter, HTTP error, or unacknowledged deletion stops the run before new Jobs launch.

## Reproducing a comparison

Retain raw CSVs and logs for repeated runs, Job status, generated config/manifests, the benchmark image
digest, workload commit, OpenSearch/chart versions, region, and pricing date. Compare matching workload,
instance family, storage, and concurrency. The load generator shares benchmark nodes, so account for that
contention. Record variance and error rates before claiming a throughput or latency improvement.

Offline checks cover generated commands and report integrity. A full EKS benchmark run is still required
to validate provisioning, chart compatibility, workload completion, and cleanup after a change.

## License

MIT. See [LICENSE](LICENSE).
