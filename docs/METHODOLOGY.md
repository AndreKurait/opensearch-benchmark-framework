# Methodology

This document records what this benchmark measures, what it deliberately does
not measure, and the specific errors in the first revision of this repo that the
current design exists to prevent. Read it before quoting any number from
`results/REPORT.md`.

## What is being compared

Three 8th-generation EC2 CPU architectures running OpenSearch 3.5 on EKS:

| CPU | Microarchitecture | Instance families |
|---|---|---|
| AWS Graviton4 | Neoverse V2, 2.8 GHz sustained | `m8g` `c8g` `r8g` |
| AMD Turin | Zen 5 (EPYC 9R45), up to 4.5 GHz | `m8a` `c8a` `r8a` |
| Intel Granite Rapids | Xeon 6 P-core, 3.9 GHz | `m8i` `c8i` `r8i` |

All specs and prices come from `ec2:DescribeInstanceTypes` and the AWS Pricing
API via `scripts/fetch_specs.py`, cached in `specs.json`. Nothing is hardcoded.

## The physical-core asymmetry you must account for

At equal vCPU count the three vendors do **not** give you equal hardware:

| instance | vCPU | physical cores | threads/core |
|---|--:|--:|--:|
| `m8g.8xlarge` (Graviton4) | 32 | 32 | 1 |
| `m8a.8xlarge` (AMD Turin) | 32 | 32 | 1 |
| `m8i.8xlarge` (Intel Granite Rapids) | 32 | **16** | 2 |

AWS ships the Graviton and AMD 8th-gen families with SMT **disabled**: one vCPU
is one physical core. The Intel families ship with SMT **enabled**: one vCPU is
one hardware thread, so an `m8i` gives you half the physical cores of an `m8g`
or `m8a` for the same vCPU count and a comparable bill.

Consequences:

* **Graviton4 vs AMD Turin is a clean per-core comparison.** Both are 1:1
  vCPU-to-core. Any difference is microarchitecture and clock (2.8 GHz fixed vs
  up to 4.5 GHz boost), not accounting.
* **Any comparison involving Intel is not per-core.** Intel is being asked to do
  the same work with half the physical cores. Reports must show the
  `physical cores` column so this is visible rather than hidden inside "vCPU".

`report.py` emits an explicit warning block whenever the matrix mixes
threads-per-core values.

## Design rules, and the failures that motivated them

### 1. The load generator is never co-located with the system under test

OSB runs on a dedicated node pool of a **single fixed instance type**
(`c8i.8xlarge` by default), tainted so no OpenSearch pod can land on it.

*Previously:* the OSB job was pinned to the SUT node with `limits.cpu: 2` while
OpenSearch requested `cpu: 6` on an 8-vCPU node. Two failures at once. One of
the three OpenSearch pods was starved relative to its peers, making the cluster
asymmetric. And because OSB is largely per-core-bound Python, running it on the
SUT meant a slower-per-core CPU slowed the *measuring instrument* as well as the
thing being measured — the architecture delta was counted twice, in favour of
whichever CPU had the higher clock.

### 2. Offered load is an independent axis

Client counts are fixed at `search_clients=64`, `bulk_indexing_clients=32` for
every instance type. Concurrency is varied instead by sweeping **offered search
throughput**: 500, 2000, 8000 ops/s, plus an unthrottled `saturate` level.

*Previously:* `SEARCH_CLIENTS = {"c": 2, "m": 4, "r": 8}` tied concurrency to
instance family, which simultaneously varied heap (2/4/8 GB) and RAM
(16/32/64 GB). Those three variables were perfectly confounded, so the framework
could not distinguish "this CPU is faster" from "this CPU was tested at a more
favourable occupancy". With 2–8 clients against 24 total vCPUs, the cluster was
never saturated — the measurement was effectively a clock-speed benchmark, which
is the single most boost-clock-favourable operating point available.

This matters for the headline conclusion. Graviton4 holds a flat 2.8 GHz with no
turbo; Turin boosts to ~4.5 GHz. At low occupancy the boost clock dominates. As
occupancy rises, all-core clocks converge and per-core count matters more. The
old matrix only sampled the low-occupancy end. The `saturate` level and the
"Scaling across load levels" table exist to sample the other end.

### 3. Latency and throughput are never both free variables

* At **fixed-rate** levels, offered load is pinned, so service time is
  comparable across architectures. The report also prints achieved vs offered
  throughput and flags any cell that could not sustain the offered rate — a
  shortfall invalidates that cell's service-time numbers.
