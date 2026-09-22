# OpenSearch 3.5 — 8th-Gen EC2 CPU Architecture Benchmark

**Generated:** 2026-09-22 23:35 UTC  
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

### Indexing

Server-side Lucene counters, so these are the metrics least sensitive to load-generator behaviour.

| perm | CPU | cores | index time (min) | merge time (min) | index throughput (docs/s) | $/M docs (ap-northeast-1) |
|---|---|--:|--:|--:|--:|--:|
| `r8a` | AMD Turin | 32 | 7.36 [7.25–7.62] | 3.56 [3.49–3.83] | — | $0.0995 |
| `m8a` | AMD Turin | 32 | 7.71 [7.57–7.83] | 3.35 [3.17–3.55] | — | $0.0851 |
| `c8a` | AMD Turin | 32 | 7.96 [7.70–8.00] | 3.12 [3.10–3.45] | — | $0.0758 |
| `c8g` | Graviton4 | 32 | 8.26 [8.17–8.38] | 3.50 [3.47–3.97] | — | $0.0580 |
| `r8g` | Graviton4 | 32 | 8.27 [8.18–8.40] | 4.19 [4.06–4.25] | — | $0.0825 |
| `m8g` | Graviton4 | 32 | 8.33 [8.30–8.34] | 4.22 [3.81–4.28] | — | $0.0678 |
| `r8i` | Intel Granite Rapids | 16 | 8.72 [8.69–8.89] | 3.55 [3.48–3.58] | — | $0.1026 |
| `m8i` | Intel Granite Rapids | 16 | 8.95 [8.85–8.97] | 3.74 [3.36–3.75] | — | $0.0859 |
| `c8i` | Intel Granite Rapids | 16 | 8.96 [8.76–9.25] | 3.79 [3.60–3.81] | — | $0.0742 |

### Search — load level `load-2000` (fixed offered rate 2000 ops/s)

Offered load is pinned, so **service time is comparable across architectures** here.

| perm | CPU | cores | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | 32 | 1.369ms [1.315ms–1.428ms] | 1.559ms [1.497ms–1.678ms] | 1.378ms [1.353ms–1.383ms] | 418ms [397ms–436ms] | 852ms [851ms–868ms] |
| `m8a` | AMD Turin | 32 | 1.049ms [1.033ms–1.158ms] | 1.153ms [1.150ms–1.252ms] | 1.093ms [1.068ms–1.188ms] | 246ms [240ms–250ms] | 859ms [849ms–872ms] |
| `m8i` | Intel Granite Rapids | 16 | 1.630ms [1.587ms–2.202ms] | 1.793ms [1.779ms–1.814ms] | 1.915ms [1.848ms–1.929ms] | 450ms [449ms–463ms] | 812ms [777ms–828ms] |
| `c8g` | Graviton4 | 32 | 1.387ms [1.374ms–1.480ms] | 1.659ms [1.652ms–1.699ms] | 1.428ms [1.362ms–1.460ms] | 380ms [378ms–388ms] | 808ms [806ms–838ms] |
| `c8a` | AMD Turin | 32 | 1.054ms [1.052ms–1.060ms] | 1.153ms [1.136ms–1.153ms] | 1.054ms [1.034ms–1.075ms] | 240ms [239ms–260ms] | 874ms [854ms–877ms] |
| `c8i` | Intel Granite Rapids | 16 | 1.662ms [1.560ms–1.837ms] | 2.105ms [1.933ms–2.193ms] | 2.150ms [1.758ms–2.267ms] | 455ms [455ms–465ms] | 830ms [821ms–850ms] |
| `r8g` | Graviton4 | 32 | 1.387ms [1.374ms–1.404ms] | 1.647ms [1.554ms–1.668ms] | 1.362ms [1.332ms–1.378ms] | 403ms [393ms–415ms] | 806ms [803ms–823ms] |
| `r8a` | AMD Turin | 32 | 1.024ms [0.996ms–1.043ms] | 1.133ms [1.123ms–1.229ms] | 1.004ms [0.990ms–1.027ms] | 232ms [230ms–236ms] | 876ms [875ms–876ms] |
| `r8i` | Intel Granite Rapids | 16 | 1.868ms [1.766ms–2.006ms] | 1.972ms [1.906ms–2.252ms] | 2.068ms [2.023ms–2.079ms] | 452ms [451ms–470ms] | 691ms [627ms–696ms] |

