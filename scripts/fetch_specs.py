#!/usr/bin/env python3
"""Fetch authoritative EC2 specs + on-demand pricing into specs.json.

Prices and core counts are NEVER hardcoded in this framework -- they come from
the AWS Pricing API and ec2:DescribeInstanceTypes. Run this before generate.py
whenever the instance matrix or region changes:

    python3 scripts/fetch_specs.py --region us-east-1

Why this exists: an earlier revision of this repo hardcoded prices that were
30-49% below list and, critically, had the *wrong ordering* between vendors,
which inverted the price-performance conclusion. Never hardcode these again.
"""
import argparse
import json
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent

FAMILIES = ["m8g", "m8a", "m8i", "c8g", "c8a", "c8i", "r8g", "r8a", "r8i"]
SIZES = ["2xlarge", "8xlarge", "16xlarge"]
# Load generator is architecture-FIXED across the whole matrix on purpose.
EXTRA = ["c8i.8xlarge", "c8i.16xlarge"]

# Pricing API "location" names, keyed by region.
LOCATIONS = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
}

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


def fetch_prices(session, region, types):
    # The Pricing API itself is only served from a few regions.
    pricing = session.client("pricing", region_name="us-east-1")
    location = LOCATIONS.get(region)
    if not location:
        raise SystemExit(f"Add {region!r} to LOCATIONS in fetch_specs.py")

    out = {}
    for it in types:
        filters = [
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": it},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
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
        resp = ec2.describe_instance_types(InstanceTypes=chunk)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--out", default=str(ROOT / "specs.json"))
    args = ap.parse_args()

    types = sorted({f"{f}.{s}" for f in FAMILIES for s in SIZES} | set(EXTRA))
    session = boto3.Session()

    prices = fetch_prices(session, args.region, types)
    hardware = fetch_hardware(session, args.region, types)
    azs = fetch_offerings(session, args.region, types)

    specs = {}
    for it in types:
        if it not in prices or it not in hardware:
            print(f"  WARN missing data for {it}, skipping")
            continue
        p, h = prices[it], hardware[it]
        proc = p["physical_processor"]
        if proc not in UARCH:
            raise SystemExit(
                f"Unknown physicalProcessor {proc!r} for {it}. Add it to UARCH so "
                f"reports cannot mislabel the CPU generation."
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

    payload = {
        "region": args.region,
        "source": "aws pricing:GetProducts + ec2:DescribeInstanceTypes",
        "instances": specs,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.out} ({len(specs)} instance types, region {args.region})")

    # Operator-facing sanity table: this is where hardcoded-price bugs die.
    print(f"\n{'type':<16} {'$/hr':>8} {'vCPU':>5} {'cores':>6} {'t/c':>4} "
          f"{'RAM GiB':>8} {'EBS base':>9}  cpu")
    for it in sorted(specs, key=lambda k: (specs[k]["size"], k)):
        s = specs[it]
        print(f"{it:<16} {s['usd_per_hour']:>8.4f} {s['vcpus']:>5} "
              f"{s['physical_cores']:>6} {s['threads_per_core']:>4} "
              f"{s['memory_mib'] // 1024:>8} {str(s['ebs_baseline_mbps']):>9}  {s['cpu']}")


if __name__ == "__main__":
    main()
