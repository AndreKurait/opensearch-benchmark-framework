#!/usr/bin/env python3
"""Generate REPORT.md from OSB CSV results across multiple workloads."""
import csv, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "k8s" / "generated" / "config.json"
RESULTS_DIR = ROOT / "results"

def load_config():
    if not CONFIG_PATH.exists():
        print("No config.json. Run: python3 scripts/generate.py"); sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())

def parse_csv(path):
    m = {}
    if not path.exists(): return m
    for row in csv.reader(path.open()):
        if len(row) < 3 or row[0].strip() == "Metric": continue
        try: m[(row[0].strip(), row[1].strip())] = float(row[2].strip())
        except ValueError: pass
    return m

def gf(m, metric, task=""):
    return m.get((metric, task), 0.0)

def get_lat(m, task):
    """Get p50 latency in ms, trying both metric names."""
    v = gf(m, "50th percentile latency", task)
    if v <= 0: v = gf(m, "50th percentile service time", task)
    return v

def fmt_ms(v):
    """Format milliseconds: show as seconds if >= 1000."""
    if v <= 0: return "—"
    if v >= 1000: return f"{v/1000:.1f}s"
    return f"{v:.1f}ms"

def fmt(v, d=1):
    if v <= 0: return "—"
    return f"{v:,.{d}f}"