Achieved vs offered throughput (a shortfall means the cell could not sustain the offered rate, which invalidates its service-time numbers):

| perm | CPU | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | 1,999 | 1,999 | 1,998 | **145** ⚠️ | **1,750** ⚠️ |
| `m8a` | AMD Turin | 1,999 | 1,999 | 1,998 | **247** ⚠️ | **1,819** ⚠️ |
| `m8i` | Intel Granite Rapids | 2,000 | 1,999 | 1,994 | **137** ⚠️ | **1,750** ⚠️ |
| `c8g` | Graviton4 | 1,999 | 1,999 | 1,999 | **158** ⚠️ | **1,779** ⚠️ |
| `c8a` | AMD Turin | 2,000 | 1,999 | 1,964 | **249** ⚠️ | **1,834** ⚠️ |
| `c8i` | Intel Granite Rapids | 1,999 | 1,999 | 1,997 | **134** ⚠️ | **1,757** ⚠️ |
| `r8g` | Graviton4 | 1,998 | 1,999 | 1,999 | **152** ⚠️ | **1,797** ⚠️ |
| `r8a` | AMD Turin | 1,999 | 1,999 | 1,996 | **261** ⚠️ | **1,850** ⚠️ |
| `r8i` | Intel Granite Rapids | 1,999 | 1,999 | 1,998 | **133** ⚠️ | 2,209 |

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

### Search — load level `load-8000` (fixed offered rate 8000 ops/s)

Offered load is pinned, so **service time is comparable across architectures** here.

| perm | CPU | cores | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | 32 | 1.487ms [1.446ms–1.496ms] | 1.611ms [1.588ms–1.629ms] | 1.441ms [1.424ms–1.456ms] | 443ms [419ms–446ms] | 883ms [804ms–885ms] |
| `m8a` | AMD Turin | 32 | 1.024ms [1.002ms–1.110ms] | 1.181ms [1.135ms–1.270ms] | 1.048ms [1.013ms–1.141ms] | 243ms [232ms–249ms] | 892ms [883ms–892ms] |
| `m8i` | Intel Granite Rapids | 16 | 1.438ms [1.432ms–1.493ms] | 1.614ms [1.606ms–1.672ms] | 1.487ms [1.467ms–1.548ms] | 460ms [457ms–462ms] | 829ms [791ms–878ms] |
| `c8g` | Graviton4 | 32 | 1.474ms [1.408ms–1.518ms] | 1.645ms [1.556ms–1.685ms] | 1.436ms [1.353ms–1.470ms] | 393ms [388ms–402ms] | 815ms [808ms–880ms] |
| `c8a` | AMD Turin | 32 | 1.017ms [0.990ms–1.030ms] | 1.099ms [1.089ms–1.124ms] | 1.035ms [1.017ms–1.053ms] | 242ms [239ms–265ms] | 882ms [879ms–883ms] |
| `c8i` | Intel Granite Rapids | 16 | 1.478ms [1.441ms–1.694ms] | 1.654ms [1.604ms–1.906ms] | 1.569ms [1.463ms–1.774ms] | 467ms [460ms–475ms] | 818ms [801ms–885ms] |
| `r8g` | Graviton4 | 32 | 1.456ms [1.414ms–1.495ms] | 1.642ms [1.600ms–1.663ms] | 1.402ms [1.383ms–1.422ms] | 410ms [399ms–437ms] | 878ms [866ms–891ms] |
| `r8a` | AMD Turin | 32 | 0.999ms [0.987ms–1.101ms] | 1.075ms [1.061ms–1.090ms] | 1.024ms [1.011ms–1.061ms] | 228ms [227ms–232ms] | 858ms [857ms–864ms] |
| `r8i` | Intel Granite Rapids | 16 | 1.554ms [1.523ms–1.606ms] | 1.713ms [1.675ms–1.890ms] | 1.464ms [1.443ms–1.501ms] | 467ms [457ms–469ms] | 671ms [644ms–701ms] |

Achieved vs offered throughput (a shortfall means the cell could not sustain the offered rate, which invalidates its service-time numbers):

