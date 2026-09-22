# OpenSearch 3.5 — 8th-Gen EC2 CPU Architecture Benchmark

**Generated:** 2026-09-22 21:00 UTC  
**Instance size:** `8xlarge` | **Load generator:** `c8i.8xlarge` (fixed everywhere)  
**Repetitions:** 7, one per region | **Tool:** OpenSearch Benchmark | **OpenSearch:** 3.5.0 | **EKS Auto Mode + Karpenter**

| repetition (region) | AZ | 27-node $/hr |
|---|---|--:|
| `ap-northeast-1` | `ap-northeast-1a` | $60.77 |
| `eu-central-1` | `eu-central-1a` | $57.75 |
| `eu-south-2` | `eu-south-2a` | $53.81 |
| `eu-west-1` | `eu-west-1c` | $53.82 |
| `us-east-1` | `us-east-1a` | $48.72 |
| `us-east-2` | `us-east-2a` | $48.71 |
| `us-west-2` | `us-west-2a` | $48.72 |

> **Each repetition is a separate region**, running the full nine-type matrix on its own EKS cluster, pinned to a single AZ. Repetitions therefore sample independent hardware and independent capacity pools, so the interquartile ranges below reflect real placement variance — not just run-to-run jitter on one set of nodes. No comparison is ever split across regions.

> All figures are **medians over repetitions**, with the interquartile range in brackets. A comparison is reported as a percentage **only when the two IQRs do not overlap**; otherwise it reads *within noise*. Price-adjusted figures are computed **within** each region and then aggregated, because on-demand prices differ by up to 29% between regions. See [METHODOLOGY.md](../docs/METHODOLOGY.md).

## Instances under test

| perm | instance | CPU | µarch | vCPU | physical cores | threads/core | RAM | clock | $/hr | 3-node $/hr |
|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|
| `m8g` | m8g.8xlarge | Graviton4 | Neoverse V2 | 32 | **32** | 1 | 128 GiB | 2.7 GHz | $1.8550 | $5.5651 |
| `m8a` | m8a.8xlarge | AMD Turin | Zen 5 | 32 | **32** | 1 | 128 GiB | Up to 4.5 GHz | $2.5155 | $7.5466 |
| `m8i` | m8i.8xlarge | Intel Granite Rapids | Xeon 6 P-core | 32 | **16** | 2 | 128 GiB | 3.9 GHz | $2.1874 | $6.5621 |
| `c8g` | c8g.8xlarge | Graviton4 | Neoverse V2 | 32 | **32** | 1 | 64 GiB | 2.7 GHz | $1.6010 | $4.8029 |
| `c8a` | c8a.8xlarge | AMD Turin | Zen 5 | 32 | **32** | 1 | 64 GiB | Up to 4.5 GHz | $2.1706 | $6.5117 |
| `c8i` | c8i.8xlarge | Intel Granite Rapids | Xeon 6 P-core | 32 | **16** | 2 | 64 GiB | 3.9 GHz | $1.8875 | $5.6626 |
| `r8g` | r8g.8xlarge | Graviton4 | Neoverse V2 | 32 | **32** | 1 | 256 GiB | 2.7 GHz | $2.2739 | $6.8218 |
| `r8a` | r8a.8xlarge | AMD Turin | Zen 5 | 32 | **32** | 1 | 256 GiB | Up to 4.5 GHz | $3.0835 | $9.2506 |
| `r8i` | r8i.8xlarge | Intel Granite Rapids | Xeon 6 P-core | 32 | **16** | 2 | 256 GiB | 3.9 GHz | $2.6813 | $8.0438 |

> ⚠️ **Physical-core asymmetry at equal vCPU count.** AMD Turin, Graviton4 ship with SMT disabled (1 vCPU = 1 physical core), while Intel Granite Rapids ship with SMT enabled (1 vCPU = 1 hardware thread, so half the physical cores for the same vCPU count and the same bill). Per-vCPU comparisons therefore understate Intel Granite Rapids per-core capability and overstate its per-socket capability. Read the **physical cores** column before drawing any conclusion from these tables.

### Relative on-demand price

Absolute prices below are `ap-northeast-1`. The **premium columns are region-invariant**: within a family the three vendors' prices scale by the same regional multiplier, so the price *ratios* — which is what price-performance depends on — hold in all 7 regions. Verified rather than assumed; a mismatch is flagged inline.

