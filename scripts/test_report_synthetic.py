#!/usr/bin/env python3
"""Exercise report.py end-to-end on fabricated results before spending money.

A crash or a silent mis-aggregation in report.py is only discovered AFTER the
benchmark has been paid for, so the reporting path is tested against synthetic
data with a KNOWN answer. Three scenarios:

  unanimous  every region agrees Turin beats Graviton on term-query throughput
  split      regions disagree 4-3, so the cross-region vote must refuse to call it
  degraded   some runs carry error rates / doc-count mismatches and must be dropped

The test asserts on report.py's own conclusions, not just that it exits 0. Run:
    python3 scripts/test_report_synthetic.py
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN_DIR = ROOT / "k8s" / "generated"
RESULTS = ROOT / "results"

SEARCH_TASKS = ["term", "phrase", "match-all", "country_agg_uncached", "scroll"]


def write_run(dest, perm, thr_term, degrade=None):
    """Write one (region, perm) run: the CSV OSB emits plus our probe/log."""
    dest.mkdir(parents=True, exist_ok=True)
    err = 5.0 if degrade == "errors" else 0.0
    rows = [("Metric", "Task", "Value")]
    rows.append(("Mean Throughput", "index-append", f"{thr_term * 12:.2f}"))
    rows.append(("50th percentile service time", "index-append",
                 f"{60000 / thr_term:.2f}"))
    # Cluster-level metrics carry no task name. Indexing time moves INVERSELY to
    # throughput (faster host -> less time), so a report that mixed up the
    # direction of "lower is better" would flip sign here and nowhere else.
    rows.append(("Cumulative indexing time of primary shards", "",
                 f"{20000.0 / thr_term:.3f}"))
    rows.append(("Cumulative merge time of primary shards", "",
                 f"{6000.0 / thr_term:.3f}"))
    for t in SEARCH_TASKS:
        # Only 'term' carries the planted effect; the others are flat so a bug
        # that cross-wires tasks shows up as an implausible effect elsewhere.
        v = thr_term if t == "term" else 400.0
        rows.append(("Mean Throughput", t, f"{v:.2f}"))
        rows.append(("50th percentile service time", t, f"{1000 / v:.3f}"))
        rows.append(("50th percentile latency", t, f"{1500 / v:.3f}"))
        rows.append(("error rate", t, f"{err:.2f}"))
    (dest / f"{perm}.csv").write_text(
        "\n".join(",".join(r) for r in rows) + "\n")

    probe = ("DOCCOUNT_MISMATCH expected=11396505 actual=11000000"
             if degrade == "doccount" else "DOCCOUNT_OK 11396505")
    (dest / f"{perm}.probe").write_text(probe + "\n")
    (dest / f"{perm}.log").write_text("osb_exit_code=0\n")


def build(scenario, configs, turin_wins_in):
    """Fabricate a full results tree. Returns nothing; writes to results/."""
    rng = random.Random(1234)
    for region, cfg in configs.items():
        for wl in cfg["workloads"]:
            for lk in cfg["load_levels"]:
                dest = RESULTS / wl / lk / region
                for pk in cfg["permutations"]:
                    fam = pk.split("-")[0]
                    base = 1000.0
                    # Planted effect: Turin (m8a/c8a/r8a) vs Graviton (m8g/...).
                    if fam.endswith("a"):
                        base *= 1.20 if region in turin_wins_in else 0.85
                    # Region-level offset: real regions differ slightly. Well
                    # under the planted effect so it must not flip any sign.
                    # Indexed, not hash()ed -- hash() is salted per interpreter
                    # run, which would make this test irreproducible.
                    base *= 1.0 + sorted(configs).index(region) / 100.0
                    base *= 1.0 + rng.uniform(-0.01, 0.01)
                    degrade = None
                    if scenario == "degraded" and region == "us-east-1" \
                            and pk == cfg["permutations"][0]:
                        first_load = list(cfg["load_levels"])[0]
                        degrade = "errors" if lk == first_load else "doccount"
                    write_run(dest, pk, base, degrade)
                shutil.copy(GEN_DIR / region / "config.json",
                            dest / "cell.meta.json")


def run_report():
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "report.py")],
                       capture_output=True, text=True, cwd=ROOT)
    if p.returncode != 0:
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        raise SystemExit(f"report.py exited {p.returncode}")
    return (RESULTS / "REPORT.md").read_text()


def main():
    configs = {}
    for d in sorted(GEN_DIR.glob("*/config.json")):
        c = json.loads(d.read_text())
        configs[c["region"]] = c
    if len(configs) < 3:
        raise SystemExit(f"need >=3 generated regions, found {len(configs)}")
    regions = sorted(configs)

    backup = None
    if RESULTS.exists():
        backup = RESULTS.with_name("results.bak-test")
        if backup.exists():
            shutil.rmtree(backup)
        RESULTS.rename(backup)

    failures = []
    try:
        # ── 1. unanimous ────────────────────────────────────────────────────
        shutil.rmtree(RESULTS, ignore_errors=True)
        build("unanimous", configs, turin_wins_in=set(regions))
        md = run_report()
        Path("/tmp/report-unanimous.md").write_text(md)
        if "unanimous: Turin" not in md:
            failures.append("unanimous scenario: cross-region vote did not report "
                            "'unanimous: Turin'")
        if "insufficient reps" in md:
            failures.append("unanimous scenario: reported 'insufficient reps' "
                            f"despite {len(regions)} regions of data")

        # ── 2. split vote ──────────────────────────────────────────────────
        split_winners = set(regions[: (len(regions) + 1) // 2])
        shutil.rmtree(RESULTS, ignore_errors=True)
        build("split", configs, turin_wins_in=split_winners)
        md = run_report()
        Path("/tmp/report-split.md").write_text(md)
        if "not robust" not in md:
            failures.append("split scenario: a 4-3 disagreement was NOT flagged "
                            "'not robust' -- the report would over-claim")
        if "unanimous" in md.split("Cross-region agreement")[-1]:
            failures.append("split scenario: claimed unanimity on split data")

        # ── 3. degraded runs must be excluded ──────────────────────────────
        shutil.rmtree(RESULTS, ignore_errors=True)
        build("degraded", configs, turin_wins_in=set(regions))
        md = run_report()
        Path("/tmp/report-degraded.md").write_text(md)
        if "error rate" not in md and "doc count" not in md:
            failures.append("degraded scenario: bad runs were not reported as "
                            "excluded -- invalid data may be in the medians")
    finally:
        shutil.rmtree(RESULTS, ignore_errors=True)
        if backup is not None:
            backup.rename(RESULTS)

    if failures:
        print(f"FAILED {len(failures)} check(s):\n")
        for f in failures:
            print(f"  ✗ {f}")
        print("\nRendered reports kept at /tmp/report-{unanimous,split,degraded}.md")
        sys.exit(1)
    print(f"report.py validated on {len(regions)} synthetic regions: "
          f"unanimous vote detected, 4-3 split refused, degraded runs excluded.")
    print("Rendered reports at /tmp/report-{unanimous,split,degraded}.md")


if __name__ == "__main__":
    main()