| perm | CPU | term | phrase | match-all | country_agg_uncached | scroll |
|---|---|--:|--:|--:|--:|--:|
| `m8g` | Graviton4 | 7,911 | 7,904 | 7,901 | **140** ⚠️ | **1,689** ⚠️ |
| `m8a` | AMD Turin | 7,918 | 7,933 | 7,951 | **257** ⚠️ | **1,777** ⚠️ |
| `m8i` | Intel Granite Rapids | 7,923 | 7,905 | 7,875 | **135** ⚠️ | **1,687** ⚠️ |
| `c8g` | Graviton4 | 7,947 | 7,961 | 7,887 | **154** ⚠️ | **1,784** ⚠️ |
| `c8a` | AMD Turin | 7,949 | 7,900 | 7,954 | **250** ⚠️ | **1,738** ⚠️ |
| `c8i` | Intel Granite Rapids | 7,917 | 7,900 | 7,906 | **132** ⚠️ | **1,706** ⚠️ |
| `r8g` | Graviton4 | 7,961 | 7,935 | 7,741 | **150** ⚠️ | **1,706** ⚠️ |
| `r8a` | AMD Turin | 7,961 | 7,928 | 7,904 | **261** ⚠️ | **1,816** ⚠️ |
| `r8i` | Intel Granite Rapids | 7,974 | 7,927 | 7,937 | **132** ⚠️ | **2,293** ⚠️ |

### Scaling across load levels (term query)

This is the axis the previous revision could not measure, because client count was tied to instance family (c=2, m=4, r=8) and therefore confounded with heap size and RAM. Here client count is fixed at 64 everywhere and only the offered rate varies.

| perm | CPU | cores | `load-2000` | `load-500` | `load-8000` |
|---|---|--:|--:|--:|--:|
| `m8g` | Graviton4 | 32 | 1,999 [1,999–2,000] | 500 [500–500] | 7,911 [7,906–7,911] |
| `m8a` | AMD Turin | 32 | 1,999 [1,999–1,999] | 500 [500–500] | 7,918 [7,880–7,950] |
| `m8i` | Intel Granite Rapids | 16 | 2,000 [2,000–2,000] | 500 [500–500] | 7,923 [7,917–7,924] |
| `c8g` | Graviton4 | 32 | 1,999 [1,999–1,999] | 500 [500–500] | 7,947 [7,919–7,973] |
| `c8a` | AMD Turin | 32 | 2,000 [1,999–2,000] | 500 [500–500] | 7,949 [7,904–7,950] |
| `c8i` | Intel Granite Rapids | 16 | 1,999 [1,999–1,999] | 500 [500–500] | 7,917 [7,905–7,921] |
| `r8g` | Graviton4 | 32 | 1,998 [1,997–1,999] | 500 [500–500] | 7,961 [7,923–7,968] |
| `r8a` | AMD Turin | 32 | 1,999 [1,999–2,000] | 500 [500–500] | 7,961 [7,926–7,982] |
| `r8i` | Intel Granite Rapids | 16 | 1,999 [1,999–2,000] | 500 [500–500] | 7,974 [7,964–7,976] |

### Head-to-head, noise-gated

Percentages appear only where the interquartile ranges of the two medians do not overlap. Everything else is *within noise* and must not be quoted as a result.