| family | Graviton4 | AMD Turin | Intel Granite Rapids | Turin vs Graviton | Turin vs Intel |
|---|--:|--:|--:|--:|--:|
| m | $1.8550 | $2.5155 | $2.1874 | +35.6% | +15.0% |
| c | $1.6010 | $2.1706 | $1.8875 | +35.6% | +15.0% |
| r | $2.2739 | $3.0835 | $2.6813 | +35.6% | +15.0% |

## Workload: `geonames`

### Search — load level `load-2000` (fixed offered rate 2000 ops/s)

Offered load is pinned, so **service time is comparable across architectures** here.

| perm | CPU | cores | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | 32 | — | — | — | — | — |
| `m8a` | AMD Turin | 32 | — | — | — | — | — |
| `m8i` | Intel Granite Rapids | 16 | — | — | — | — | — |
| `c8g` | Graviton4 | 32 | — | — | — | — | — |
| `c8a` | AMD Turin | 32 | — | — | — | — | — |
| `c8i` | Intel Granite Rapids | 16 | — | — | — | — | — |
| `r8g` | Graviton4 | 32 | — | — | — | — | — |
| `r8a` | AMD Turin | 32 | — | — | — | — | — |
| `r8i` | Intel Granite Rapids | 16 | — | — | — | — | — |

Achieved vs offered throughput (a shortfall means the cell could not sustain the offered rate, which invalidates its service-time numbers):

| perm | CPU | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | — | — | — | — | — |
| `m8a` | AMD Turin | — | — | — | — | — |
| `m8i` | Intel Granite Rapids | — | — | — | — | — |
| `c8g` | Graviton4 | — | — | — | — | — |
| `c8a` | AMD Turin | — | — | — | — | — |
| `c8i` | Intel Granite Rapids | — | — | — | — | — |
| `r8g` | Graviton4 | — | — | — | — | — |
| `r8a` | AMD Turin | — | — | — | — | — |
| `r8i` | Intel Granite Rapids | — | — | — | — | — |

### Search — load level `load-500` (fixed offered rate 500 ops/s)

Offered load is pinned, so **service time is comparable across architectures** here.

| perm | CPU | cores | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | 32 | 1.489ms [1.487ms–1.532ms] | 1.709ms [1.709ms–1.730ms] | 1.453ms [1.449ms–1.490ms] | 357ms [354ms–376ms] | 694ms [690ms–706ms] |
| `m8a` | AMD Turin | 32 | 1.334ms [1.307ms–1.432ms] | 1.472ms [1.390ms–1.572ms] | 1.342ms [1.294ms–1.425ms] | 234ms [225ms–241ms] | 691ms [668ms–701ms] |
| `m8i` | Intel Granite Rapids | 16 | 2.075ms [1.929ms–2.089ms] | 2.099ms [2.015ms–2.130ms] | 1.919ms [1.910ms–2.015ms] | 446ms [439ms–446ms] | 689ms [633ms–701ms] |
| `c8g` | Graviton4 | 32 | 1.464ms [1.418ms–1.608ms] | 1.678ms [1.622ms–1.939ms] | 1.429ms [1.378ms–1.645ms] | 375ms [360ms–376ms] | 822ms [773ms–861ms] |
| `c8a` | AMD Turin | 32 | 1.198ms [1.149ms–1.199ms] | 1.291ms [1.272ms–1.314ms] | 1.247ms [1.238ms–1.265ms] | 241ms [237ms–248ms] | 864ms [860ms–866ms] |
| `c8i` | Intel Granite Rapids | 16 | 2.051ms [1.958ms–2.076ms] | 1.960ms [1.944ms–2.325ms] | 2.069ms [2.000ms–2.085ms] | 450ms [439ms–452ms] | 779ms [776ms–796ms] |
| `r8g` | Graviton4 | 32 | 1.434ms [1.429ms–1.499ms] | 1.686ms [1.640ms–1.735ms] | 1.452ms [1.433ms–1.454ms] | 380ms [365ms–380ms] | 823ms [802ms–833ms] |
| `r8a` | AMD Turin | 32 | 1.214ms [1.160ms–1.357ms] | 1.350ms [1.343ms–1.363ms] | 1.146ms [1.114ms–1.247ms] | 231ms [227ms–235ms] | 814ms [797ms–833ms] |
| `r8i` | Intel Granite Rapids | 16 | 1.757ms [1.692ms–2.018ms] | 2.190ms [2.189ms–2.228ms] | 1.946ms [1.857ms–2.034ms] | 443ms [430ms–461ms] | 671ms [625ms–740ms] |