def main():
    config = load_config()
    perms = config["permutations"]
    details = {p["name"]: p for p in config["perm_details"]}

    workloads = sorted([d.name for d in RESULTS_DIR.iterdir() if d.is_dir() and d.name != ".gitkeep"])
    if not workloads:
        print("No results found."); return

    R = []
    w = R.append

    w("# OpenSearch 3.5 Benchmark — 8th Gen EC2 Price-Performance")
    w("")
    w(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    w(f"**Workloads:** {', '.join(workloads)} | **Permutations:** {len(perms)}")
    w("**Tool:** OpenSearch Benchmark 2.1 | **OpenSearch:** 3.5.0 | **EKS Auto Mode + Karpenter**")
    w("")

    # ── Executive Summary (computed from gp3-default results) ──
    all_results = {}
    for wl in workloads:
        for pk in perms:
            m = parse_csv(RESULTS_DIR / wl / f"{pk}.csv")
            if m and "gp3-default" in pk:
                all_results.setdefault(details[pk]["cpu"], []).append(m)

    if len(all_results) == 3:
        def cpu_avg(cpu, fn):
            rows = all_results.get(cpu, [])
            vals = [fn(m) for m in rows if fn(m) > 0]
            return sum(vals) / len(vals) if vals else 0

        ai = cpu_avg("AMD Turin", lambda m: gf(m, "Cumulative indexing time of primary shards"))
        gi = cpu_avg("Graviton4", lambda m: gf(m, "Cumulative indexing time of primary shards"))
        ii = cpu_avg("Intel Emerald Rapids", lambda m: gf(m, "Cumulative indexing time of primary shards"))
        at = cpu_avg("AMD Turin", lambda m: get_lat(m, "term"))
        gt = cpu_avg("Graviton4", lambda m: get_lat(m, "term"))
        it = cpu_avg("Intel Emerald Rapids", lambda m: get_lat(m, "term"))
        aq = cpu_avg("AMD Turin", lambda m: gf(m, "Max Throughput", "term"))
        gq = cpu_avg("Graviton4", lambda m: gf(m, "Max Throughput", "term"))
        iq = cpu_avg("Intel Emerald Rapids", lambda m: gf(m, "Max Throughput", "term"))

        w("## Summary")
        w("")
        w(f"**AMD Turin (m8a/c8a/r8a) appears to be the best 8th-gen EBS-based instance family for OpenSearch workloads** — "
          f"delivering {(gi-ai)/gi*100:.0f}% faster indexing ({ai:.1f} min vs {gi:.1f} min), "
          f"{(aq-gq)/gq*100:.0f}% higher search QPS ({aq:,.0f} vs {gq:,.0f}), "
          f"and {(gt-at)/gt*100:.0f}% lower p50 search latency ({fmt_ms(at)} vs {fmt_ms(gt)}) "
          f"than Graviton4 at only 9-12% higher cost, "
          f"while being both faster and 6% cheaper than Intel Emerald Rapids across all instance families tested (m/c/r).")
        w("")
        w("---")
        w("")

    # Instance table
    w("## Instance Types")
    w("")
    w("| Instance | CPU | vCPU | RAM | $/hr | 3-node $/hr |")
    w("|----------|-----|-----:|----:|-----:|------------:|")
    seen = set()
    for pk in perms:
        d = details[pk]
        ik = d["instance_key"]
        if ik in seen: continue
        seen.add(ik)
        ram = {"m": 32, "c": 16, "r": 64}[d["family"]]
        w(f"| {d['instance_type']} | {d['cpu']} | 8 | {ram}GB | ${d['price']:.4f} | ${d['price']*3:.4f} |")
    w("")
    w("---")
    w("")

    for wl in workloads:
        wl_dir = RESULTS_DIR / wl
        results = {}
        for pk in perms:
            m = parse_csv(wl_dir / f"{pk}.csv")
            if m: results[pk] = m
        if not results: continue

        w(f"## {wl} ({len(results)}/{len(perms)} permutations)")
        w("")

        # ── SUMMARY BY CPU (gp3-default only) ──
        cpus = {}
        for pk, m in results.items():
            if "gp3-fast" in pk: continue
            d = details[pk]
            cpu = d["cpu"]
            cpus.setdefault(cpu, []).append({
                "d": d, "m": m,
                "idx": gf(m, "Cumulative indexing time of primary shards"),
                "term": get_lat(m, "term"),
                "agg": get_lat(m, "country_agg_uncached"),
                "term_qps": gf(m, "Max Throughput", "term"),
            })

        if len(cpus) == 3:
            w("### Summary by CPU Architecture (gp3-default)")
            w("")
            w("| CPU | Avg Index Time | Avg Term Latency | Avg Agg Latency | Avg Term QPS | Avg $/hr |")
            w("|-----|---------------:|-----------------:|----------------:|-------------:|---------:|")
            for cpu in ["AMD Turin", "Graviton4", "Intel Emerald Rapids"]:
                rows = cpus.get(cpu, [])
                if not rows: continue
                n = len(rows)
                ai = sum(r["idx"] for r in rows) / n
                at = sum(r["term"] for r in rows) / n
                aa = sum(r["agg"] for r in rows) / n
                aq = sum(r["term_qps"] for r in rows) / n
                ap = sum(r["d"]["price"] for r in rows) / n
                w(f"| {cpu} | {ai:.1f} min | {fmt_ms(at)} | {fmt_ms(aa)} | {aq:,.0f} | ${ap:.4f} |")
            w("")

            # Turin advantage
            amd = cpus.get("AMD Turin", [])
            grav = cpus.get("Graviton4", [])
            intel = cpus.get("Intel Emerald Rapids", [])
            if amd and grav and intel:
                def avg(rows, k): return sum(r[k] for r in rows) / len(rows)
                ai, gi, ii = avg(amd,"idx"), avg(grav,"idx"), avg(intel,"idx")
                at, gt, it = avg(amd,"term"), avg(grav,"term"), avg(intel,"term")
                w("**AMD Turin advantage:**")
                w(f"- vs Graviton4: **{(gi-ai)/gi*100:.0f}% faster indexing**, **{(gt-at)/gt*100:.0f}% lower search latency**, 9-12% higher cost")
                w(f"- vs Intel: **{(ii-ai)/ii*100:.0f}% faster indexing**, **{(it-at)/it*100:.0f}% lower search latency**, **6% cheaper**")
                w("")

        # ── INDEXING ──
        w("### Indexing Performance")
        w("")
        rows = []
        for pk, m in results.items():
            d = details[pk]
            idx = gf(m, "Cumulative indexing time of primary shards")
            merge = gf(m, "Cumulative merge time of primary shards")
            ebs = "default" if "default" in d["ebs_key"] else "fast"
            rows.append((pk, d, ebs, idx, merge))
        rows.sort(key=lambda x: x[3] if x[3] > 0 else 999)

        w("| Rank | Instance | CPU | EBS | Index Time (min) | Merge Time (min) |")
        w("|-----:|----------|-----|-----|----------------:|-----------------:|")
        for i, (pk, d, ebs, idx, merge) in enumerate(rows):
            w(f"| #{i+1} | {d['instance_type']} | {d['cpu']} | {ebs} | {fmt(idx,2)} | {fmt(merge,2)} |")
        w("")

        # ── SEARCH LATENCY ──
        search_tasks = ["term", "phrase", "match-all", "country_agg_uncached", "scroll"]
        has_search = any(get_lat(m, "term") > 0 for m in results.values())

        if has_search:
            w("### Search Latency (p50)")
            w("")
            w("| Instance | CPU | EBS | term | phrase | match-all | country_agg | scroll |")
            w("|----------|-----|-----|-----:|-------:|----------:|------------:|-------:|")
            for pk in sorted(results.keys()):
                d = details[pk]
                ebs = "default" if "default" in d["ebs_key"] else "fast"
                vals = [fmt_ms(get_lat(results[pk], t)) for t in search_tasks]
                w(f"| {d['instance_type']} | {d['cpu']} | {ebs} | " + " | ".join(vals) + " |")
            w("")

            # ── SEARCH QPS ──
            w("### Search Throughput (QPS)")
            w("")
            w("| Instance | CPU | EBS | term | phrase | match-all | country_agg | scroll |")
            w("|----------|-----|-----|-----:|-------:|----------:|------------:|-------:|")
            for pk in sorted(results.keys()):
                d = details[pk]
                ebs = "default" if "default" in d["ebs_key"] else "fast"
                vals = [fmt(gf(results[pk], "Max Throughput", t)) for t in search_tasks]
                w(f"| {d['instance_type']} | {d['cpu']} | {ebs} | " + " | ".join(vals) + " |")
            w("")

        # ── EBS COMPARISON ──
        w("### EBS Impact (default vs fast)")
        w("")
        w("| Instance | CPU | Default | Fast | Δ% |")
        w("|----------|-----|--------:|-----:|---:|")
        for ik in config["instances"]:
            pk_d = f"{ik}-gp3-default"
            pk_f = f"{ik}-gp3-fast"
            if pk_d not in results or pk_f not in results: continue
            d = details[pk_d]
            td = gf(results[pk_d], "Cumulative indexing time of primary shards")
            tf = gf(results[pk_f], "Cumulative indexing time of primary shards")
            delta = round((tf - td) / td * 100, 1) if td > 0 else 0
            w(f"| {d['instance_type']} | {d['cpu']} | {fmt(td,2)} min | {fmt(tf,2)} min | {delta:+.1f}% |")
        w("")
        w("---")
        w("")

    w(f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} — [opensearch-benchmark-framework](https://github.com/AndreKurait/opensearch-benchmark-framework)*")

    report = "\n".join(R)
    out = RESULTS_DIR / "REPORT.md"
    out.write_text(report)
    print(f"Report: {out} ({len(R)} lines)")

if __name__ == "__main__":
    main()
