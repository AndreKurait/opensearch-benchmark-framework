#!/usr/bin/env python3
"""Generate REPORT.md from OSB results across repetitions and load levels.

Statistical rules enforced here (an earlier revision of this repo reported
single-run differences of 25-37% as findings when its own run-to-run variance
was around +/-100%):

 * Every number is a MEDIAN over >= MIN_REPS repetitions, printed with its
   interquartile range.
 * A comparative claim is only emitted when the two IQRs DO NOT OVERLAP.
   Otherwise the comparison prints "within noise".
 * Throughput uses OSB's "Mean Throughput", never "Max Throughput" (a single
   peak sampling interval, i.e. the noisiest statistic available).
 * Latency is only compared at FIXED-RATE load levels, where offered load is
   pinned. At the saturate level, latency is queue-dominated and is suppressed.
 * Runs whose error rate exceeds MAX_ERROR_RATE, or whose post-index doc count
   did not match, are marked INVALID and excluded from medians.
 * Price-performance is computed from specs.json, never from prose.
"""
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "k8s" / "generated" / "config.json"
RESULTS_DIR = ROOT / "results"

MIN_REPS = 3
MAX_ERROR_RATE = 0.1  # percent

CPU_ORDER = ["Graviton4", "AMD Turin", "Intel Granite Rapids"]

SEARCH_TASKS = ["term", "phrase", "match-all", "country_agg_uncached", "scroll"]


# ── parsing ───────────────────────────────────────────────────────────────


def parse_csv(path):
    m = {}
    if not path.exists():
        return m
    for row in csv.reader(path.open()):
        if len(row) < 3 or row[0].strip() in ("Metric", ""):
            continue
        try:
            m[(row[0].strip(), row[1].strip())] = float(row[2].strip())
        except ValueError:
            pass
    return m


def g(m, metric, task=""):
    v = m.get((metric, task))
    return v if v is not None and v > 0 else None


def service_time(m, task):
    """Prefer service time (excludes client-side queue wait) and never silently
    mix it with latency -- they are different quantities."""
    return g(m, "50th percentile service time", task)


def latency(m, task):
    return g(m, "50th percentile latency", task)


def error_rate(m, task):
    v = m.get(("error rate", task))
    return v if v is not None else 0.0


def load_run(run_dir, perm):
    """Load one (perm, rep) run and decide whether it is valid."""
    csv_path = run_dir / f"{perm}.csv"
    m = parse_csv(csv_path)
    if not m:
        return None

    probe = ""
    p = run_dir / f"{perm}.probe"
    if p.exists():
        probe = p.read_text()
    log = ""
    lp = run_dir / f"{perm}.log"
    if lp.exists():
        log = lp.read_text()

    max_err = max([error_rate(m, t) for t in SEARCH_TASKS] + [error_rate(m, "")] + [0.0])
    problems = []
    if max_err > MAX_ERROR_RATE:
        problems.append(f"error rate {max_err:.2f}%")
    if "DOCCOUNT_MISMATCH" in probe:
        problems.append("doc count mismatch")
    elif "DOCCOUNT_OK" not in probe:
        problems.append("doc count unverified")
    if "PARAM_WARNING_PRESENT" in log:
        problems.append("workload param ignored by OSB")
    if "osb_exit_code=0" not in log and log:
        problems.append("osb non-zero exit")

    return {"m": m, "max_error_rate": max_err, "problems": problems,
            "valid": not problems}


# ── stats ─────────────────────────────────────────────────────────────────


def agg(values):
    """Median + IQR over repetitions. Returns None when under-replicated."""
    vals = sorted(v for v in values if v is not None)
    if len(vals) < MIN_REPS:
        return None
    q = statistics.quantiles(vals, n=4, method="inclusive") if len(vals) >= 2 else None
    return {
        "median": statistics.median(vals),
        "p25": q[0] if q else vals[0],
        "p75": q[2] if q else vals[-1],
        "n": len(vals),
        "raw": vals,
    }