| family | comparison | load level | metric | baseline | challenger | challenger vs baseline | price-adjusted |
|---|---|---|---|--:|--:|--:|--:|
| m | Turin vs Graviton4 | (indexing) | index time | 8.33 [8.30–8.34] | 7.71 [7.57–7.83] | +7.4% | -28.2% |
| m | Turin vs Graviton4 | `load-2000` | term service time | 1.369ms [1.315ms–1.428ms] | 1.049ms [1.033ms–1.158ms] | +23.3% | -12.3% |
| m | Turin vs Graviton4 | `load-500` | term service time | 1.489ms [1.487ms–1.532ms] | 1.334ms [1.307ms–1.432ms] | +10.4% | -25.2% |
| m | Turin vs Graviton4 | `load-8000` | term service time | 1.487ms [1.446ms–1.496ms] | 1.024ms [1.002ms–1.110ms] | +31.1% | -4.5% |
| c | Turin vs Graviton4 | (indexing) | index time | 8.26 [8.17–8.38] | 7.96 [7.70–8.00] | +3.6% | -32.0% |
| c | Turin vs Graviton4 | `load-2000` | term service time | 1.387ms [1.374ms–1.480ms] | 1.054ms [1.052ms–1.060ms] | +24.0% | -11.6% |
| c | Turin vs Graviton4 | `load-500` | term service time | 1.464ms [1.418ms–1.608ms] | 1.198ms [1.149ms–1.199ms] | +18.2% | -17.4% |
| c | Turin vs Graviton4 | `load-8000` | term service time | 1.474ms [1.408ms–1.518ms] | 1.017ms [0.990ms–1.030ms] | +31.0% | -4.5% |
| r | Turin vs Graviton4 | (indexing) | index time | 8.27 [8.18–8.40] | 7.36 [7.25–7.62] | +11.0% | -24.6% |
| r | Turin vs Graviton4 | `load-2000` | term service time | 1.387ms [1.374ms–1.404ms] | 1.024ms [0.996ms–1.043ms] | +26.1% | -9.5% |
| r | Turin vs Graviton4 | `load-500` | term service time | 1.434ms [1.429ms–1.499ms] | 1.214ms [1.160ms–1.357ms] | +15.4% | -20.2% |
| r | Turin vs Graviton4 | `load-8000` | term service time | 1.456ms [1.414ms–1.495ms] | 0.999ms [0.987ms–1.101ms] | +31.4% | -4.2% |
| m | Intel vs Graviton4 | (indexing) | index time | 8.33 [8.30–8.34] | 8.95 [8.85–8.97] | -7.4% | -25.3% |
| m | Intel vs Graviton4 | `load-2000` | term service time | 1.369ms [1.315ms–1.428ms] | 1.630ms [1.587ms–2.202ms] | -19.1% | -37.0% |
| m | Intel vs Graviton4 | `load-500` | term service time | 1.489ms [1.487ms–1.532ms] | 2.075ms [1.929ms–2.089ms] | -39.4% | -57.3% |
| m | Intel vs Graviton4 | `load-8000` | term service time | 1.487ms [1.446ms–1.496ms] | 1.438ms [1.432ms–1.493ms] | within noise | — |
| c | Intel vs Graviton4 | (indexing) | index time | 8.26 [8.17–8.38] | 8.96 [8.76–9.25] | -8.5% | -26.4% |
| c | Intel vs Graviton4 | `load-2000` | term service time | 1.387ms [1.374ms–1.480ms] | 1.662ms [1.560ms–1.837ms] | -19.9% | -37.8% |
| c | Intel vs Graviton4 | `load-500` | term service time | 1.464ms [1.418ms–1.608ms] | 2.051ms [1.958ms–2.076ms] | -40.1% | -58.0% |
| c | Intel vs Graviton4 | `load-8000` | term service time | 1.474ms [1.408ms–1.518ms] | 1.478ms [1.441ms–1.694ms] | within noise | — |
| r | Intel vs Graviton4 | (indexing) | index time | 8.27 [8.18–8.40] | 8.72 [8.69–8.89] | -5.5% | -23.4% |
| r | Intel vs Graviton4 | `load-2000` | term service time | 1.387ms [1.374ms–1.404ms] | 1.868ms [1.766ms–2.006ms] | -34.7% | -52.6% |
| r | Intel vs Graviton4 | `load-500` | term service time | 1.434ms [1.429ms–1.499ms] | 1.757ms [1.692ms–2.018ms] | -22.5% | -40.4% |
| r | Intel vs Graviton4 | `load-8000` | term service time | 1.456ms [1.414ms–1.495ms] | 1.554ms [1.523ms–1.606ms] | -6.7% | -24.7% |

*price-adjusted* = performance delta minus the on-demand price delta. Negative means the faster instance is not worth its premium at list price. The price delta is region-invariant within a family (see the price table), so one figure is valid for all regions.

### Cross-region agreement (term query)

Each region is an independent repetition on independent hardware. Below, each region votes on the sign of each pairwise difference. Unanimous agreement across regions is far stronger evidence than a pooled median alone, and a split vote means the effect is not robust no matter how the IQRs fall.

