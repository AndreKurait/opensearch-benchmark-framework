#!/usr/bin/env python3
"""Report individual OSB measurements without imputing missing data or winners."""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = ["term", "phrase", "match-all", "country_agg_uncached", "scroll"]


def parse_csv(path):
    """Keep units with finite, nonnegative metrics; reject ambiguous duplicates."""
    metrics = {}
    if not path.exists():
        return metrics
    with path.open(newline="") as source:
        for row in csv.reader(source):
            if len(row) < 4 or row[0].strip() == "Metric":
                continue
            metric, task, value, unit = (part.strip() for part in row[:4])
            try:
                number = float(value)
            except ValueError:
                continue
            if not math.isfinite(number) or number < 0:
                continue
            key = (metric, task)
            if key in metrics and metrics[key] != (number, unit):
                raise ValueError(f"{path}: conflicting measurements for {key}")
            metrics[key] = (number, unit)
    return metrics


def measurement(metrics, metric, task="", unit=None):
    value = metrics.get((metric, task))
    if value is None or (unit is not None and value[1] != unit):
        return "—"
    number, units = value
    return f"{number:,.2f}" + (f" {units}" if units else "")


def report(config, results_dir):
    details = {item["name"]: item for item in config["perm_details"]}
    permutations = config["permutations"]
    if len(set(permutations)) != len(permutations) or set(permutations) != set(details):
        raise ValueError("Configuration must contain one detail entry for every permutation")
    workloads = sorted(path for path in results_dir.iterdir() if path.is_dir()) if results_dir.exists() else []
    lines = [
        "# OpenSearch benchmark measurements", "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"OpenSearch configuration: `{config.get('opensearch_version', 'not recorded')}`",
        f"Benchmark image configuration: `{config.get('benchmark_image', 'not recorded')}`", "",
        "These are individual CSV observations, not a controlled comparison or a recommendation. "
        "The image above is the configured reference; a mutable tag does not identify the image actually run. "
        "Missing, invalid, or unexpected-unit values are shown as —, never as zero. "
        "Service time is not substituted for latency. No averages across workloads or instance families are computed.", "",
        "Cumulative indexing time is summed shard work, not elapsed wall-clock duration. "
        "Max throughput is the maximum reported sample, not sustained throughput. "
        "No repeated-run variance, confidence interval, or tail-latency conclusion can be inferred here.", "",
        "## Configured instance prices", "",
        "Prices are unverified configuration inputs with no recorded region or observation date. "
        "The three-node figure excludes EBS, EKS/Auto Mode fees, networking, and load generators.", "",
        "| Instance | CPU | Configured $/node-hour | Three nodes $/hour |",
        "|---|---|---:|---:|",
    ]
    seen = set()
    for name in permutations:
        item = details[name]
        if item["instance_type"] in seen:
            continue
        seen.add(item["instance_type"])
        price = item["price"]
        lines.append(f"| {item['instance_type']} | {item['cpu']} | {price:.4f} | {price * 3:.4f} |")
    usable = 0
    for workload in workloads:
        results = {name: parse_csv(workload / f"{name}.csv") for name in permutations}
        present = sum(bool(value) for value in results.values())
        if not present:
            continue
        usable += present
        lines.extend(["", f"## {workload.name}", "", f"CSV coverage: **{present}/{len(permutations)}** permutations. "
                      "A readable CSV alone does not prove a successful run; retain Job status and logs.", "",
                      "| Instance | EBS | CSV | Cumulative indexing time | Cumulative merge time |",
                      "|---|---|---|---:|---:|"])
        for name in permutations:
            item, metrics = details[name], results[name]
            lines.append(f"| {item['instance_type']} | {item['ebs_key']} | {'present' if metrics else 'missing/invalid'} | "
                         f"{measurement(metrics, 'Cumulative indexing time of primary shards', unit='min')} | "
                         f"{measurement(metrics, 'Cumulative merge time of primary shards', unit='min')} |")
        for title, metric, unit in [
            ("p50 latency", "50th percentile latency", "ms"),
            ("p99 latency", "99th percentile latency", "ms"),
            ("Maximum sampled throughput", "Max Throughput", "ops/s"),
            ("Error rate", "error rate", "%"),
        ]:
            if not any((metric, task) in metrics for metrics in results.values() for task in TASKS):
                continue
            lines.extend(["", f"### {title}", "",
                          "| Instance | EBS | " + " | ".join(TASKS) + " |",
                          "|---|---|" + "---:|" * len(TASKS)])
            for name in permutations:
                item, metrics = details[name], results[name]
                values = [measurement(metrics, metric, task, unit) for task in TASKS]
                lines.append(f"| {item['instance_type']} | {item['ebs_key']} | " + " | ".join(values) + " |")
    if not usable:
        raise ValueError("No usable CSV measurements found; existing report has not been replaced")
    lines.extend(["", "For reproducibility, retain the exact workload revision, image digest, chart version, region, "
                  "pricing date, cluster configuration, run logs/status, and repeated raw CSVs. "
                  "Compare matching workload, instance family, storage, and concurrency settings before drawing conclusions.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "k8s/generated/config.json")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        text = report(json.loads(args.config.read_text()), args.results)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Report not generated: {error}\n")
    output = args.output or args.results / "REPORT.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