* At the **saturate** level, throughput is comparable and latency is
  *deliberately not reported*, because at saturation latency is dominated by
  queue depth, not service time.

*Previously:* every run was unthrottled (`target_throughput: 10000`) and p50
latency was compared across permutations that achieved wildly different
throughputs. That is not a valid comparison in either direction.

The report also uses **service time** (excludes client-side queue wait) and
never silently falls back between service time and latency, which are different
quantities.

### 4. Statistics before conclusions

Every cell is run once per region, and each region is one repetition (see rule
4a). The report prints the median with its interquartile range, and emits a
comparative percentage **only when the two IQRs do not overlap**. Otherwise it
prints *within noise*.

*Previously:* n=1, no repetitions, no intervals. The variance was measurable
from the report's own contents: the EBS tier provably changed indexing time by
~1%, yet the same tier change swung search p50 by −50% to +94% across
permutations. Run-to-run noise was on the order of ±100%, which is far larger
than the 25–37% differences being published as findings.

### 4a. One region is one repetition, and it runs all nine instance types

The seven benchmark regions run **concurrently**, each executing the full
9-instance-type matrix once. Regions are the repetition axis.

This is not only a way to finish in 3 hours instead of 17. It is the more
defensible experiment. Repeating a cell on the *same* nodes samples only
run-to-run jitter, while the largest noise source in a cloud benchmark is
**host placement** — which physical socket you landed on, what neighbours you
share, how the rack is cabled. Same-node repetitions cannot see that variance,
so they produce error bars that are too narrow and invite over-claiming. Seven
regions means seven independent sets of physical hosts, so the IQRs widen to
something honest. Conclusions get *harder* to reach, not easier.

Two rules protect this from becoming a confound of its own:

* **A region always runs all nine instance types, or it is dropped entirely.**
  A region contributing only Graviton results would compare Graviton in region A
  against Turin in region B, which is no longer a CPU comparison. `fetch_specs.py`
  therefore marks a region `usable_as_repetition` only if every one of the nine
  types is offered at the benchmark size in a single shared AZ. Only 7 of 18
  candidate regions qualify — the AMD `*8a` types are the scarce ones.
* **Every node in a region is pinned to one AZ.** Otherwise some clusters sit one
  network hop from the load generator and others two, and that shows up as a
  throughput difference indistinguishable from an architecture difference. In
  `eu-west-1` exactly one AZ (`eu-west-1c`) offers all nine types, which is why
  terraform takes `bench_az` explicitly rather than trusting the first three AZs
  the API returns.

Because regions are also the repetition axis, **prices are never pooled**. The
same instance costs up to 29% more in `ap-northeast-1` than in `us-east-2`, so a
price-performance number averaged over regions would be meaningless. `report.py`
computes price-per-unit-work per region, quotes absolute dollars in one named
reference region, and asserts the *premium* is region-invariant — it is, to
within 0.5%, which is itself a useful cross-check.

`report.py` additionally asserts the hardware identity of every region before
pooling anything and refuses to produce a report if they disagree
(*"Results are not poolable"*), and `validate_manifests.py` asserts that heap
size, client counts, EBS settings and offered load are byte-identical across all
seven generated regions. A configuration difference between repetitions would
otherwise be silently absorbed into the error bars as if it were noise.

Finally, each region votes independently on the *sign* of every comparison. A
unanimous 7/7 vote is much stronger evidence than a pooled median; a split vote
means the effect is not robust **regardless of how the pooled IQRs fall**, and
the report says so explicitly. This is a deliberate second, independent guard on
top of the IQR test.

*Side effect worth knowing:* a region that fails mid-run costs one repetition,
not the whole experiment. The previous single-region design lost everything.

### 5. Throughput is the mean, not the max

`Mean Throughput`, not `Max Throughput`. OSB's `Max Throughput` is a single peak
sampling interval — the noisiest statistic it emits, and what the previous
revision reported.

### 6. Runs are validated, not just averaged

Each run records, into its result ConfigMap:

* the post-index document count, compared against the workload's known total;
* `_nodes/jvm`, `_nodes/os` and `_nodes/plugins`, so JVM build and architecture
  are on the record (a JIT or vectorisation difference between arm64 and x86
  must not be misread as a CPU difference);
* the OSB log, scanned for warnings that a workload parameter was ignored — this
  is how a nominally fixed-rate run can end up unthrottled unnoticed;
* the OSB exit code and per-task error rates.

