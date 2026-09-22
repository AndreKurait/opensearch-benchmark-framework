# OpenSearch 3.5 — 8th-Gen EC2 CPU Architecture Benchmark

**Generated:** 2026-09-21 22:11 UTC  
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

_No results collected yet._
