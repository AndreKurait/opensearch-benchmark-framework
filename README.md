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

**Reported:** medians over 7 repetitions — one per region, on independent
hardware — with interquartile ranges. A difference is only stated as a percentage
when the IQRs do not overlap *and* the regions agree on its direction.

> ### Read this before quoting a number
> At equal vCPU count the vendors do not give you equal hardware. Graviton4 and
> AMD Turin 8th-gen instances ship with **SMT disabled** (1 vCPU = 1 physical
> core). Intel 8th-gen instances ship with **SMT enabled** (1 vCPU = 1 thread,
> so half the physical cores for the same vCPU count). Graviton-vs-Turin is a
> clean per-core comparison; anything involving Intel is not. The report prints
> a `physical cores` column for this reason.

## Architecture

7 regions concurrently, each one independent repetition of:

```
EKS Auto Mode (Karpenter built-in)      [all nodes pinned to ONE AZ]
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

### One region is one repetition

The suite runs in **7 regions concurrently**, each executing the full
9-instance-type matrix once. Regions are the repetition axis, for two reasons:

* **Wall clock.** Repetitions run in parallel rather than in series: 7 reps take
  ~3 h instead of ~17 h, because the only thing that duplicates is provisioning
  overhead, and that duplicates in parallel too.
* **Better error bars.** Repeating a cell on the *same* nodes samples only
  run-to-run jitter. The dominant noise source in cloud benchmarking is host
  placement, and 7 regions means 7 independent sets of physical hosts. IQRs get
  wider and more honest, so claims get harder to make, not easier.

Only 7 of 18 candidate regions offer all nine 8th-gen types in a single shared
AZ (the AMD `*8a` types are the scarce ones). A region must run **all nine** or
it is dropped — a partial region would compare Graviton in one region against
Turin in another, which is not a CPU comparison. `fetch_specs.py` determines this
from the AWS APIs and records it as `usable_as_repetition` in `specs.json`.

Because regions differ in price by up to 29%, prices are **never pooled**:
`report.py` computes price-performance per region and quotes absolute dollars in
one named reference region.

### Controlling matrix size

Cost scales with load levels × regions (cells run sequentially within a region;
all nine instance types run in parallel within a cell). Check before committing:

```bash
python3 scripts/fetch_specs.py
for rg in $(python3 -c "import json;print(' '.join(r for r,v in json.load(open('specs.json'))['regions'].items() if v['usable_as_repetition']))"); do
  BENCH_REGION=$rg python3 scripts/generate.py
done
python3 scripts/validate_manifests.py && python3 scripts/estimate.py
```

```bash
# Pilot: validate the harness end to end in two regions, one load level
BENCH_LOADS=saturate bash scripts/run-all.sh --regions us-east-1,us-east-2

# Full: 4 load levels, all 7 regions (~3 h, ~$1,310)
bash scripts/run-all.sh

# Cheap smoke test on burstable instances (NOT publication quality)
BENCH_SIZE=2xlarge BENCH_LOADS=saturate bash scripts/run-all.sh --regions us-east-2
```

Environment variables: `BENCH_SIZE`, `BENCH_LOADS`, `BENCH_WORKLOADS`,
`BENCH_LOADGEN_TYPE`, `BENCH_REGION`, `BENCH_AZ`, `OSB_IMAGE`.

Each region gets its own terraform state directory (`.runs/<region>/`) and its
own kubeconfig, so concurrent runs cannot corrupt shared state and concurrent
`kubectl` calls cannot race on the current context.

A pre-flight check refuses to generate if the matrix (960 vCPU) exceeds a
region's `Running On-Demand Standard instances` quota — all nine families share
one bucket, and Karpenter would otherwise quietly provision a partial matrix and
produce a comparison with missing arms.

### Step by step (single region)

```bash
export BENCH_REGION=us-east-1
python3 scripts/fetch_specs.py            # prices, cores, quotas -- per region
python3 scripts/generate.py               # manifests -> k8s/generated/$BENCH_REGION/
python3 scripts/validate_manifests.py     # experiment invariants
python3 scripts/estimate.py               # cost/time estimate
# provision the cluster from terraform/ with region + bench_az set, then:
eval "$(cd terraform && terraform output -raw kubeconfig_cmd)"
bash scripts/deploy.sh                    # 9 clusters + loadgen pool
bash scripts/run.sh geonames              # all load levels for this region
python3 scripts/report.py                 # results/REPORT.md
bash scripts/teardown.sh                  # then destroy the cluster
```

`terraform/` needs `region` and `bench_az` set to match `BENCH_REGION`; the AZ
must be one that offers all nine instance types (`azs_with_all_families` in
`specs.json`). `run-all.sh` handles this automatically for every region.

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
│   ├── run.sh                  # one region's load levels, checkpointed
│   ├── run-all.sh              # all regions concurrently, end to end
│   ├── collect.sh              # one cell → results/ raw artifacts
│   ├── report.py               # raw results → REPORT.md with IQRs
│   ├── validate_manifests.py   # experiment invariants (CI gate)
│   ├── test_report_synthetic.py # exercises report.py on fabricated results
│   └── teardown.sh
├── specs.json                  # committed API-derived specs, per region
├── docs/METHODOLOGY.md         # what this measures, and what it doesn't
├── results/<wl>/<load>/<region>/  # RAW CSV/log/probe output IS committed
├── logs/<region>.log           # per-region run logs (gitignored)
└── k8s/generated/<region>/     # generated manifests (gitignored)
```

## Cost

Depends on matrix size; `scripts/estimate.py` prints the figure for your
configuration before anything is provisioned, and `run-all.sh` requires explicit
confirmation. Wall clock is set by **one** region's pass over the load levels,
because regions run concurrently; cost is the sum across regions.

For the default matrix (9 types × 4 load levels × `geonames` × 7 regions = 252
runs, 210 nodes): **~3.0 h, ~$1,310**. The same 7 repetitions run sequentially in
the cheapest single region would be ~17 h and ~$985 — so parallelising across
regions is ~5.7× faster for ~1.33× the cost.

## Testing the reporting path

A crash or mis-aggregation in `report.py` would only surface *after* the
benchmark has been paid for, so it is tested against fabricated results with a
known planted answer:

```bash
python3 scripts/test_report_synthetic.py
```

This asserts that a unanimous cross-region effect is detected, that a 4–3 split
is refused rather than quoted, and that runs with error rates or doc-count
mismatches are excluded from the medians.

## CI

GitHub Actions on every push/PR: secrets scan, Python/shell/Terraform lint, and
a dry-run that generates the matrix for **every** benchmark region and asserts
the invariants that matter (load generator is tainted off the SUT, all nodes
AZ-pinned, client counts and heap identical across permutations *and across
regions*, no prices hardcoded outside `specs.json`).

## License

MIT