Achieved vs offered throughput (a shortfall means the cell could not sustain the offered rate, which invalidates its service-time numbers):

| perm | CPU | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | 500 | 500 | 500 | **164** ⚠️ | 2,222 |
| `m8a` | AMD Turin | 500 | 500 | 500 | **247** ⚠️ | 2,227 |
| `m8i` | Intel Granite Rapids | 500 | 500 | 500 | **137** ⚠️ | 2,255 |
| `c8g` | Graviton4 | 500 | 500 | 500 | **165** ⚠️ | 1,785 |
| `c8a` | AMD Turin | 500 | 500 | 500 | **250** ⚠️ | 1,827 |
| `c8i` | Intel Granite Rapids | 500 | 500 | 500 | **137** ⚠️ | 1,781 |
| `r8g` | Graviton4 | 500 | 500 | 500 | **166** ⚠️ | 1,789 |
| `r8a` | AMD Turin | 500 | 500 | 500 | **257** ⚠️ | 1,990 |
| `r8i` | Intel Granite Rapids | 500 | 500 | 500 | **136** ⚠️ | 2,035 |

### Scaling across load levels (term query)

This is the axis the previous revision could not measure, because client count was tied to instance family (c=2, m=4, r=8) and therefore confounded with heap size and RAM. Here client count is fixed at 64 everywhere and only the offered rate varies.

| perm | CPU | cores | `load-2000` | `load-500` |
|---|---|--:|--:|--:|
| `m8g` | Graviton4 | 32 | — | 500 [500–500] |
| `m8a` | AMD Turin | 32 | — | 500 [500–500] |
| `m8i` | Intel Granite Rapids | 16 | — | 500 [500–500] |
| `c8g` | Graviton4 | 32 | — | 500 [500–500] |
| `c8a` | AMD Turin | 32 | — | 500 [500–500] |
| `c8i` | Intel Granite Rapids | 16 | — | 500 [500–500] |
| `r8g` | Graviton4 | 32 | — | 500 [500–500] |
| `r8a` | AMD Turin | 32 | — | 500 [500–500] |
| `r8i` | Intel Granite Rapids | 16 | — | 500 [500–500] |

### Head-to-head, noise-gated

Percentages appear only where the interquartile ranges of the two medians do not overlap. Everything else is *within noise* and must not be quoted as a result.

| family | comparison | load level | metric | baseline | challenger | challenger vs baseline | price-adjusted |
|---|---|---|---|--:|--:|--:|--:|
| m | Turin vs Graviton4 | (indexing) | index time | — | — | insufficient reps | — |
| m | Turin vs Graviton4 | `load-2000` | term service time | — | — | insufficient reps | — |
| m | Turin vs Graviton4 | `load-500` | term service time | 1.489ms [1.487ms–1.532ms] | 1.334ms [1.307ms–1.432ms] | +10.4% | -25.2% |
| c | Turin vs Graviton4 | (indexing) | index time | — | — | insufficient reps | — |
| c | Turin vs Graviton4 | `load-2000` | term service time | — | — | insufficient reps | — |
| c | Turin vs Graviton4 | `load-500` | term service time | 1.464ms [1.418ms–1.608ms] | 1.198ms [1.149ms–1.199ms] | +18.2% | -17.4% |
| r | Turin vs Graviton4 | (indexing) | index time | — | — | insufficient reps | — |
| r | Turin vs Graviton4 | `load-2000` | term service time | — | — | insufficient reps | — |
| r | Turin vs Graviton4 | `load-500` | term service time | 1.434ms [1.429ms–1.499ms] | 1.214ms [1.160ms–1.357ms] | +15.4% | -20.2% |
| m | Intel vs Graviton4 | (indexing) | index time | — | — | insufficient reps | — |
| m | Intel vs Graviton4 | `load-2000` | term service time | — | — | insufficient reps | — |
| m | Intel vs Graviton4 | `load-500` | term service time | 1.489ms [1.487ms–1.532ms] | 2.075ms [1.929ms–2.089ms] | -39.4% | -57.3% |
| c | Intel vs Graviton4 | (indexing) | index time | — | — | insufficient reps | — |
| c | Intel vs Graviton4 | `load-2000` | term service time | — | — | insufficient reps | — |
| c | Intel vs Graviton4 | `load-500` | term service time | 1.464ms [1.418ms–1.608ms] | 2.051ms [1.958ms–2.076ms] | -40.1% | -58.0% |
| r | Intel vs Graviton4 | (indexing) | index time | — | — | insufficient reps | — |
| r | Intel vs Graviton4 | `load-2000` | term service time | — | — | insufficient reps | — |
| r | Intel vs Graviton4 | `load-500` | term service time | 1.434ms [1.429ms–1.499ms] | 1.757ms [1.692ms–2.018ms] | -22.5% | -40.4% |

