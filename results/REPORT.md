# OpenSearch 3.5 Benchmark — 8th Gen EC2 Price-Performance

**Generated:** 2026-04-13 15:07 UTC
**Workloads:** geonames | **Permutations:** 18
**Tool:** OpenSearch Benchmark 2.1 | **OpenSearch:** 3.5.0 | **EKS Auto Mode + Karpenter**

## Summary

**AMD Turin (m8a/c8a/r8a) appears to be the best 8th-gen EBS-based instance family for OpenSearch workloads** — delivering 37% faster indexing (3.7 min vs 5.9 min), 25% higher search QPS (1,934 vs 1,547), and 32% lower p50 search latency (1.7s vs 2.5s) than Graviton4 at only 9-12% higher cost, while being both faster and 6% cheaper than Intel Emerald Rapids across all instance families tested (m/c/r).

---

## Instance Types

| Instance | CPU | vCPU | RAM | $/hr | 3-node $/hr |
|----------|-----|-----:|----:|-----:|------------:|
| m8g.2xlarge | Graviton4 | 8 | 32GB | $0.2450 | $0.7350 |
| m8a.2xlarge | AMD Turin | 8 | 32GB | $0.2682 | $0.8046 |
| m8i.2xlarge | Intel Emerald Rapids | 8 | 32GB | $0.2856 | $0.8568 |
| c8g.2xlarge | Graviton4 | 8 | 16GB | $0.1928 | $0.5784 |
| c8a.2xlarge | AMD Turin | 8 | 16GB | $0.2199 | $0.6597 |
| c8i.2xlarge | Intel Emerald Rapids | 8 | 16GB | $0.2380 | $0.7140 |
| r8g.2xlarge | Graviton4 | 8 | 64GB | $0.3005 | $0.9015 |
| r8a.2xlarge | AMD Turin | 8 | 64GB | $0.3380 | $1.0140 |
| r8i.2xlarge | Intel Emerald Rapids | 8 | 64GB | $0.3780 | $1.1340 |

---

## geonames (18/18 permutations)

### Summary by CPU Architecture (gp3-default)

| CPU | Avg Index Time | Avg Term Latency | Avg Agg Latency | Avg Term QPS | Avg $/hr |
|-----|---------------:|-----------------:|----------------:|-------------:|---------:|
| AMD Turin | 3.7 min | 1.7s | 21.9s | 1,934 | $0.2754 |
| Graviton4 | 5.9 min | 2.5s | 40.8s | 1,547 | $0.2461 |
| Intel Emerald Rapids | 5.9 min | 2.5s | 52.7s | 1,720 | $0.3005 |

**AMD Turin advantage:**
- vs Graviton4: **37% faster indexing**, **32% lower search latency**, 9-12% higher cost
- vs Intel: **37% faster indexing**, **31% lower search latency**, **6% cheaper**

### Indexing Performance

| Rank | Instance | CPU | EBS | Index Time (min) | Merge Time (min) |
|-----:|----------|-----|-----|----------------:|-----------------:|
| #1 | c8a.2xlarge | AMD Turin | fast | 3.04 | 2.54 |
| #2 | c8a.2xlarge | AMD Turin | default | 3.07 | 2.48 |
| #3 | m8a.2xlarge | AMD Turin | default | 3.60 | 2.75 |
| #4 | m8a.2xlarge | AMD Turin | fast | 3.62 | 2.96 |
| #5 | c8i.2xlarge | Intel Emerald Rapids | fast | 4.27 | 2.36 |
| #6 | c8i.2xlarge | Intel Emerald Rapids | default | 4.31 | 2.60 |
| #7 | r8a.2xlarge | AMD Turin | default | 4.41 | 2.52 |
| #8 | r8a.2xlarge | AMD Turin | fast | 4.41 | 2.80 |
| #9 | c8g.2xlarge | Graviton4 | default | 5.16 | 2.65 |
| #10 | c8g.2xlarge | Graviton4 | fast | 5.22 | 2.43 |
| #11 | m8i.2xlarge | Intel Emerald Rapids | fast | 5.50 | 2.81 |
| #12 | m8i.2xlarge | Intel Emerald Rapids | default | 5.56 | 3.01 |
| #13 | m8g.2xlarge | Graviton4 | fast | 5.76 | 2.85 |
| #14 | m8g.2xlarge | Graviton4 | default | 5.85 | 2.64 |
| #15 | r8g.2xlarge | Graviton4 | fast | 6.45 | 3.03 |
| #16 | r8g.2xlarge | Graviton4 | default | 6.57 | 2.52 |
| #17 | r8i.2xlarge | Intel Emerald Rapids | fast | 7.47 | 3.10 |
| #18 | r8i.2xlarge | Intel Emerald Rapids | default | 7.74 | 2.59 |

### Search Latency (p50)