`report.py` marks any run that fails these checks as **INVALID** and excludes it
from all medians, listing it in a validity ledger. `--on-error=continue` is
retained so a partial failure still yields data, but a run that silently drops
bulk requests otherwise measures as *faster*, which is worse than no data.

Raw CSV, log and probe output are **committed to git**. The previous revision
gitignored them, so no published number could be audited.

### 7. Instance size avoids burstable allocations

Default size is `8xlarge`. At `2xlarge` the EBS allocation is burstable —
312.5 MB/s baseline against a 1250 MB/s burst ceiling — so credit depletion
part-way through a 30–45 minute run is a large uncontrolled noise source, and
different permutations cross the credit boundary at different times. At
`8xlarge`, baseline equals maximum (1250 MB/s) and storage behaviour is
steady-state.

`2xlarge` is also the worst size for the core-count question: SMT and
core-scaling effects only really express themselves at higher core counts.

### 8. One realisable storage tier, not two unrealisable ones

A single `gp3` tier at 1000 MB/s / 16000 IOPS, which an `8xlarge` can actually
sustain.

*Previously:* a "gp3-fast" tier requested 1000 MB/s on nodes with a 312.5 MB/s
baseline. It could never be realised, which is why it moved indexing time by
~1%. Half the permutations bought nothing but noise. That budget is now spent on
repetitions instead.

### 9. Hard anti-affinity

`antiAffinity: hard`. Previously `soft`, where nothing but an accident of CPU
request arithmetic prevented two data pods from sharing a node and silently
invalidating a permutation.

### 10. Service naming has a single source of truth

`svc_name()` in `generate.py`.

*Previously:* `generate.py` pointed OSB at
`opensearch-cluster-master.<ns>.svc.cluster.local` while its own Helm values set
`clusterName: <perm>`, which makes the chart create `<perm>-master`. Meanwhile
`run.sh` used `<perm>-master-0`. The two files disagreed, so the committed code
could not have reached the clusters it was meant to measure — the committed
results were therefore not reproducible from the committed code.

## Known remaining limitations

These are real and are not fixed. Do not let the report imply otherwise.

* **RAM still varies with family.** `c`/`m`/`r` differ in memory (64/128/256 GiB
  at 8xlarge) and therefore in page-cache size. Heap is pinned at 26 GiB
  everywhere and no memory limit is set, so page cache is the only uncontrolled
  variable, and it is symmetric across vendors. Compare *within* a family for the
  cleanest signal.
* **`geonames` is cache-resident.** At ~3 GB it fits entirely in page cache on
  every node in the matrix, so it is a CPU and memory-bandwidth benchmark, not a
  storage one. `nyc_taxis` (~75 GB) and `http_logs` are configured for the
  I/O-bound case but are much slower and more expensive to run; if storage
  behaviour matters to your decision, run those.
* **Page cache is not dropped between repetitions.** Indices are deleted and
  re-created, but the kernel page cache is not explicitly flushed.
* **No spot/capacity-pool control.** On-demand instances land on whatever
  underlying host revision the AZ provides.
* **Vectorisation parity is recorded, not enforced.** The framework captures JVM
  and plugin state so an arm64/x86 Lucene vector-path difference is visible in
  the artifacts, but it does not pin JVM flags to force equivalence.
* **Region is confounded with repetition.** Each region contributes exactly one
  observation per cell, so a genuine regional effect (a different host hardware
  revision in one region, say) is inseparable from ordinary noise. This is the
  conservative direction — it widens intervals and suppresses claims rather than
  manufacturing them — but it means a *single* region's numbers should not be
  quoted on their own, and n is 7, which is small.
* **Only 7 regions carry all nine instance types**, so the repetition count is
  capped by AMD `*8a` availability, not chosen for statistical power.
* **No within-region repetition.** Placement variance is now sampled, but
  run-to-run jitter on fixed hardware is not measured separately from it, so the
  two cannot be attributed independently.

## How to read the report

1. Check the **Run validity** ledger first. Excluded runs mean thinner medians.
2. Check the **physical cores** column before comparing anything to Intel.
3. For latency, use a **fixed-rate** level, and confirm the achieved-throughput
   table shows no shortfall for the cells you are comparing.
4. For throughput, use the **saturate** level.
5. Treat *within noise* as "no difference was demonstrated". It is not a
   near-miss to be rounded into a claim.
6. Read the **price-adjusted** column before concluding anything about value.
   A performance win smaller than the price premium is a loss.
7. Check the **Cross-region agreement** table last, and let it override. A split
   vote means the direction of the effect was not reproducible across independent
   hardware, which disqualifies the percentage no matter how clean the IQRs look.
