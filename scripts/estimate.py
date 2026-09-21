#!/usr/bin/env python3
"""Estimate the cost and wall-clock time of the configured matrix.

Printed before any run so the spend is an explicit, reviewed decision rather
than a surprise on the bill.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
config = json.loads((ROOT / "k8s" / "generated" / "config.json").read_text())
specs = json.loads((ROOT / "specs.json").read_text())["instances"]

perms = config["permutations"]
det = config["perm_details"]
reps = config["reps"]
loads = list(config["load_levels"])
workloads = list(config["workloads"])

# Minutes per cell: one full index + full query suite per permutation. All
# permutations in a cell run concurrently, so a cell costs one cell-duration.
MIN_PER_CELL = {"geonames": 35, "pmc": 12, "nyc_taxis": 150, "http_logs": 120}

sut_hourly = sum(det[pk]["usd_per_hour"] for pk in perms) * 3
lg_nodes = -(-len(perms) // 4)  # 4 OSB pods per 32-vCPU loadgen node
lg_hourly = specs[config["loadgen_type"]]["usd_per_hour"] * lg_nodes
ebs_gib = len(perms) * 3 * int(config["ebs"]["size"].rstrip("Gi"))
# gp3: $0.08/GiB-mo + provisioned iops/throughput above the free tier
ebs_hourly = (ebs_gib * 0.08 / 730)
ebs_hourly += len(perms) * 3 * max(0, config["ebs"]["iops"] - 3000) * 0.005 / 730
ebs_hourly += len(perms) * 3 * max(0, config["ebs"]["throughput"] - 125) * 0.040 / 730
fixed_hourly = 0.10 + 0.045 * 1  # EKS control plane + 1 NAT gateway

total_hourly = sut_hourly + lg_hourly + ebs_hourly + fixed_hourly

bench_minutes = sum(MIN_PER_CELL.get(w, 40) for w in workloads) * len(loads) * reps
provision_minutes = 45
hours = (bench_minutes + provision_minutes) / 60

print(f"Matrix: {len(perms)} instance types x {len(loads)} load levels x {reps} reps "
      f"x {len(workloads)} workload(s)")
print(f"        = {len(perms) * len(loads) * reps * len(workloads)} benchmark runs, "
      f"{len(loads) * reps * len(workloads)} sequential cells")
print(f"Nodes:  {len(perms) * 3} SUT ({config['size']}) + {lg_nodes} loadgen "
      f"({config['loadgen_type']})")
print()
print(f"  SUT compute        ${sut_hourly:8.2f}/hr")
print(f"  loadgen compute    ${lg_hourly:8.2f}/hr")
print(f"  EBS ({ebs_gib} GiB)    ${ebs_hourly:8.2f}/hr")
print(f"  EKS + NAT          ${fixed_hourly:8.2f}/hr")
print(f"  {'-' * 30}")
print(f"  TOTAL              ${total_hourly:8.2f}/hr")
print()
print(f"Estimated wall clock: {hours:.1f} h "
      f"({bench_minutes} min benchmarking + {provision_minutes} min provisioning)")
print(f"Estimated total cost: ${total_hourly * hours:,.0f}")
print()
print("Note: cells run sequentially (all instance types in parallel within a cell),")
print("so wall clock scales with load levels x reps, not with instance count.")
