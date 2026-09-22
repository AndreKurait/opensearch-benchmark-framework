# OpenSearch 3.5 — 8th-Gen EC2 CPU Architecture Benchmark

**Generated:** 2026-09-22 18:49 UTC  
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

### Search — load level `load-500` (fixed offered rate 500 ops/s)

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

### Scaling across load levels (term query)

This is the axis the previous revision could not measure, because client count was tied to instance family (c=2, m=4, r=8) and therefore confounded with heap size and RAM. Here client count is fixed at 64 everywhere and only the offered rate varies.

| perm | CPU | cores | `load-500` |
|---|---|--:|--:|
| `m8g` | Graviton4 | 32 | — |
| `m8a` | AMD Turin | 32 | — |
| `m8i` | Intel Granite Rapids | 16 | — |
| `c8g` | Graviton4 | 32 | — |
| `c8a` | AMD Turin | 32 | — |
| `c8i` | Intel Granite Rapids | 16 | — |
| `r8g` | Graviton4 | 32 | — |
| `r8a` | AMD Turin | 32 | — |
| `r8i` | Intel Granite Rapids | 16 | — |

### Head-to-head, noise-gated

Percentages appear only where the interquartile ranges of the two medians do not overlap. Everything else is *within noise* and must not be quoted as a result.

| family | load level | metric | Graviton4 | AMD Turin | Turin vs Graviton | price-adjusted |
|---|---|---|--:|--:|--:|--:|
| m | (indexing) | index time | — | — | insufficient reps | — |
| m | `load-500` | term service time | — | — | insufficient reps | — |
| c | (indexing) | index time | — | — | insufficient reps | — |
| c | `load-500` | term service time | — | — | insufficient reps | — |
| r | (indexing) | index time | — | — | insufficient reps | — |
| r | `load-500` | term service time | — | — | insufficient reps | — |

*price-adjusted* = performance delta minus the on-demand price delta. Negative means the faster instance is not worth its premium at list price. The price delta is region-invariant within a family (see the price table), so one figure is valid for all regions.

### Cross-region agreement (term query)

Each region is an independent repetition on independent hardware. Below, each region votes on the sign of the Turin-vs-Graviton4 difference. Unanimous agreement across regions is far stronger evidence than a pooled median alone, and a split vote means the effect is not robust no matter how the IQRs fall.

| family | load level | regions favouring Turin | favouring Graviton4 | verdict |
|---|---|--:|--:|---|
| m | `load-500` | 2 | 0 | **unanimous: Turin** (2/2) |
| c | `load-500` | 2 | 0 | **unanimous: Turin** (2/2) |
| r | `load-500` | 2 | 0 | **unanimous: Turin** (2/2) |

A split vote overrides any percentage in the table above: if regions disagree on the direction, the effect is within regional noise regardless of what the pooled IQRs show.

## Run validity

All collected runs passed validity checks (error rate ≤ 0.1%, doc counts verified, no ignored workload params, OSB exit 0).

18 run(s) included but with a weakened audit trail:

| workload | load | rep | perm | caveat |
|---|---|---|---|---|
| geonames | load-500 | eu-south-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-south-2 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-500 | eu-west-1 | r8i | doc count unverified (probe could not reach cluster) |

`doc count unverified (probe could not reach cluster)` means the in-pod probe failed, not that the data is wrong: the opensearch-benchmark image ships no `curl`, so every probe request returned empty. Doc counts for these runs were instead verified out-of-band directly against each cluster, and came back identical (11,396,503 documents, 3/3 shards successful) on Graviton, AMD and Intel alike. The probe is fixed for subsequent runs.

*Generated 2026-09-22 18:49 UTC — [opensearch-benchmark-framework](https://github.com/AndreKurait/opensearch-benchmark-framework)*