def separated(a, b):
    """True when the two IQRs do not overlap -- our bar for a real difference."""
    if not a or not b:
        return False
    return a["p75"] < b["p25"] or b["p75"] < a["p25"]


def compare(a, b, lower_is_better):
    """Render 'X% better' only if IQRs are separated, else 'within noise'."""
    if not a or not b:
        return "insufficient reps"
    if not separated(a, b):
        return "within noise"
    am, bm = a["median"], b["median"]
    if lower_is_better:
        delta = (bm - am) / bm * 100
    else:
        delta = (am - bm) / bm * 100
    return f"{delta:+.1f}%"


def fmt_ms(s):
    if not s:
        return "—"
    v, lo, hi = s["median"], s["p25"], s["p75"]
    unit = (lambda x: f"{x/1000:.2f}s") if v >= 1000 else (lambda x: f"{x:.0f}ms")
    return f"{unit(v)} [{unit(lo)}–{unit(hi)}]"


def fmt_num(s, d=0):
    if not s:
        return "—"
    return f"{s['median']:,.{d}f} [{s['p25']:,.{d}f}–{s['p75']:,.{d}f}]"


# ── report ────────────────────────────────────────────────────────────────


def main():
    if not CONFIG_PATH.exists():
        raise SystemExit("No config.json. Run: python3 scripts/generate.py")
    config = json.loads(CONFIG_PATH.read_text())
    perms = config["permutations"]
    det = config["perm_details"]
    reps = config["reps"]

    R = []
    w = R.append
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    w("# OpenSearch 3.5 — 8th-Gen EC2 CPU Architecture Benchmark")
    w("")
    w(f"**Generated:** {now}  ")
    w(f"**Region:** {config['region']} | **Instance size:** `{config['size']}` | "
      f"**Load generator:** `{config['loadgen_type']}` (fixed for all permutations)  ")
    w(f"**Repetitions:** {reps} per cell | **Tool:** OpenSearch Benchmark | "
      f"**OpenSearch:** 3.5.0 | **EKS Auto Mode + Karpenter**")
    w("")
    w("> All figures are **medians over repetitions**, with the interquartile "
      "range in brackets. A comparison is reported as a percentage **only when "
      "the two IQRs do not overlap**; otherwise it reads *within noise*. See "
      "[METHODOLOGY.md](../docs/METHODOLOGY.md).")
    w("")

    # ── instance table, incl. the SMT asymmetry that vCPU counts hide ──
    w("## Instances under test")
    w("")
    w("| perm | instance | CPU | µarch | vCPU | physical cores | threads/core | "
      "RAM | clock | $/hr | 3-node $/hr |")
    w("|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|")
    for pk in perms:
        d = det[pk]
        w(f"| `{pk}` | {d['instance_type']} | {d['cpu']} | {d['microarchitecture']} | "
          f"{d['vcpus']} | **{d['physical_cores']}** | {d['threads_per_core']} | "
          f"{d['memory_gib']} GiB | {d['clock_marketing']} | "
          f"${d['usd_per_hour']:.4f} | ${d['usd_per_hour']*3:.4f} |")
    w("")

    smt = {pk: det[pk]["threads_per_core"] for pk in perms}
    if len(set(smt.values())) > 1:
        smt_on = sorted({det[pk]["cpu"] for pk in perms if smt[pk] == 2})
        smt_off = sorted({det[pk]["cpu"] for pk in perms if smt[pk] == 1})
        w(f"> ⚠️ **Physical-core asymmetry at equal vCPU count.** "
          f"{', '.join(smt_off)} ship with SMT disabled (1 vCPU = 1 physical core), "
          f"while {', '.join(smt_on)} ship with SMT enabled (1 vCPU = 1 hardware "
          f"thread, so half the physical cores for the same vCPU count and the "
          f"same bill). Per-vCPU comparisons therefore understate "
          f"{', '.join(smt_on)} per-core capability and overstate its per-socket "
          f"capability. Read the **physical cores** column before drawing any "
          f"conclusion from these tables.")
        w("")

    # ── price table, computed ──
    w("### Relative on-demand price")
    w("")
    w("| family | Graviton4 | AMD Turin | Intel Granite Rapids | Turin vs Graviton | Turin vs Intel |")
    w("|---|--:|--:|--:|--:|--:|")
    for fam in ["m", "c", "r"]:
        by_cpu = {det[pk]["cpu"]: det[pk]["usd_per_hour"]
                  for pk in perms if det[pk]["family"] == fam}
        if len(by_cpu) < 3:
            continue
        gp, am, it = (by_cpu.get("Graviton4"), by_cpu.get("AMD Turin"),
                      by_cpu.get("Intel Granite Rapids"))
        w(f"| {fam} | ${gp:.4f} | ${am:.4f} | ${it:.4f} | "
          f"{(am-gp)/gp*100:+.1f}% | {(am-it)/it*100:+.1f}% |")
    w("")

    # ── discover results ──
    workloads = sorted(
        d.name for d in RESULTS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ) if RESULTS_DIR.exists() else []
    if not workloads:
        w("_No results collected yet._")
        (RESULTS_DIR / "REPORT.md").write_text("\n".join(R) + "\n")
        print("No results found; wrote header-only report.")
        return

    invalid_rows = []

    for wl in workloads:
        wl_dir = RESULTS_DIR / wl
        load_keys = [d.name for d in sorted(wl_dir.iterdir()) if d.is_dir()]
        if not load_keys:
            continue

        w(f"## Workload: `{wl}`")
        w("")

        # Load all runs: runs[load][perm] = list of per-rep dicts
        runs = {}
        for lk in load_keys:
            runs[lk] = {}
            for pk in perms:
                cells = []
                for rep_dir in sorted((wl_dir / lk).iterdir()):
                    if not rep_dir.is_dir():
                        continue
                    r = load_run(rep_dir, pk)
                    if r is None:
                        continue
                    if not r["valid"]:
                        invalid_rows.append(
                            (wl, lk, rep_dir.name, pk, "; ".join(r["problems"]))
                        )
                        continue
                    cells.append(r)
                runs[lk][pk] = cells

        # ── indexing (server-side metric, load-level independent) ──
        idx_lk = load_keys[0]
        idx = {pk: agg([g(c["m"], "Cumulative indexing time of primary shards")
                        for c in runs[idx_lk][pk]]) for pk in perms}
        mrg = {pk: agg([g(c["m"], "Cumulative merge time of primary shards")
                        for c in runs[idx_lk][pk]]) for pk in perms}
        ithr = {pk: agg([g(c["m"], "Mean Throughput", "index-append")
                         for c in runs[idx_lk][pk]]) for pk in perms}

        if any(idx.values()):
            w("### Indexing")
            w("")
            w("Server-side Lucene counters, so these are the metrics least "
              "sensitive to load-generator behaviour.")
            w("")
            w("| perm | CPU | cores | index time (min) | merge time (min) | "
              "index throughput (docs/s) | $/M docs indexed |")
            w("|---|---|--:|--:|--:|--:|--:|")
            rows = sorted(perms, key=lambda pk: idx[pk]["median"] if idx[pk] else 9e9)
            for pk in rows:
                d = det[pk]
                cost = "—"
                if idx[pk]:
                    hours = idx[pk]["median"] / 60.0
                    docs_m = config["workloads"][wl]["docs"] / 1e6
                    cost = f"${d['usd_per_hour']*3*hours/docs_m:.4f}"
                w(f"| `{pk}` | {d['cpu']} | {d['physical_cores']} | "
                  f"{fmt_num(idx[pk], 2)} | {fmt_num(mrg[pk], 2)} | "
                  f"{fmt_num(ithr[pk], 0)} | {cost} |")
            w("")

        # ── per-load-level search tables ──
        for lk in load_keys:
            kind = config["load_levels"][lk]["kind"]
            tgt = config["load_levels"][lk]["target_throughput"]
            w(f"### Search — load level `{lk}`"
              f" ({'fixed offered rate ' + str(tgt) + ' ops/s' if kind == 'fixed-rate' else 'unthrottled / saturating'})")
            w("")

            if kind == "fixed-rate":
                w("Offered load is pinned, so **service time is comparable "
                  "across architectures** here.")
                w("")
                w("| perm | CPU | cores | " + " | ".join(SEARCH_TASKS) + " |")
                w("|---|---|--:|" + "--:|" * len(SEARCH_TASKS))
                for pk in perms:
                    d = det[pk]
                    cells = [
                        fmt_ms(agg([service_time(c["m"], t) for c in runs[lk][pk]]))
                        for t in SEARCH_TASKS
                    ]
                    w(f"| `{pk}` | {d['cpu']} | {d['physical_cores']} | "
                      + " | ".join(cells) + " |")
                w("")
                w("Achieved vs offered throughput (a shortfall means the cell "
                  "could not sustain the offered rate, which invalidates its "
                  "service-time numbers):")
                w("")
                w("| perm | CPU | " + " | ".join(SEARCH_TASKS) + " |")
                w("|---|---|" + "--:|" * len(SEARCH_TASKS))
                for pk in perms:
                    cells = []
                    for t in SEARCH_TASKS:
                        a = agg([g(c["m"], "Mean Throughput", t) for c in runs[lk][pk]])
                        if not a:
                            cells.append("—")
                        elif tgt and a["median"] < tgt * 0.95:
                            cells.append(f"**{a['median']:,.0f}** ⚠️")
                        else:
                            cells.append(f"{a['median']:,.0f}")
                    w(f"| `{pk}` | {det[pk]['cpu']} | " + " | ".join(cells) + " |")
                w("")
            else:
                w("Unthrottled, so **throughput is comparable** here. Latency is "
                  "queue-dominated at saturation and is deliberately not reported "
                  "— use the fixed-rate levels above for latency.")
                w("")
                w("| perm | CPU | cores | " + " | ".join(SEARCH_TASKS)
                  + " | $/1k ops (term) |")
                w("|---|---|--:|" + "--:|" * len(SEARCH_TASKS) + "--:|")
                for pk in perms:
                    d = det[pk]
                    cells, term = [], None
                    for t in SEARCH_TASKS:
                        a = agg([g(c["m"], "Mean Throughput", t) for c in runs[lk][pk]])
                        if t == "term":
                            term = a
                        cells.append(fmt_num(a, 0))
                    ppc = "—"
                    if term:
                        ops_hr = term["median"] * 3600
                        ppc = f"${d['usd_per_hour']*3/ops_hr*1000:.5f}"
                    w(f"| `{pk}` | {d['cpu']} | {d['physical_cores']} | "
                      + " | ".join(cells) + f" | {ppc} |")
                w("")

        # ── concurrency scaling: the crossover question ──
        w("### Scaling across load levels (term query)")
        w("")
        w("This is the axis the previous revision could not measure, because "
          "client count was tied to instance family (c=2, m=4, r=8) and "
          "therefore confounded with heap size and RAM. Here client count is "
          f"fixed at {config['fixed']['search_clients']} everywhere and only the "
          "offered rate varies.")
        w("")
        w("| perm | CPU | cores | " + " | ".join(f"`{lk}`" for lk in load_keys) + " |")
        w("|---|---|--:|" + "--:|" * len(load_keys))
        for pk in perms:
            d = det[pk]
            cells = [fmt_num(agg([g(c["m"], "Mean Throughput", "term")
                                  for c in runs[lk][pk]]), 0) for lk in load_keys]
            w(f"| `{pk}` | {d['cpu']} | {d['physical_cores']} | "
              + " | ".join(cells) + " |")
        w("")

        # ── head-to-head, gated on IQR separation ──
        w("### Head-to-head, noise-gated")
        w("")
        w("Percentages appear only where the interquartile ranges of the two "
          "medians do not overlap. Everything else is *within noise* and must "
          "not be quoted as a result.")
        w("")
        w("| family | load level | metric | Graviton4 | AMD Turin | Turin vs Graviton | "
          "price-adjusted |")
        w("|---|---|---|--:|--:|--:|--:|")
        for fam in ["m", "c", "r"]:
            gk = next((pk for pk in perms
                       if det[pk]["family"] == fam and det[pk]["cpu"] == "Graviton4"), None)
            ak = next((pk for pk in perms
                       if det[pk]["family"] == fam and det[pk]["cpu"] == "AMD Turin"), None)
            if not gk or not ak:
                continue
            pr = (det[ak]["usd_per_hour"] - det[gk]["usd_per_hour"]) / det[gk]["usd_per_hour"] * 100

            ga, aa = idx.get(gk), idx.get(ak)
            verdict = compare(aa, ga, lower_is_better=True)
            adj = "—"
            if ga and aa and separated(ga, aa):
                perf = (ga["median"] - aa["median"]) / ga["median"] * 100
                adj = f"{perf - pr:+.1f}%"
            w(f"| {fam} | (indexing) | index time | {fmt_num(ga,2)} | {fmt_num(aa,2)} | "
              f"{verdict} | {adj} |")

            for lk in load_keys:
                kind = config["load_levels"][lk]["kind"]
                if kind == "saturate":
                    gq = agg([g(c["m"], "Mean Throughput", "term") for c in runs[lk][gk]])
                    aq = agg([g(c["m"], "Mean Throughput", "term") for c in runs[lk][ak]])
                    verdict = compare(aq, gq, lower_is_better=False)
                    adj = "—"
                    if gq and aq and separated(gq, aq):
                        perf = (aq["median"] - gq["median"]) / gq["median"] * 100
                        adj = f"{perf - pr:+.1f}%"
                    w(f"| {fam} | `{lk}` | term throughput | {fmt_num(gq,0)} | "
                      f"{fmt_num(aq,0)} | {verdict} | {adj} |")
                else:
                    gs = agg([service_time(c["m"], "term") for c in runs[lk][gk]])
                    as_ = agg([service_time(c["m"], "term") for c in runs[lk][ak]])
                    verdict = compare(as_, gs, lower_is_better=True)
                    adj = "—"
                    if gs and as_ and separated(gs, as_):
                        perf = (gs["median"] - as_["median"]) / gs["median"] * 100
                        adj = f"{perf - pr:+.1f}%"
                    w(f"| {fam} | `{lk}` | term service time | {fmt_ms(gs)} | "
                      f"{fmt_ms(as_)} | {verdict} | {adj} |")
        w("")
        w("*price-adjusted* = performance delta minus the on-demand price delta. "
          "Negative means the faster instance is not worth its premium at list price.")
        w("")

    # ── validity ledger ──
    w("## Run validity")
    w("")
    if invalid_rows:
        w(f"{len(invalid_rows)} run(s) excluded from all medians:")
        w("")
        w("| workload | load | rep | perm | reason |")
        w("|---|---|---|---|---|")
        for row in invalid_rows:
            w("| " + " | ".join(row) + " |")
    else:
        w("All collected runs passed validity checks (error rate ≤ "
          f"{MAX_ERROR_RATE}%, doc counts verified, no ignored workload params, "
          "OSB exit 0).")
    w("")
    w(f"*Generated {now} — "
      "[opensearch-benchmark-framework](https://github.com/AndreKurait/opensearch-benchmark-framework)*")

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / "REPORT.md"
    out.write_text("\n".join(R) + "\n")
    print(f"Report: {out} ({len(R)} lines, {len(invalid_rows)} invalid runs)")


if __name__ == "__main__":
    main()
