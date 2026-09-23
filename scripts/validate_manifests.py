#!/usr/bin/env python3
"""Assert the invariants that make this benchmark a controlled experiment.

Run by CI after generate.py. Each check corresponds to a documented failure in
docs/METHODOLOGY.md -- if one of these regresses, the resulting numbers are not
comparable across architectures, so CI fails rather than letting a plausible
looking report get published.

Every generated region is checked independently, and then a final pass asserts
the regions are identical to each other in everything except region/AZ/price.
That cross-region check is what makes "region == repetition" legitimate: if two
regions differ in heap size or client count, their results are not poolable and
the aggregate IQR would be measuring our own configuration drift.
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GEN_ROOT = ROOT / "k8s" / "generated"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


def load_all(path):
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


def validate_region(GEN, specs_all):
    """Run every per-region invariant. Returns a fingerprint for cross-region
    comparison: the things that MUST be identical between repetitions."""
    rg = GEN.name
    config = json.loads((GEN / "config.json").read_text())
    perms = config["permutations"]
    det = config["perm_details"]

    # ── 1. Load generator must be isolated from the system under test ──────
    pools = {p["metadata"]["name"]: p for p in load_all(GEN / "nodepools.yaml")}
    check("loadgen" in pools,
          f"{rg}: no 'loadgen' NodePool: load generator would land on the SUT")
    if "loadgen" in pools:
        taints = pools["loadgen"]["spec"]["template"]["spec"].get("taints", [])
        check(
            any(t.get("key") == "bench/loadgen" and t.get("effect") == "NoSchedule"
                for t in taints),
            f"{rg}: loadgen NodePool is not tainted NoSchedule: OpenSearch pods "
            f"could be scheduled onto the load generator",
        )

    # Every pool must be pinned to the single benchmark AZ. A pool that is free
    # to land anywhere puts some SUTs one network hop from the loadgen and
    # others two, which shows up as a throughput difference we would misread as
    # an architecture difference.
    az = config["az"]
    for name, pool in pools.items():
        reqs = pool["spec"]["template"]["spec"]["requirements"]
        zones = [r for r in reqs if r["key"] == "topology.kubernetes.io/zone"]
        check(
            len(zones) == 1 and zones[0]["values"] == [az],
            f"{rg}: NodePool {name} is not pinned to {az} (zone requirement "
            f"{zones}); cross-AZ placement confounds the comparison",
        )

    for job_file in sorted((GEN / "jobs").glob("*.yaml")):
        for job in load_all(job_file):
            spec = job["spec"]["template"]["spec"]
            sel = spec.get("nodeSelector", {})
            check(
                sel.get("bench/role") == "loadgen",
                f"{rg}/{job_file.name}/{job['metadata']['name']}: OSB job is not "
                f"pinned to the loadgen pool (nodeSelector={sel})",
            )
            check(
                "bench/perm" not in sel,
                f"{rg}/{job_file.name}/{job['metadata']['name']}: OSB job is "
                f"pinned to a SUT node -- this is the co-located load generator bug",
            )
            check(
                job["spec"].get("backoffLimit") == 0,
                f"{rg}/{job_file.name}/{job['metadata']['name']}: backoffLimit "
                f"!= 0; a retry silently overwrites its own failed result",
            )

    # ── 2. Everything except the instance must be identical across perms ────
    values = {pk: yaml.safe_load(
        (GEN / "opensearch" / f"values-{pk}.yaml").read_text()) for pk in perms}

    IDENTICAL = [
        ("opensearchJavaOpts", lambda v: v["opensearchJavaOpts"]),
        ("cpu request", lambda v: v["resources"]["requests"]["cpu"]),
        ("memory request", lambda v: v["resources"]["requests"]["memory"]),
        ("replicas", lambda v: v["replicas"]),
        ("antiAffinity", lambda v: v["antiAffinity"]),
        ("storageClass", lambda v: v["persistence"]["storageClass"]),
        ("volume size", lambda v: v["persistence"]["size"]),
    ]
    for field, getter in IDENTICAL:
        seen = {getter(v) for v in values.values()}
        check(
            len(seen) == 1,
            f"{rg}: {field} differs across permutations ({seen}); it must be "
            f"identical or the comparison is confounded",
        )

    for pk, v in values.items():
        check(
            v["antiAffinity"] == "hard",
            f"{rg}/{pk}: antiAffinity is {v['antiAffinity']!r}, must be 'hard' "
            f"or two data pods can share a node",
        )
        check(
            "limits" not in v.get("resources", {})
            or "memory" not in v["resources"].get("limits", {}),
            f"{rg}/{pk}: a memory limit throttles page cache, which is the "
            f"legitimate difference between the c/m/r families",
        )
        check(
            v.get("masterService") == f"{pk}-master",
            f"{rg}/{pk}: masterService={v.get('masterService')!r} does not match "
            f"the chart-derived name {pk}-master",
        )

    # ── 3. Client counts and load levels must be family-independent ─────────
    offered = {}
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
            f"{rg}/{job_file.name}: client count / offered load varies across "
            f"instance types within one cell ({clients}); concurrency would be "
            f"confounded with instance family",
        )
        if clients:
            offered[job_file.name] = sorted(clients)[0]

    # ── 4. OSB target must resolve to the service the chart creates ─────────
    for job_file in sorted((GEN / "jobs").glob("*.yaml")):
        for job in load_all(job_file):
            pk = job["metadata"]["labels"]["perm"]
            args = job["spec"]["template"]["spec"]["containers"][0]["args"][0]
            check(
                f"{pk}-master.os-{pk}.svc.cluster.local" in args,
                f"{rg}/{job_file.name}/{pk}: OSB target host does not match the "
                f"chart-created service {pk}-master.os-{pk}",
            )
            check(
                "opensearch-cluster-master" not in args,
                f"{rg}/{job_file.name}/{pk}: still references the default chart "
                f"service name, which this config does not create",
            )

    # ── 5. Prices must resolve, per region ─────────────────────────────────
    for pk in perms:
        check(
            det[pk]["usd_per_hour"] > 0,
            f"{rg}/{pk}: no price resolved from specs.json",
        )

    # ── 6. Warn on burstable-EBS sizes ─────────────────────────────────────
    specs = specs_all[rg]["instances"]
    for pk in perms:
        it = det[pk]["instance_type"]
        s = specs[it]
        if s["ebs_baseline_mbps"] < s["ebs_max_mbps"]:
            print(f"  NOTE {rg}/{it}: burstable EBS "
                  f"({s['ebs_baseline_mbps']} baseline / {s['ebs_max_mbps']} max)"
                  f" -- acceptable only for smoke tests, not published results")

    n_jobs = sum(len(load_all(f)) for f in (GEN / "jobs").glob("*.yaml"))
    ref = next(iter(values.values()))
    return {
        "permutations": tuple(perms),
        "instance_types": tuple(det[pk]["instance_type"] for pk in perms),
        "load_levels": tuple(config["load_levels"]),
        "workloads": tuple(config["workloads"]),
        "ebs": json.dumps(config["ebs"], sort_keys=True),
        "heap": ref["opensearchJavaOpts"],
        "cpu": ref["resources"]["requests"]["cpu"],
        "memory": ref["resources"]["requests"]["memory"],
        "replicas": ref["replicas"],
        "offered_load": json.dumps(offered, sort_keys=True),
        "n_jobs": n_jobs,
    }


# ── no hardcoded prices anywhere in generate.py (region-independent) ────────
gen_src = (ROOT / "scripts" / "generate.py").read_text()
hardcoded = re.findall(
    r'["\'](?:price|usd_per_hour|cost)["\']\s*:\s*[0-9]+\.?[0-9]*', gen_src
)
check(
    not hardcoded,
    f"generate.py hardcodes prices {hardcoded}; they must come from specs.json",
)

specs_all = json.loads((ROOT / "specs.json").read_text())["regions"]

region_dirs = sorted(p.parent for p in GEN_ROOT.glob("*/config.json"))
if not region_dirs:
    raise SystemExit("No generated regions under k8s/generated/. "
                     "Run: BENCH_REGION=<rg> python3 scripts/generate.py")

prints = {d.name: validate_region(d, specs_all) for d in region_dirs}

# ── cross-region: repetitions must be identical experiments ────────────────
if len(prints) > 1:
    keys = next(iter(prints.values())).keys()
    for k in keys:
        seen = {rg: fp[k] for rg, fp in prints.items()}
        if len(set(seen.values())) > 1:
            failures.append(
                f"{k} differs across regions ({seen}); regions are used as "
                f"repetitions, so a difference here means the results are not "
                f"poolable and any aggregate error bar is meaningless"
            )

if failures:
    print(f"\nFAILED {len(failures)} invariant check(s):\n")
    for f in failures:
        print(f"  ✗ {f}")
    sys.exit(1)

fp = next(iter(prints.values()))
print(f"All invariants hold across {len(prints)} region(s) "
      f"({', '.join(prints)}): {len(fp['permutations'])} permutations, "
      f"{fp['n_jobs']} jobs each, loadgen isolated, all nodes AZ-pinned, "
      f"config identical across permutations and across regions.")
