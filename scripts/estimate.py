#!/usr/bin/env python3
"""Estimate the cost and wall-clock time of the configured matrix.

Printed before any run so the spend is an explicit, reviewed decision rather
than a surprise on the bill.

Regions run CONCURRENTLY, one full repetition each, so wall clock is set by a
single region's pass over the load levels while cost is the sum across regions.
That is the whole point of the multi-region layout: repetitions are nearly free
in wall-clock terms, because the only thing that duplicates is provisioning
overhead, and that happens in parallel too.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "k8s" / "generated"

configs = {}
for p in sorted(GEN.glob("*/config.json")):
    c = json.loads(p.read_text())
    configs[c["region"]] = c
if not configs:
    raise SystemExit("No generated configs. Run: python3 scripts/generate.py")

specs_all = json.loads((ROOT / "specs.json").read_text())["regions"]

ref = configs[sorted(configs)[0]]
perms = ref["permutations"]
loads = list(ref["load_levels"])
workloads = list(ref["workloads"])
regions = sorted(configs)

# Minutes per cell: one full index + full query suite per permutation. All
# permutations in a cell run concurrently, so a cell costs one cell-duration.
MIN_PER_CELL = {"geonames": 35, "pmc": 12, "nyc_taxis": 150, "http_logs": 120}


def region_hourly(rg):
    c = configs[rg]
    det = c["perm_details"]
    sut = sum(det[pk]["usd_per_hour"] for pk in c["permutations"]) * 3
    lg_nodes = -(-len(c["permutations"]) // 4)  # 4 OSB pods per 32-vCPU node
    lg = specs_all[rg]["instances"][c["loadgen_type"]]["usd_per_hour"] * lg_nodes
    n_vol = len(c["permutations"]) * 3
    gib = n_vol * int(c["ebs"]["size"].rstrip("Gi"))
    # gp3: $0.08/GiB-mo + provisioned iops/throughput above the free tier
    ebs = gib * 0.08 / 730
    ebs += n_vol * max(0, c["ebs"]["iops"] - 3000) * 0.005 / 730
    ebs += n_vol * max(0, c["ebs"]["throughput"] - 125) * 0.040 / 730
    fixed = 0.10 + 0.045  # EKS control plane + 1 NAT gateway
    return {"sut": sut, "lg": lg, "ebs": ebs, "fixed": fixed,
            "total": sut + lg + ebs + fixed, "gib": gib, "lg_nodes": lg_nodes}


per = {rg: region_hourly(rg) for rg in regions}
total_hourly = sum(v["total"] for v in per.values())

# Wall clock = ONE region's pass, because regions run concurrently.
bench_minutes = sum(MIN_PER_CELL.get(w, 40) for w in workloads) * len(loads)
provision_minutes = 25   # EKS create + node boot, paid in parallel per region
teardown_minutes = 15
hours = (bench_minutes + provision_minutes + teardown_minutes) / 60

n_runs = len(perms) * len(loads) * len(workloads) * len(regions)

print(f"Matrix: {len(perms)} instance types x {len(loads)} load levels x "
      f"{len(workloads)} workload(s) x {len(regions)} regions (= repetitions)")
print(f"        = {n_runs} benchmark runs, {len(loads) * len(workloads)} "
      f"sequential cells per region, all regions concurrent")
print(f"Nodes:  {len(perms) * 3} SUT + {per[regions[0]]['lg_nodes']} loadgen "
      f"per region = {(len(perms) * 3 + per[regions[0]]['lg_nodes']) * len(regions)} total")
print()
print(f"  {'region':<16} {'AZ':<18} {'SUT':>8} {'loadgen':>8} {'EBS':>7} "
      f"{'fixed':>6} {'$/hr':>8}")
for rg in regions:
    v = per[rg]
    print(f"  {rg:<16} {configs[rg]['az']:<18} {v['sut']:>8.2f} {v['lg']:>8.2f} "
          f"{v['ebs']:>7.2f} {v['fixed']:>6.2f} {v['total']:>8.2f}")
print(f"  {'-' * 74}")
print(f"  {'TOTAL':<16} {'':<18} "
      f"{sum(v['sut'] for v in per.values()):>8.2f} "
      f"{sum(v['lg'] for v in per.values()):>8.2f} "
      f"{sum(v['ebs'] for v in per.values()):>7.2f} "
      f"{sum(v['fixed'] for v in per.values()):>6.2f} "
      f"{total_hourly:>8.2f}")
print()
print(f"Estimated wall clock: {hours:.1f} h  "
      f"({bench_minutes} min benchmarking + {provision_minutes} provisioning "
      f"+ {teardown_minutes} teardown)")
print(f"Estimated total cost: ${total_hourly * hours:,.0f}")
print()

# What the same work would cost run sequentially in one region, for comparison.
# Use the CHEAPEST region as the baseline -- anyone running sequentially would
# pick it, so this is the honest comparison rather than a flattering one.
seq_region = min(regions, key=lambda r: per[r]["total"])
seq_hourly = per[seq_region]["total"]
seq_hours = (bench_minutes * len(regions) + 45) / 60
print(f"For comparison, {len(regions)} repetitions SEQUENTIALLY in "
      f"{seq_region} (cheapest region) alone:")
print(f"  {seq_hours:.1f} h at ${seq_hourly:.2f}/hr = ${seq_hourly * seq_hours:,.0f}")
print(f"  Multi-region is {seq_hours / hours:.1f}x faster for "
      f"{total_hourly * hours / (seq_hourly * seq_hours):.2f}x the cost.")
print()
print("Regions run concurrently, so wall clock is set by ONE region's pass over")
print("the load levels. Adding repetitions costs money but almost no extra time.")
print()
print("vCPU headroom per region (all nine families share one Standard quota):")
for rg in regions:
    need = sum(configs[rg]["perm_details"][pk]["vcpus"]
               for pk in configs[rg]["permutations"]) * 3
    need += per[rg]["lg_nodes"] * 32
    q = configs[rg].get("vcpu_quota")
    mark = "" if q is None or need <= q else "  <-- OVER QUOTA"
    print(f"  {rg:<16} need {need:>5} of {q if q else '?':>6}{mark}")
