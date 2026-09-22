# OpenSearch 3.5 — 8th-Gen EC2 CPU Architecture Benchmark

**Generated:** 2026-09-22 19:45 UTC  
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
| `m8g` | Graviton4 | 32 | 1.509ms [1.484ms–1.587ms] | 1.720ms [1.709ms–1.801ms] | 1.451ms [1.445ms–1.513ms] | 367ms [356ms–379ms] | 700ms [676ms–744ms] |
| `m8a` | AMD Turin | 32 | 1.360ms [1.330ms–1.504ms] | 1.418ms [1.361ms–1.565ms] | 1.306ms [1.283ms–1.434ms] | 241ms [228ms–242ms] | 698ms [691ms–705ms] |
| `m8i` | Intel Granite Rapids | 16 | 2.009ms [1.928ms–2.217ms] | 2.057ms [2.010ms–2.225ms] | 1.962ms [1.885ms–2.124ms] | 442ms [436ms–446ms] | 695ms [675ms–729ms] |
| `c8g` | Graviton4 | 32 | 1.536ms [1.445ms–1.669ms] | 1.808ms [1.659ms–2.008ms] | 1.537ms [1.411ms–1.683ms] | 368ms [359ms–375ms] | 817ms [753ms–862ms] |
| `c8a` | AMD Turin | 32 | 1.198ms [1.149ms–1.199ms] | 1.291ms [1.272ms–1.314ms] | 1.247ms [1.238ms–1.265ms] | 241ms [237ms–248ms] | 864ms [860ms–866ms] |
| `c8i` | Intel Granite Rapids | 16 | 2.017ms [1.940ms–2.092ms] | 2.135ms [1.922ms–2.336ms] | 2.077ms [2.052ms–2.118ms] | 451ms [442ms–458ms] | 778ms [775ms–783ms] |
| `r8g` | Graviton4 | 32 | 1.432ms [1.426ms–1.450ms] | 1.688ms [1.626ms–1.753ms] | 1.442ms [1.411ms–1.456ms] | 380ms [376ms–386ms] | 812ms [800ms–825ms] |
| `r8a` | AMD Turin | 32 | 1.187ms [1.159ms–1.250ms] | 1.353ms [1.304ms–1.377ms] | 1.130ms [1.113ms–1.171ms] | 233ms [230ms–235ms] | 806ms [796ms–819ms] |
| `r8i` | Intel Granite Rapids | 16 | 1.724ms [1.689ms–1.894ms] | 2.209ms [2.190ms–2.234ms] | 1.990ms [1.924ms–2.038ms] | 452ms [436ms–461ms] | 706ms [659ms–753ms] |

Achieved vs offered throughput (a shortfall means the cell could not sustain the offered rate, which invalidates its service-time numbers):

| perm | CPU | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | 500 | 500 | 500 | **164** ⚠️ | 2,175 |
| `m8a` | AMD Turin | 500 | 500 | 500 | **245** ⚠️ | 2,168 |
| `m8i` | Intel Granite Rapids | 500 | 500 | 500 | **137** ⚠️ | 2,214 |
| `c8g` | Graviton4 | 500 | 500 | 500 | **166** ⚠️ | 1,879 |
| `c8a` | AMD Turin | 500 | 500 | 500 | **250** ⚠️ | 1,827 |
| `c8i` | Intel Granite Rapids | 500 | 500 | 500 | **136** ⚠️ | 1,786 |
| `r8g` | Graviton4 | 500 | 500 | 500 | **164** ⚠️ | 1,816 |
| `r8a` | AMD Turin | 500 | 500 | 500 | **255** ⚠️ | 2,038 |
| `r8i` | Intel Granite Rapids | 500 | 500 | 500 | **137** ⚠️ | 1,948 |

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

| family | load level | metric | Graviton4 | AMD Turin | Turin vs Graviton | price-adjusted |
|---|---|---|--:|--:|--:|--:|
| m | (indexing) | index time | — | — | insufficient reps | — |
| m | `load-2000` | term service time | — | — | insufficient reps | — |
| m | `load-500` | term service time | 1.509ms [1.484ms–1.587ms] | 1.360ms [1.330ms–1.504ms] | within noise | — |
| c | (indexing) | index time | — | — | insufficient reps | — |
| c | `load-2000` | term service time | — | — | insufficient reps | — |
| c | `load-500` | term service time | 1.536ms [1.445ms–1.669ms] | 1.198ms [1.149ms–1.199ms] | +22.0% | -13.6% |
| r | (indexing) | index time | — | — | insufficient reps | — |
| r | `load-2000` | term service time | — | — | insufficient reps | — |
| r | `load-500` | term service time | 1.432ms [1.426ms–1.450ms] | 1.187ms [1.159ms–1.250ms] | +17.1% | -18.5% |

*price-adjusted* = performance delta minus the on-demand price delta. Negative means the faster instance is not worth its premium at list price. The price delta is region-invariant within a family (see the price table), so one figure is valid for all regions.

### Cross-region agreement (term query)

Each region is an independent repetition on independent hardware. Below, each region votes on the sign of the Turin-vs-Graviton4 difference. Unanimous agreement across regions is far stronger evidence than a pooled median alone, and a split vote means the effect is not robust no matter how the IQRs fall.

| family | load level | regions favouring Turin | favouring Graviton4 | verdict |
|---|---|--:|--:|---|
| m | `load-2000` | 1 | 0 | **unanimous: Turin** (1/1) |
| m | `load-500` | 3 | 0 | **unanimous: Turin** (3/3) |
| c | `load-2000` | 1 | 0 | **unanimous: Turin** (1/1) |
| c | `load-500` | 3 | 0 | **unanimous: Turin** (3/3) |
| r | `load-2000` | 1 | 0 | **unanimous: Turin** (1/1) |
| r | `load-500` | 4 | 0 | **unanimous: Turin** (4/4) |

A split vote overrides any percentage in the table above: if regions disagree on the direction, the effect is within regional noise regardless of what the pooled IQRs show.

## Run validity

All collected runs passed validity checks (error rate ≤ 0.1%, doc counts verified, no ignored workload params, OSB exit 0).

43 run(s) included but with a weakened audit trail:

| workload | load | rep | perm | caveat |
|---|---|---|---|---|
| geonames | load-2000 | eu-south-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-central-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | us-west-2 | r8i | doc count unverified (probe could not reach cluster) |

`doc count unverified (probe could not reach cluster)` means the in-pod probe failed, not that the data is wrong: the opensearch-benchmark image ships no `curl`, so every probe request returned empty. Doc counts for these runs were instead verified out-of-band directly against each cluster, and came back identical (11,396,503 documents, 3/3 shards successful) on Graviton, AMD and Intel alike. The probe is fixed for subsequent runs.

*Generated 2026-09-22 19:45 UTC — [opensearch-benchmark-framework](https://github.com/AndreKurait/opensearch-benchmark-framework)*