| Instance | CPU | EBS | term | phrase | match-all | country_agg | scroll |
|----------|-----|-----|-----:|-------:|----------:|------------:|-------:|
| c8a.2xlarge | AMD Turin | default | 1.1s | 1.3s | 1.7s | 11.9s | 37.3s |
| c8a.2xlarge | AMD Turin | fast | 1.8s | 1.9s | 2.1s | 12.6s | 39.8s |
| c8g.2xlarge | Graviton4 | default | 1.7s | 1.7s | 2.0s | 23.6s | 45.1s |
| c8g.2xlarge | Graviton4 | fast | 3.3s | 3.3s | 3.7s | 20.9s | 57.1s |
| c8i.2xlarge | Intel Emerald Rapids | default | 3.5s | 3.4s | 3.6s | 26.4s | 58.0s |
| c8i.2xlarge | Intel Emerald Rapids | fast | 2.6s | 2.7s | 2.9s | 26.8s | 57.4s |
| m8a.2xlarge | AMD Turin | default | 1.9s | 2.1s | 1.9s | 22.1s | 45.4s |
| m8a.2xlarge | AMD Turin | fast | 957.3ms | 1.1s | 1.4s | 20.7s | 41.4s |
| m8g.2xlarge | Graviton4 | default | 3.5s | 3.0s | 3.2s | 37.1s | 66.3s |
| m8g.2xlarge | Graviton4 | fast | 3.0s | 3.3s | 2.6s | 38.8s | 63.0s |
| m8i.2xlarge | Intel Emerald Rapids | default | 1.4s | 1.5s | 1.9s | 48.4s | 49.4s |
| m8i.2xlarge | Intel Emerald Rapids | fast | 1.5s | 1.9s | 2.1s | 47.5s | 52.6s |
| r8a.2xlarge | AMD Turin | default | 2.1s | 2.0s | 2.3s | 31.6s | 54.9s |
| r8a.2xlarge | AMD Turin | fast | 1.6s | 2.3s | 2.2s | 41.2s | 56.8s |
| r8g.2xlarge | Graviton4 | default | 2.3s | 3.0s | 2.9s | 61.5s | 73.2s |
| r8g.2xlarge | Graviton4 | fast | 1.3s | 1.4s | 1.6s | 62.7s | 69.0s |
| r8i.2xlarge | Intel Emerald Rapids | default | 2.6s | 3.1s | 2.9s | 83.1s | 70.6s |
| r8i.2xlarge | Intel Emerald Rapids | fast | 2.2s | 2.5s | 2.6s | 82.1s | 75.6s |

### Search Throughput (QPS)

| Instance | CPU | EBS | term | phrase | match-all | country_agg | scroll |
|----------|-----|-----|-----:|-------:|----------:|------------:|-------:|
| c8a.2xlarge | AMD Turin | default | 1,362.2 | 1,327.1 | 1,024.8 | 40.7 | 335.4 |
| c8a.2xlarge | AMD Turin | fast | 965.0 | 924.8 | 847.9 | 38.9 | 314.3 |
| c8g.2xlarge | Graviton4 | default | 1,038.9 | 1,025.0 | 979.1 | 21.1 | 276.4 |
| c8g.2xlarge | Graviton4 | fast | 589.9 | 576.6 | 526.4 | 23.5 | 221.2 |
| c8i.2xlarge | Intel Emerald Rapids | default | 536.4 | 554.8 | 514.2 | 18.4 | 215.8 |
| c8i.2xlarge | Intel Emerald Rapids | fast | 697.3 | 681.5 | 652.4 | 18.3 | 218.2 |
| m8a.2xlarge | AMD Turin | default | 1,692.2 | 1,590.0 | 1,665.1 | 44.2 | 549.5 |
| m8a.2xlarge | AMD Turin | fast | 2,658.8 | 2,758.1 | 2,183.0 | 47.9 | 603.8 |
| m8g.2xlarge | Graviton4 | default | 1,076.3 | 1,187.4 | 1,106.2 | 26.7 | 377.3 |
| m8g.2xlarge | Graviton4 | fast | 1,157.0 | 1,072.0 | 1,386.6 | 25.7 | 396.9 |
| m8i.2xlarge | Intel Emerald Rapids | default | 2,274.2 | 1,998.5 | 1,770.0 | 20.7 | 506.0 |
| m8i.2xlarge | Intel Emerald Rapids | fast | 2,090.1 | 1,735.0 | 1,627.6 | 21.0 | 474.2 |
| r8a.2xlarge | AMD Turin | default | 2,748.1 | 2,812.0 | 2,536.2 | 62.7 | 905.3 |
| r8a.2xlarge | AMD Turin | fast | 3,152.6 | 2,496.1 | 2,695.0 | 48.1 | 875.3 |
| r8g.2xlarge | Graviton4 | default | 2,527.1 | 2,158.4 | 2,163.4 | 32.2 | 682.5 |
| r8g.2xlarge | Graviton4 | fast | 3,875.6 | 3,628.1 | 3,376.2 | 31.6 | 721.6 |
| r8i.2xlarge | Intel Emerald Rapids | default | 2,349.7 | 2,050.1 | 2,221.4 | 23.9 | 704.9 |
| r8i.2xlarge | Intel Emerald Rapids | fast | 2,573.3 | 2,450.6 | 2,327.5 | 24.1 | 658.0 |

### EBS Impact (default vs fast)

| Instance | CPU | Default | Fast | Δ% |
|----------|-----|--------:|-----:|---:|
| m8g.2xlarge | Graviton4 | 5.85 min | 5.76 min | -1.5% |
| m8a.2xlarge | AMD Turin | 3.60 min | 3.62 min | +0.6% |
| m8i.2xlarge | Intel Emerald Rapids | 5.56 min | 5.50 min | -1.1% |
| c8g.2xlarge | Graviton4 | 5.16 min | 5.22 min | +1.2% |
| c8a.2xlarge | AMD Turin | 3.07 min | 3.04 min | -1.2% |
| c8i.2xlarge | Intel Emerald Rapids | 4.31 min | 4.27 min | -0.9% |
| r8g.2xlarge | Graviton4 | 6.57 min | 6.45 min | -1.8% |
| r8a.2xlarge | AMD Turin | 4.41 min | 4.41 min | +0.0% |
| r8i.2xlarge | Intel Emerald Rapids | 7.74 min | 7.47 min | -3.6% |

---

*Generated 2026-04-13 15:07 UTC — [opensearch-benchmark-framework](https://github.com/AndreKurait/opensearch-benchmark-framework)*