*price-adjusted* = performance delta minus the on-demand price delta. Negative means the faster instance is not worth its premium at list price. The price delta is region-invariant within a family (see the price table), so one figure is valid for all regions.

### Cross-region agreement (term query)

Each region is an independent repetition on independent hardware. Below, each region votes on the sign of each pairwise difference. Unanimous agreement across regions is far stronger evidence than a pooled median alone, and a split vote means the effect is not robust no matter how the IQRs fall.

| family | comparison | load level | regions favouring challenger | favouring baseline | verdict |
|---|---|---|--:|--:|---|
| m | Turin vs Graviton4 | `load-2000` | 2 | 0 | **unanimous: Turin** (2/2) |
| m | Turin vs Graviton4 | `load-500` | 4 | 0 | **unanimous: Turin** (4/4) |
| c | Turin vs Graviton4 | `load-2000` | 2 | 0 | **unanimous: Turin** (2/2) |
| c | Turin vs Graviton4 | `load-500` | 3 | 0 | **unanimous: Turin** (3/3) |
| r | Turin vs Graviton4 | `load-2000` | 2 | 0 | **unanimous: Turin** (2/2) |
| r | Turin vs Graviton4 | `load-500` | 5 | 0 | **unanimous: Turin** (5/5) |
| m | Intel vs Graviton4 | `load-2000` | 0 | 2 | **unanimous: Graviton4** (2/2) |
| m | Intel vs Graviton4 | `load-500` | 0 | 5 | **unanimous: Graviton4** (5/5) |
| c | Intel vs Graviton4 | `load-2000` | 0 | 2 | **unanimous: Graviton4** (2/2) |
| c | Intel vs Graviton4 | `load-500` | 0 | 5 | **unanimous: Graviton4** (5/5) |
| r | Intel vs Graviton4 | `load-2000` | 0 | 2 | **unanimous: Graviton4** (2/2) |
| r | Intel vs Graviton4 | `load-500` | 0 | 5 | **unanimous: Graviton4** (5/5) |

A split vote overrides any percentage in the table above: if regions disagree on the direction, the effect is within regional noise regardless of what the pooled IQRs show.

## Run validity

All collected runs passed validity checks (error rate ≤ 0.1%, doc counts verified, no ignored workload params, OSB exit 0).

60 run(s) included but with a weakened audit trail:

| workload | load | rep | perm | caveat |
|---|---|---|---|---|
| geonames | load-2000 | eu-south-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | ap-northeast-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | ap-northeast-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | ap-northeast-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | ap-northeast-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | ap-northeast-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | ap-northeast-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | ap-northeast-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | ap-northeast-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | r8i | doc count unverified (probe could not reach cluster) |

`doc count unverified (probe could not reach cluster)` means the in-pod probe failed, not that the data is wrong: the opensearch-benchmark image ships no `curl`, so every probe request returned empty. Doc counts for these runs were instead verified out-of-band directly against each cluster, and came back identical (11,396,503 documents, 3/3 shards successful) on Graviton, AMD and Intel alike. The probe is fixed for subsequent runs.

*Generated 2026-09-22 21:00 UTC — [opensearch-benchmark-framework](https://github.com/AndreKurait/opensearch-benchmark-framework)*