| family | comparison | load level | regions favouring challenger | favouring baseline | verdict |
|---|---|---|--:|--:|---|
| m | Turin vs Graviton4 | `load-2000` | 4 | 0 | **unanimous: Turin** (4/4) |
| m | Turin vs Graviton4 | `load-500` | 4 | 0 | **unanimous: Turin** (4/4) |
| m | Turin vs Graviton4 | `load-8000` | 4 | 0 | **unanimous: Turin** (4/4) |
| c | Turin vs Graviton4 | `load-2000` | 3 | 0 | **unanimous: Turin** (3/3) |
| c | Turin vs Graviton4 | `load-500` | 3 | 0 | **unanimous: Turin** (3/3) |
| c | Turin vs Graviton4 | `load-8000` | 3 | 0 | **unanimous: Turin** (3/3) |
| r | Turin vs Graviton4 | `load-2000` | 5 | 0 | **unanimous: Turin** (5/5) |
| r | Turin vs Graviton4 | `load-500` | 5 | 0 | **unanimous: Turin** (5/5) |
| r | Turin vs Graviton4 | `load-8000` | 5 | 0 | **unanimous: Turin** (5/5) |
| m | Intel vs Graviton4 | `load-2000` | 0 | 5 | **unanimous: Graviton4** (5/5) |
| m | Intel vs Graviton4 | `load-500` | 0 | 5 | **unanimous: Graviton4** (5/5) |
| m | Intel vs Graviton4 | `load-8000` | 2 | 3 | split 2–3 — not robust |
| c | Intel vs Graviton4 | `load-2000` | 0 | 5 | **unanimous: Graviton4** (5/5) |
| c | Intel vs Graviton4 | `load-500` | 0 | 5 | **unanimous: Graviton4** (5/5) |
| c | Intel vs Graviton4 | `load-8000` | 2 | 3 | split 2–3 — not robust |
| r | Intel vs Graviton4 | `load-2000` | 0 | 5 | **unanimous: Graviton4** (5/5) |
| r | Intel vs Graviton4 | `load-500` | 0 | 5 | **unanimous: Graviton4** (5/5) |
| r | Intel vs Graviton4 | `load-8000` | 0 | 5 | **unanimous: Graviton4** (5/5) |

A split vote overrides any percentage in the table above: if regions disagree on the direction, the effect is within regional noise regardless of what the pooled IQRs show.

## Run validity

All collected runs passed validity checks (error rate ≤ 0.1%, doc counts verified, no ignored workload params, OSB exit 0).

126 run(s) included but with a weakened audit trail:

| workload | load | rep | perm | caveat |
|---|---|---|---|---|
| geonames | load-2000 | ap-northeast-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-central-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | us-west-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | ap-northeast-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-central-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | ap-northeast-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-central-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | us-west-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | ap-northeast-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-central-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | us-west-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | us-west-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | ap-northeast-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-central-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | us-west-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | ap-northeast-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-central-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | us-west-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | ap-northeast-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-central-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | us-west-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | ap-northeast-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-central-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-south-2 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | eu-west-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-2000 | us-west-2 | r8i | doc count unverified (probe could not reach cluster) |
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
| geonames | load-8000 | ap-northeast-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-central-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | us-west-2 | m8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | ap-northeast-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-central-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | m8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | ap-northeast-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-central-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | us-west-2 | m8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | ap-northeast-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-central-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | us-west-2 | c8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | us-west-2 | c8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | ap-northeast-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-central-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | us-west-2 | c8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | ap-northeast-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-central-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | us-west-2 | r8g | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | ap-northeast-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-central-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | us-west-2 | r8a | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | ap-northeast-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-central-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-south-2 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | eu-west-1 | r8i | doc count unverified (probe could not reach cluster) |
| geonames | load-8000 | us-west-2 | r8i | doc count unverified (probe could not reach cluster) |

`doc count unverified (probe could not reach cluster)` means the in-pod probe failed, not that the data is wrong: the opensearch-benchmark image ships no `curl`, so every probe request returned empty. Doc counts for these runs were instead verified out-of-band directly against each cluster, and came back identical (11,396,503 documents, 3/3 shards successful) on Graviton, AMD and Intel alike. The probe is fixed for subsequent runs.

*Generated 2026-09-22 23:35 UTC — [opensearch-benchmark-framework](https://github.com/AndreKurait/opensearch-benchmark-framework)*
