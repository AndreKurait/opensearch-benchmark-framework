#!/usr/bin/env python3
"""Assert the invariants that make this benchmark a controlled experiment.

Run by CI after generate.py. Each check corresponds to a documented failure in
docs/METHODOLOGY.md -- if one of these regresses, the resulting numbers are not
comparable across architectures, so CI fails rather than letting a plausible
looking report get published.
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "k8s" / "generated"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


def load_all(path):
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


config = json.loads((GEN / "config.json").read_text())
perms = config["permutations"]
det = config["perm_details"]

# ── 1. Load generator must be isolated from the system under test ──────────
pools = {p["metadata"]["name"]: p for p in load_all(GEN / "nodepools.yaml")}
check("loadgen" in pools, "no 'loadgen' NodePool: load generator would land on the SUT")
if "loadgen" in pools:
    taints = pools["loadgen"]["spec"]["template"]["spec"].get("taints", [])
    check(
        any(t.get("key") == "bench/loadgen" and t.get("effect") == "NoSchedule"
            for t in taints),
        "loadgen NodePool is not tainted NoSchedule: OpenSearch pods could be "
        "scheduled onto the load generator",
    )

for job_file in sorted((GEN / "jobs").glob("*.yaml")):
    for job in load_all(job_file):
        spec = job["spec"]["template"]["spec"]
        sel = spec.get("nodeSelector", {})
        check(
            sel.get("bench/role") == "loadgen",
            f"{job_file.name}/{job['metadata']['name']}: OSB job is not pinned to "
            f"the loadgen pool (nodeSelector={sel})",
        )
        check(
            "bench/perm" not in sel,
            f"{job_file.name}/{job['metadata']['name']}: OSB job is pinned to a SUT "
            f"node -- this is the co-located load generator bug",
        )
        check(
            job["spec"].get("backoffLimit") == 0,
            f"{job_file.name}/{job['metadata']['name']}: backoffLimit != 0; a retry "
            f"silently overwrites its own failed result",
        )

# ── 2. Everything except the instance must be identical across permutations ─
values = {pk: yaml.safe_load((GEN / "opensearch" / f"values-{pk}.yaml").read_text())
          for pk in perms}

for field, getter in [
    ("opensearchJavaOpts", lambda v: v["opensearchJavaOpts"]),
    ("cpu request", lambda v: v["resources"]["requests"]["cpu"]),
    ("memory request", lambda v: v["resources"]["requests"]["memory"]),
    ("replicas", lambda v: v["replicas"]),
    ("antiAffinity", lambda v: v["antiAffinity"]),
    ("storageClass", lambda v: v["persistence"]["storageClass"]),
    ("volume size", lambda v: v["persistence"]["size"]),
]:
    seen = {getter(v) for v in values.values()}
    check(
        len(seen) == 1,
        f"{field} differs across permutations ({seen}); it must be identical or "
        f"the comparison is confounded",
    )

for pk, v in values.items():
    check(
        v["antiAffinity"] == "hard",
        f"{pk}: antiAffinity is {v['antiAffinity']!r}, must be 'hard' or two data "
        f"pods can share a node",
    )
    check(
        "limits" not in v.get("resources", {})
        or "memory" not in v["resources"].get("limits", {}),
        f"{pk}: a memory limit throttles page cache, which is the legitimate "
        f"difference between the c/m/r families",
    )
    # Service name must match what the chart actually creates.
    check(
        v.get("masterService") == f"{pk}-master",
        f"{pk}: masterService={v.get('masterService')!r} does not match the "
        f"chart-derived name {pk}-master",
    )

# ── 3. Client counts and load levels must be family-independent ────────────
for job_file in sorted((GEN / "jobs").glob("*.yaml")):
    clients = set()
    for job in load_all(job_file):
        args = job["spec"]["template"]["spec"]["containers"][0]["args"][0]
        for token in args.split():
            if token.startswith("--workload-params="):
                params = dict(
                    kv.split(":", 1)
                    for kv in token.split("=", 1)[1].strip("'").split(",")
                )
                clients.add((params.get("search_clients"),
                             params.get("bulk_indexing_clients"),
                             params.get("target_throughput")))
    check(
        len(clients) <= 1,
        f"{job_file.name}: client count / offered load varies across instance "
        f"types within one cell ({clients}); concurrency would be confounded "
        f"with instance family",
    )

# ── 4. OSB target must resolve to the service the chart creates ─────────────
for job_file in sorted((GEN / "jobs").glob("*.yaml")):
    for job in load_all(job_file):
        pk = job["metadata"]["labels"]["perm"]
        args = job["spec"]["template"]["spec"]["containers"][0]["args"][0]
        check(
            f"{pk}-master.os-{pk}.svc.cluster.local" in args,
            f"{job_file.name}/{pk}: OSB target host does not match the "
            f"chart-created service {pk}-master.os-{pk}",
        )
        check(
            "opensearch-cluster-master" not in args,
            f"{job_file.name}/{pk}: still references the default chart service "
            f"name, which this config does not create",
        )

# ── 5. No hardcoded prices outside specs.json ──────────────────────────────
gen_src = (ROOT / "scripts" / "generate.py").read_text()
# Look for a price key assigned a NUMERIC LITERAL, e.g. `"price": 0.2450`.
# Assignments that read through from specs.json are fine and expected.
hardcoded = re.findall(
    r'["\'](?:price|usd_per_hour|cost)["\']\s*:\s*[0-9]+\.?[0-9]*', gen_src
)
check(
    not hardcoded,
    f"generate.py hardcodes prices {hardcoded}; they must come from specs.json",
)
for pk in perms:
    check(
        det[pk]["usd_per_hour"] > 0,
        f"{pk}: no price resolved from specs.json",
    )

# ── 6. Size must not be a burstable-EBS size unless explicitly acknowledged ─
specs = json.loads((ROOT / "specs.json").read_text())["instances"]
for pk in perms:
    it = det[pk]["instance_type"]
    s = specs[it]
    if s["ebs_baseline_mbps"] < s["ebs_max_mbps"]:
        print(f"  NOTE {it}: burstable EBS "
              f"({s['ebs_baseline_mbps']} baseline / {s['ebs_max_mbps']} max) -- "
              f"acceptable only for smoke tests, not published results")

# ── report ─────────────────────────────────────────────────────────────────
n_jobs = sum(len(load_all(f)) for f in (GEN / "jobs").glob("*.yaml"))
if failures:
    print(f"\nFAILED {len(failures)} invariant check(s):\n")
    for f in failures:
        print(f"  ✗ {f}")
    sys.exit(1)

print(f"All invariants hold: {len(perms)} permutations, {n_jobs} jobs, "
      f"loadgen isolated, config identical across permutations.")
