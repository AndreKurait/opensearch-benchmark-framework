#!/usr/bin/env python3
"""Fetch authoritative EC2 specs + on-demand pricing into specs.json.

Prices and core counts are NEVER hardcoded in this framework -- they come from
the AWS Pricing API and ec2:DescribeInstanceTypes. Run this before generate.py
whenever the instance matrix or region set changes:

    python3 scripts/fetch_specs.py                      # all bench regions
    python3 scripts/fetch_specs.py --regions us-east-1   # just one

Why this exists: an earlier revision of this repo hardcoded prices that were
30-49% below list and, critically, had the *wrong ordering* between vendors,
which inverted the price-performance conclusion. Never hardcode these again.

Multi-region: each region runs one full REPETITION of the matrix, concurrently
with the others, because on-demand vCPU quota is per-region. Prices differ by up
to 25% between regions, so price-performance must be computed *within* a region
and never pooled across them -- this file records a separate price table per
region so report.py cannot accidentally mix them.
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config

ROOT = Path(__file__).resolve().parent.parent

# The Pricing API has a low request rate and throttles hard when several regions
# are fetched at once. Adaptive mode backs off instead of failing the run.
RETRY = Config(retries={"max_attempts": 10, "mode": "adaptive"})

FAMILIES = ["m8g", "m8a", "m8i", "c8g", "c8a", "c8i", "r8g", "r8a", "r8i"]
SIZES = ["2xlarge", "8xlarge", "16xlarge"]
# Load generator is architecture-FIXED across the whole matrix on purpose.
EXTRA = ["c8i.8xlarge", "c8i.16xlarge"]

# Regions that offer ALL nine 8th-gen families, verified via
# ec2:DescribeInstanceTypeOfferings. The AMD (*8a) types are the scarce ones and
# are what disqualify every other region. A region must never be missing a type:
# that would silently drop one arm of a comparison.
#
# Ordered cheapest-first. eu-west-1 is LAST on purpose -- only one of its AZs
# (eu-west-1c) carries all nine types, so it has no fallback AZ if that one is
# out of capacity.
BENCH_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-2",
    "eu-south-2",
    "eu-west-1",
    "eu-central-1",
    "ap-northeast-1",
]

# Marketing name -> canonical microarchitecture. The Pricing API's
# physicalProcessor string is authoritative for the vendor part number; these
# labels exist so reports cannot mislabel a CPU generation.
UARCH = {
    "AWS Graviton4 Processor": ("Graviton4", "Neoverse V2", "arm64"),
    "AMD EPYC 9R45 Processor": ("AMD Turin", "Zen 5", "x86_64"),
    "Intel Xeon Scalable (Granite Rapids)": ("Intel Granite Rapids", "Xeon 6 P-core", "x86_64"),
    "Intel Xeon Scalable (Emerald Rapids)": ("Intel Emerald Rapids", "Xeon 5th gen", "x86_64"),
    "Intel Xeon Scalable (Sapphire Rapids)": ("Intel Sapphire Rapids", "Xeon 4th gen", "x86_64"),
}


def fetch_prices(session, region, types, pricing=None):
    """On-demand Linux price per type. Filters on regionCode rather than the
    human-readable 'location' string: location names are hand-maintained and
    drift (EU (Spain) vs Europe (Spain)), regionCode never does."""
    # The Pricing API itself is only served from a few regions.
    if pricing is None:
        pricing = session.client("pricing", region_name="us-east-1", config=RETRY)
    out = {}
    for it in types:
        filters = [
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": it},
            {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
            {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
        ]
        resp = pricing.get_products(ServiceCode="AmazonEC2", Filters=filters)
        for blob in resp.get("PriceList", []):
            d = json.loads(blob) if isinstance(blob, str) else blob
            attrs = d["product"]["attributes"]
            for term in d["terms"].get("OnDemand", {}).values():
                for dim in term["priceDimensions"].values():
                    out[it] = {
                        "usd_per_hour": float(dim["pricePerUnit"]["USD"]),
                        "physical_processor": attrs.get("physicalProcessor"),
                        "clock_speed_marketing": attrs.get("clockSpeed"),
                    }
    return out


def fetch_hardware(session, region, types):
    ec2 = session.client("ec2", region_name=region)
    out = {}
    for i in range(0, len(types), 50):
        chunk = types[i : i + 50]
        try:
            resp = ec2.describe_instance_types(InstanceTypes=chunk)
        except ec2.exceptions.ClientError:
            # A type absent from this region raises; fall back to per-type.
            resp = {"InstanceTypes": []}
            for it in chunk:
                try:
                    r = ec2.describe_instance_types(InstanceTypes=[it])
                    resp["InstanceTypes"].extend(r["InstanceTypes"])
                except ec2.exceptions.ClientError:
                    pass
        for it in resp["InstanceTypes"]:
            ebs = it.get("EbsInfo", {}).get("EbsOptimizedInfo", {})
            out[it["InstanceType"]] = {
                "vcpus": it["VCpuInfo"]["DefaultVCpus"],
                "physical_cores": it["VCpuInfo"]["DefaultCores"],
                "threads_per_core": it["VCpuInfo"]["DefaultThreadsPerCore"],
                "memory_mib": it["MemoryInfo"]["SizeInMiB"],
                "architecture": it["ProcessorInfo"]["SupportedArchitectures"][0],
                "sustained_ghz": it["ProcessorInfo"].get("SustainedClockSpeedInGhz"),
                "ebs_baseline_mbps": ebs.get("BaselineThroughputInMBps"),
                "ebs_max_mbps": ebs.get("MaximumThroughputInMBps"),
                "ebs_baseline_iops": ebs.get("BaselineIops"),
                "ebs_max_iops": ebs.get("MaximumIops"),
                "network": it["NetworkInfo"]["NetworkPerformance"],
            }
    return out


def fetch_offerings(session, region, types):
    ec2 = session.client("ec2", region_name=region)
    paginator = ec2.get_paginator("describe_instance_type_offerings")
    azs = {}
    for page in paginator.paginate(
        LocationType="availability-zone",
        Filters=[{"Name": "instance-type", "Values": types}],
    ):
        for o in page["InstanceTypeOfferings"]:
            azs.setdefault(o["InstanceType"], []).append(o["Location"])
    return {k: sorted(v) for k, v in azs.items()}


def fetch_vcpu_quota(session, region):
    """Running On-Demand Standard (A,C,D,H,I,M,R,T,Z) instances, in vCPU.
    All nine families draw on this single bucket, so it is the hard ceiling on
    how much of the matrix a region can hold at once."""
    try:
        sq = session.client("service-quotas", region_name=region)
        r = sq.get_service_quota(ServiceCode="ec2", QuotaCode="L-1216C47A")
        return r["Quota"]["Value"]
    except Exception:
        return None


def build_region(session, region, types, size, prices):
    hardware = fetch_hardware(session, region, types)
    azs = fetch_offerings(session, region, types)
    quota = fetch_vcpu_quota(session, region)

    specs = {}
    for it in types:
        if it not in prices or it not in hardware:
            continue
        p, h = prices[it], hardware[it]
        proc = p["physical_processor"]
        if proc not in UARCH:
            raise SystemExit(
                f"Unknown physicalProcessor {proc!r} for {it} in {region}. Add it "
                f"to UARCH so reports cannot mislabel the CPU generation."
            )
        cpu, uarch, arch = UARCH[proc]
        if arch != h["architecture"]:
            raise SystemExit(f"Arch mismatch for {it}: {arch} vs {h['architecture']}")
        specs[it] = {
            "instance_type": it,
            "family": it.split(".")[0][0],
            "family_key": it.split(".")[0],
            "size": it.split(".")[1],
            "cpu": cpu,
            "microarchitecture": uarch,
            "physical_processor": proc,
            "clock_speed_marketing": p["clock_speed_marketing"],
            "usd_per_hour": p["usd_per_hour"],
            "azs": azs.get(it, []),
            **h,
        }

    # A region is only usable as a repetition if it has every family at the
    # benchmark size AND at least one AZ carrying all of them (a cell must not be
    # split across AZs, or network topology becomes a confound).
    wanted = [f"{f}.{size}" for f in FAMILIES]
    missing = [it for it in wanted if it not in specs]
    az_sets = [set(specs[it]["azs"]) for it in wanted if it in specs]
    shared_azs = sorted(set.intersection(*az_sets)) if len(az_sets) == len(wanted) else []

    return {
        "region": region,
        "vcpu_quota_standard_ondemand": quota,
        "missing_at_bench_size": missing,
        "azs_with_all_families": shared_azs,
        "usable_as_repetition": not missing and bool(shared_azs),
        "instances": specs,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", nargs="*", default=BENCH_REGIONS,
                    help="regions to fetch (default: all bench regions)")
    ap.add_argument("--size", default="8xlarge",
                    help="benchmark instance size, for the usability check")
    ap.add_argument("--out", default=str(ROOT / "specs.json"))
    args = ap.parse_args()

    types = sorted({f"{f}.{s}" for f in FAMILIES for s in SIZES} | set(EXTRA))
    session = boto3.Session()

    # Prices first, sequentially: one shared throttle-aware client for every
    # region, because the Pricing API rate-limits aggressively.
    pricing = session.client("pricing", region_name="us-east-1", config=RETRY)
    prices = {}
    for rg in args.regions:
        prices[rg] = fetch_prices(session, rg, types, pricing=pricing)
        print(f"  priced {rg} ({len(prices[rg])} types)")

    # EC2 describes are per-region and cheap; these can run concurrently.
    with ThreadPoolExecutor(max_workers=len(args.regions)) as ex:
        built = list(ex.map(
            lambda rg: build_region(session, rg, types, args.size, prices[rg]),
            args.regions))
    regions = {b["region"]: b for b in built}

    payload = {
        "source": "aws pricing:GetProducts + ec2:DescribeInstanceTypes",
        "bench_size": args.size,
        "regions": regions,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    usable = [rg for rg, b in regions.items() if b["usable_as_repetition"]]
    print(f"Wrote {args.out}: {len(regions)} regions, {len(usable)} usable as "
          f"repetitions at {args.size}")

    # Operator-facing sanity tables: this is where hardcoded-price bugs die.
    print(f"\n{'region':<16} {'quota vCPU':>10} {'stack $/hr':>11} "
          f"{'AZs w/ all 9':>13}  status")
    for rg in args.regions:
        b = regions[rg]
        stack = sum(b["instances"][f"{f}.{args.size}"]["usd_per_hour"]
                    for f in FAMILIES if f"{f}.{args.size}" in b["instances"]) * 3
        q = b["vcpu_quota_standard_ondemand"]
        status = "ok" if b["usable_as_repetition"] else f"UNUSABLE {b['missing_at_bench_size']}"
        print(f"{rg:<16} {(q if q is not None else -1):>10.0f} {stack:>11.2f} "
              f"{len(b['azs_with_all_families']):>13}  {status}")

    ref = regions[args.regions[0]]
    print(f"\nHardware ({args.regions[0]}, {args.size}) — identical across regions:")
    print(f"{'type':<16} {'$/hr':>8} {'vCPU':>5} {'cores':>6} {'t/c':>4} "
          f"{'RAM GiB':>8} {'EBS base':>9}  cpu")
    for f in FAMILIES:
        it = f"{f}.{args.size}"
        s = ref["instances"].get(it)
        if not s:
            continue
        print(f"{it:<16} {s['usd_per_hour']:>8.4f} {s['vcpus']:>5} "
              f"{s['physical_cores']:>6} {s['threads_per_core']:>4} "
              f"{s['memory_mib'] // 1024:>8} {str(s['ebs_baseline_mbps']):>9}  {s['cpu']}")

    # Price spread across regions matters: it is why price-performance is never
    # pooled across regions.
    print(f"\nPrice spread across regions ({args.size}):")
    print(f"{'type':<16} {'min $/hr':>9} {'max $/hr':>9} {'spread':>8}")
    for f in FAMILIES:
        it = f"{f}.{args.size}"
        vals = [regions[rg]["instances"][it]["usd_per_hour"]
                for rg in args.regions if it in regions[rg]["instances"]]
        if vals:
            print(f"{it:<16} {min(vals):>9.4f} {max(vals):>9.4f} "
                  f"{(max(vals)/min(vals)-1)*100:>7.1f}%")


if __name__ == "__main__":
    main()
