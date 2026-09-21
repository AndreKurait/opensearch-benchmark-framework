# OpenSearch Benchmark Framework

Controlled price-performance comparison of OpenSearch 3.5 across 8th-generation
EC2 CPU architectures (AWS Graviton4, AMD Turin, Intel Granite Rapids) on EKS.

## Status

The framework has been rebuilt to fix methodology errors that invalidated the
previous published results. **The old `results/REPORT.md` conclusion — "AMD Turin
is the best 8th-gen instance family for OpenSearch" — has been withdrawn.** It
did not survive review:

* Its cost figures were hardcoded, 30–49% below list price, and **wrong in
  ordering**. Turin is not 9–12% more expensive than Graviton4, it is ~35%
  more expensive; and it is not 6% cheaper than Intel, it is ~15% more
  expensive. A 37% indexing win at a 35% price premium is roughly a wash, and
  the search-throughput claim goes negative on price-performance.
* It labelled the Intel parts "Emerald Rapids". `m8i`/`c8i`/`r8i` are **Granite
  Rapids** (Xeon 6) — a generation out.
* Every comparison was **n=1**, while its own data implies run-to-run variance
  around ±100% — larger than any effect it reported.
* The load generator ran **on the machine under test**, so a slower-per-core CPU
  also slowed the measuring instrument.
* Concurrency was tied to instance family, confounding it with heap size and
  RAM, and holding the whole matrix at an occupancy far too low to saturate the
  cluster.
* Its committed manifests pointed OSB at a **service name the Helm chart never
  created**, so the published results are not reproducible from the code.

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for the full list and the design
rules that now prevent each one. New results will be published once the
rebuilt matrix has been run.

## What it measures

**Instance types:** `m8g` `m8a` `m8i` `c8g` `c8a` `c8i` `r8g` `r8a` `r8i`,
default size `8xlarge` (32 vCPU — avoids the burstable EBS allocations that make
`2xlarge` results noisy).

**Load axis:** offered search throughput at 500 / 2000 / 8000 ops/s plus an
unthrottled `saturate` level. Client counts are fixed at 64 search / 32 bulk for
every instance type, so concurrency is varied independently of instance family.

**Controlled identically everywhere:** JVM heap (26 GiB), CPU request, client
counts, shard/replica counts, storage tier, and the load-generator instance type.

**Reported:** medians over 5 repetitions with interquartile ranges. A difference
is only stated as a percentage when the IQRs do not overlap.

> ### Read this before quoting a number
> At equal vCPU count the vendors do not give you equal hardware. Graviton4 and
> AMD Turin 8th-gen instances ship with **SMT disabled** (1 vCPU = 1 physical
> core). Intel 8th-gen instances ship with **SMT enabled** (1 vCPU = 1 thread,
> so half the physical cores for the same vCPU count). Graviton-vs-Turin is a
> clean per-core comparison; anything involving Intel is not. The report prints
> a `physical cores` column for this reason.

## Architecture

```
EKS Auto Mode (Karpenter built-in)
├── 9 SUT NodePools (one per instance type, 3 nodes each)
├── 1 loadgen NodePool  (fixed instance type, tainted, never runs OpenSearch)
├── 9 OpenSearch clusters (3-node each, identical config)
├── OSB Jobs on the loadgen pool (results → ConfigMaps)
└── Auto-teardown (nodes terminate when workloads are removed)
```

## Quick start

```bash
# Prerequisites: AWS creds, Terraform >= 1.5, kubectl, helm, jq, python3
pip install pyyaml boto3

git clone https://github.com/AndreKurait/opensearch-benchmark-framework.git
cd opensearch-benchmark-framework

# Shows a cost estimate and prompts before spending anything
bash scripts/run-all.sh
```

### Controlling matrix size

Cost scales with load levels × repetitions (cells run sequentially; all nine
instance types run in parallel within a cell). Check before you commit to a run:

```bash
python3 scripts/fetch_specs.py && python3 scripts/generate.py && python3 scripts/estimate.py
```

```bash
# Pilot: validate the harness end to end, one load level, 2 reps
BENCH_REPS=2 BENCH_LOADS=saturate bash scripts/run-all.sh

# Full: 4 load levels, 5 reps
BENCH_REPS=5 bash scripts/run-all.sh

# Cheap smoke test on burstable instances (NOT publication quality)
BENCH_SIZE=2xlarge BENCH_REPS=2 BENCH_LOADS=saturate bash scripts/run-all.sh
```

Environment variables: `BENCH_SIZE`, `BENCH_REPS`, `BENCH_LOADS`,
`BENCH_WORKLOADS`, `BENCH_LOADGEN_TYPE`, `OSB_IMAGE`.

### Step by step

```bash
python3 scripts/fetch_specs.py --region us-east-1   # prices + core counts from AWS APIs
python3 scripts/generate.py                         # manifests
python3 scripts/estimate.py                         # cost/time estimate
cd terraform && terraform init && terraform apply && cd ..
eval "$(cd terraform && terraform output -raw kubeconfig_cmd)"
bash scripts/deploy.sh                              # 9 clusters + loadgen pool
bash scripts/run.sh geonames                        # all load levels × reps
python3 scripts/report.py                           # results/REPORT.md
bash scripts/teardown.sh && cd terraform && terraform destroy
```

## Customisation

Edit the axes at the top of `scripts/generate.py`:

```python
FAMILY_KEYS = ["m8g", "m8a", "m8i", "c8g", "c8a", "c8i", "r8g", "r8a", "r8i"]
SIZE = "8xlarge"
LOADGEN_TYPE = "c8i.8xlarge"        # fixed for the whole matrix, on purpose

LOAD_LEVELS = {
    "load-500":  {"target_throughput": 500,  "kind": "fixed-rate"},
    "saturate":  {"target_throughput": 0,    "kind": "saturate"},
}
```

Adding an instance type requires it to be present in `specs.json` — re-run
`fetch_specs.py` after editing `FAMILIES` there. Prices are never hardcoded.

## Project structure

```
├── terraform/                  # EKS Auto Mode cluster
├── scripts/
│   ├── fetch_specs.py          # AWS Pricing + DescribeInstanceTypes → specs.json
│   ├── generate.py             # permutation config → K8s manifests
│   ├── estimate.py             # cost / wall-clock estimate
│   ├── deploy.sh               # 9 clusters + loadgen pool
│   ├── run.sh                  # all load levels × reps, checkpointed
│   ├── collect.sh              # one cell → results/ raw artifacts
│   ├── report.py               # raw results → REPORT.md with IQRs
│   └── teardown.sh
├── specs.json                  # committed API-derived specs (auditable)
├── docs/METHODOLOGY.md         # what this measures, and what it doesn't
├── results/                    # RAW CSV/log/probe output IS committed
└── k8s/generated/              # generated manifests (gitignored)
```

## Cost

Depends entirely on matrix size; `scripts/estimate.py` prints the figure for your
configuration before anything is provisioned. Cells run sequentially, so wall
clock and cost scale with `load levels × repetitions`, not with instance count.
`run-all.sh` requires explicit confirmation before provisioning.

## CI

GitHub Actions on every push/PR: secrets scan, Python/shell/Terraform lint, and
a dry-run that generates the full matrix and asserts the invariants that matter
(load generator is tainted off the SUT, client counts and heap are identical
across permutations, no prices hardcoded outside `specs.json`).

## License

MIT
