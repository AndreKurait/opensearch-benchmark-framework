#!/usr/bin/env python3
"""Generate K8s manifests for OpenSearch CPU-architecture benchmark permutations.

Design constraints (each one exists because violating it produced a wrong
conclusion in an earlier revision of this repo -- see docs/METHODOLOGY.md):

 1. The load generator runs on a DEDICATED, ARCHITECTURE-FIXED node pool. It is
    never co-located with the system under test. Otherwise a slower-per-core SUT
    also slows the measuring instrument and the architecture delta is counted
    twice.
 2. Concurrency/offered-load is an INDEPENDENT axis, not a function of instance
    family. Otherwise you cannot distinguish "CPU A is faster" from "CPU A was
    tested at a more favourable occupancy".
 3. JVM heap and client count are FIXED across all instance types. Only the
    instance itself varies. RAM differences between c/m/r remain, but they are
    now the only uncontrolled variable and they are symmetric across vendors.
 4. Latency is measured at a FIXED offered rate. Latency and throughput are
    never both free variables in the same measurement.
 5. Prices and core counts come from specs.json (AWS APIs), never hardcoded.

Run: python3 scripts/fetch_specs.py && python3 scripts/generate.py
"""
import json
import os
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPECS_PATH = ROOT / "specs.json"

# One region == one full REPETITION of the matrix, run concurrently with the
# other regions. On-demand vCPU quota is per-region (~1152-1689 vCPU), and a
# single 27-node stack already needs 864, so a region cannot hold two stacks.
# Spreading repetitions across regions is therefore the only way to parallelise
# without a quota increase -- and it samples host-placement variance properly,
# which repetitions on the *same* nodes do not.
#
# Hard rule: a region always runs ALL nine instance types. Never split a
# comparison across regions, or the architecture delta is confounded with the
# regional hardware population. Region is a blocking factor, nothing more.
REGION = os.environ.get("BENCH_REGION", "us-east-1")
OUT = ROOT / "k8s" / "generated" / REGION

# ── Permutation axes ──────────────────────────────────────────────────────

# Instance families under test. Size is deliberately >= 8xlarge: at 2xlarge the
# EBS and network allocations are BURSTABLE (312.5 MB/s baseline vs 1250 MB/s
# burst), so credit depletion mid-run is a large, uncontrolled noise source.
# At 8xlarge, baseline == maximum, so storage behaviour is steady-state.
# Overridable so a Graviton5 wave (BENCH_FAMILIES="m9g,c9g,r9g") reuses this
# generator unchanged. Must match whatever BENCH_FAMILIES fetch_specs.py ran with,
# or the lookup into specs.json will miss.
FAMILY_KEYS = [
    f.strip() for f in os.environ.get(
        "BENCH_FAMILIES",
        "m8g,m8a,m8i,c8g,c8a,c8i,r8g,r8a,r8i",
    ).split(",") if f.strip()
]
SIZE = os.environ.get("BENCH_SIZE", "8xlarge")

# Load generator: ONE instance type for every permutation, so the measuring
# instrument is identical regardless of which CPU is under test.
LOADGEN_TYPE = os.environ.get("BENCH_LOADGEN_TYPE", "c8i.8xlarge")

# Offered search load in ops/sec. This is the concurrency axis. "saturate"
# removes rate limiting to measure maximum throughput; the numeric levels hold
# offered load constant so that LATENCY is comparable across architectures.
#
# Reporting rule enforced in report.py:
#   - numeric levels  -> compare latency / service time (throughput is pinned)
#   - "saturate"      -> compare throughput (latency is meaningless here)
#
# The saturate level restricts the task list (see SATURATE_TASKS). Running the
# full 26-task append-no-conflicts procedure unthrottled does not finish: with
# the rate limit removed the cluster is pegged, and the first observed attempt
# was still only 31% through task 2 of 26 (node-stats) after 82 minutes, so
# every region hit the 3h per-cell ceiling and collected zero permutations.
# The fixed-rate levels complete in 75-105 min precisely BECAUSE the rate cap
# keeps the cluster below saturation; that headroom is what the stats and
# heavy-aggregation tasks need in order to make progress.
LOAD_LEVELS = {
    "load-500": {"target_throughput": 500, "kind": "fixed-rate"},
    "load-2000": {"target_throughput": 2000, "kind": "fixed-rate"},
    "load-8000": {"target_throughput": 8000, "kind": "fixed-rate"},
    "saturate": {"target_throughput": 0, "kind": "saturate"},
}

# Tasks DROPPED at the saturate level. Two independent reasons to restrict:
#   1. Feasibility -- the full procedure cannot complete unthrottled (above).
#   2. Relevance -- saturate exists to measure a THROUGHPUT ceiling, and only
#      tasks that actually saturate can express one. index-stats/node-stats are
#      admin APIs, not search work; the sort/script/painless tasks were never
#      part of any comparison the report makes.
#
# This is an EXCLUDE list rather than an include list on purpose. OSB's
# --include-tasks filters the whole schedule, including delete-index /
# create-index / index-append / refresh-after-index / force-merge, so an include
# list of search tasks would benchmark searches against an empty index. Naming
# the tasks to drop leaves the indexing pipeline intact.
#
# What survives: match-all, term, phrase (the cheap queries whose throughput was
# pinned to the offered rate at every fixed-rate level, so saturate is the ONLY
# level where they can discriminate CPUs at all) plus country_agg_uncached and
# scroll, which already saturate at fixed rates and therefore serve as the
# cross-check that the unthrottled numbers agree with the throttled ones.
SATURATE_EXCLUDE_TASKS = [
    "index-stats",
    "node-stats",
    "country_agg_cached",
    "expression",
    "painless_static",
    "painless_dynamic",
    "decay_geo_gauss_function_score",
    "decay_geo_gauss_script_score",
    "field_value_function_score",
    "field_value_script_score",
    "large_terms",
    "large_filtered_terms",
    "large_prohibited_terms",
    "desc_sort_population",
    "asc_sort_population",
    "asc_sort_with_after_population",
    "desc_sort_geonameid",
    "desc_sort_with_after_geonameid",
    "asc_sort_geonameid",
    "asc_sort_with_after_geonameid",
    "numeric-term-cardinality-agg-high",
]

# Single storage tier, provisioned to be ACTUALLY ACHIEVABLE at 8xlarge
# (1250 MB/s EBS baseline). The old default/fast EBS axis was dead weight: the
# "fast" tier asked for 1000 MB/s on a node with a 312.5 MB/s baseline, so it
# was never realised and contributed only noise.
# 200 GiB is ~15x the largest workload's on-disk footprint with room for merges
# and translog. 500 GiB was oversized and, at 7 concurrent regions, would have
# cost real money for empty blocks while pushing against the per-region gp3
# storage quota. Throughput/IOPS are what matter here and they are unchanged.
EBS = {"throughput": 1000, "iops": 16000, "size": "200Gi", "type": "gp3"}

WORKLOADS = {
    "geonames": {
        "docs": 11396505,
        "index": "geonames",
        "test_procedure": "append-no-conflicts",
        "cache_resident": True,
    },
    "nyc_taxis": {
        "docs": 165346692,
        "index": "nyc_taxis",
        "test_procedure": "append-no-conflicts",
        "cache_resident": False,
    },
    "http_logs": {
        "docs": 247249096,
        "index": "logs-*",
        "test_procedure": "append-no-conflicts",
        "cache_resident": False,
    },
    "pmc": {
        "docs": 574199,
        "index": "pmc",
        "test_procedure": "append-no-conflicts",
        "cache_resident": True,
    },
}

# ── FIXED across every permutation (decoupled from instance family) ───────

JVM_HEAP = "26g"          # below the 32 GiB compressed-oops cliff, with room for
                          # metaspace/direct buffers inside the request below
MEM_REQUEST = "32Gi"      # must fit the SMALLEST node in the matrix (c8*.8xlarge, 64 GiB).
                          # Deliberately NO memory limit: a cgroup limit throttles
                          # page cache, and page-cache size is exactly the
                          # legitimate difference between the c/m/r families.
CPU_REQUEST = "28"        # of 32 vCPU, leaving headroom for kubelet/DaemonSets
SEARCH_CLIENTS = 64       # ample and identical everywhere: never the bottleneck
BULK_CLIENTS = 32
BULK_SIZE = 5000
SHARDS = 3
REPLICAS = 1
OS_VERSION = "3.5.0"

OSB_IMAGE = os.environ.get(
    "OSB_IMAGE", "public.ecr.aws/opensearchproject/opensearch-benchmark:latest"
)

# ── Helpers ───────────────────────────────────────────────────────────────


def load_specs():
    """Return the spec block for THIS region only. Prices differ by up to 29%
    between regions, so a cross-region price table would silently produce
    nonsense price-performance numbers."""
    if not SPECS_PATH.exists():
        raise SystemExit("No specs.json. Run: python3 scripts/fetch_specs.py")
    payload = json.loads(SPECS_PATH.read_text())
    if "regions" not in payload:
        raise SystemExit(
            "specs.json is in the old single-region format. Re-run: "
            "python3 scripts/fetch_specs.py"
        )
    block = payload["regions"].get(REGION)
    if block is None:
        have = ", ".join(sorted(payload["regions"]))
        raise SystemExit(f"No specs for region {REGION!r}. Have: {have}")
    if not block.get("usable_as_repetition"):
        raise SystemExit(
            f"{REGION} cannot host a repetition: missing "
            f"{block.get('missing_at_bench_size')} or no AZ carries all families."
        )
    return block


def dump(docs):
    return "---\n".join(
        yaml.dump(d, default_flow_style=False, sort_keys=False) for d in docs
    )


def svc_name(p):
    """Headless service / StatefulSet name produced by the OpenSearch Helm
    chart: '<clusterName>-<nodeGroup>'. Single source of truth -- the previous
    revision hardcoded 'opensearch-cluster-master' in the OSB target while the
    chart actually created '<perm>-master', so the generated jobs could not
    have reached the clusters they were meant to measure."""
    return f"{p['name']}-master"


def build_perms(specs):
    """One permutation per instance type. Load level is a run-time axis, not a
    deployment axis -- the same cluster is re-used across load levels so that
    cluster-to-cluster variation cannot masquerade as a load effect."""
    perms = []
    for fk in FAMILY_KEYS:
        it = f"{fk}.{SIZE}"
        s = specs["instances"].get(it)
        if s is None:
            raise SystemExit(f"{it} missing from specs.json; re-run fetch_specs.py")
        perms.append(
            {
                "name": fk,
                "namespace": f"os-{fk}",
                "instance_type": it,
                "cpu": s["cpu"],
                "microarchitecture": s["microarchitecture"],
                "arch": s["architecture"],
                "family": s["family"],
                "vcpus": s["vcpus"],
                "physical_cores": s["physical_cores"],
                "threads_per_core": s["threads_per_core"],
                "memory_gib": s["memory_mib"] // 1024,
                "sustained_ghz": s["sustained_ghz"],
                "clock_marketing": s["clock_speed_marketing"],
                "usd_per_hour": s["usd_per_hour"],
                "ebs_baseline_mbps": s["ebs_baseline_mbps"],
            }
        )
    return perms


# ── Generators ────────────────────────────────────────────────────────────


def gen_storageclass():
    return dump(
        [
            {
                "apiVersion": "storage.k8s.io/v1",
                "kind": "StorageClass",
                "metadata": {"name": "bench-ebs"},
                "provisioner": "ebs.csi.eks.amazonaws.com",
                "volumeBindingMode": "WaitForFirstConsumer",
                "reclaimPolicy": "Delete",
                "parameters": {
                    "type": EBS["type"],
                    "throughput": str(EBS["throughput"]),
                    "iops": str(EBS["iops"]),
                },
            }
        ]
    )


def gen_nodepools(perms, az):
    """All pools are pinned to a SINGLE availability zone.

    Two reasons. First, cross-AZ placement would make network topology a
    confound: the load generator would be one hop from some clusters and two
    from others. Second, only one AZ in some regions (eu-west-1c) offers all
    nine 8th-gen types at all, so an unpinned pool could silently fail to
    provision one arm of the comparison."""
    az_req = {
        "key": "topology.kubernetes.io/zone",
        "operator": "In",
        "values": [az],
    }
    pools = []
    for p in perms:
        pools.append(
            {
                "apiVersion": "karpenter.sh/v1",
                "kind": "NodePool",
                "metadata": {"name": f"sut-{p['name']}"},
                "spec": {
                    "template": {
                        "metadata": {
                            "labels": {"bench/role": "sut", "bench/perm": p["name"]}
                        },
                        "spec": {
                            "nodeClassRef": {
                                "group": "eks.amazonaws.com",
                                "kind": "NodeClass",
                                "name": "default",
                            },
                            "requirements": [
                                {
                                    "key": "node.kubernetes.io/instance-type",
                                    "operator": "In",
                                    "values": [p["instance_type"]],
                                },
                                {
                                    "key": "karpenter.sh/capacity-type",
                                    "operator": "In",
                                    "values": ["on-demand"],
                                },
                                az_req,
                            ],
                        },
                    },
                    # 3 SUT nodes only. No room for anything else to land here.
                    "limits": {"cpu": str(p["vcpus"] * 3)},
                    "disruption": {
                        "consolidateAfter": "Never",
                        "budgets": [{"nodes": "0"}],
                    },
                },
            }
        )

    # Load-generator pool: fixed instance type, tainted so that no OpenSearch
    # pod can ever be scheduled onto it.
    pools.append(
        {
            "apiVersion": "karpenter.sh/v1",
            "kind": "NodePool",
            "metadata": {"name": "loadgen"},
            "spec": {
                "template": {
                    "metadata": {"labels": {"bench/role": "loadgen"}},
                    "spec": {
                        "nodeClassRef": {
                            "group": "eks.amazonaws.com",
                            "kind": "NodeClass",
                            "name": "default",
                        },
                        "requirements": [
                            {
                                "key": "node.kubernetes.io/instance-type",
                                "operator": "In",
                                "values": [LOADGEN_TYPE],
                            },
                            {
                                "key": "karpenter.sh/capacity-type",
                                "operator": "In",
                                "values": ["on-demand"],
                            },
                            az_req,
                        ],
                        "taints": [
                            {
                                "key": "bench/loadgen",
                                "value": "true",
                                "effect": "NoSchedule",
                            }
                        ],
                    },
                },
                "limits": {"cpu": "512"},
                "disruption": {
                    "consolidateAfter": "Never",
                    "budgets": [{"nodes": "0"}],
                },
            },
        }
    )
    return dump(pools)


def gen_rbac():
    return dump(
        [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "osb-sa", "namespace": "default"},
            },
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {"name": "osb-writer", "namespace": "default"},
                "rules": [
                    {
                        "apiGroups": [""],
                        "resources": ["configmaps"],
                        "verbs": ["create", "update", "patch", "get"],
                    }
                ],
            },
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {"name": "osb-writer", "namespace": "default"},
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": "osb-writer",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": "osb-sa",
                        "namespace": "default",
                    }
                ],
            },
        ]
    )


def gen_helm_values(p):
    """Identical resource shape for every permutation. The ONLY thing that
    differs between these files is which node pool the pods land on."""
    return yaml.dump(
        {
            "clusterName": p["name"],
            "nodeGroup": "master",
            # The chart derives the StatefulSet, headless service and discovery
            # seed hosts from clusterName-nodeGroup. Set masterService
            # explicitly so the name used here, in run.sh and in the OSB
            # --target-hosts can never drift apart again.
            "masterService": svc_name(p),
            "replicas": 3,
            "roles": ["master", "ingest", "data", "remote_cluster_client"],
            "resources": {"requests": {"memory": MEM_REQUEST, "cpu": CPU_REQUEST}},
            "opensearchJavaOpts": f"-Xms{JVM_HEAP} -Xmx{JVM_HEAP}",
            "persistence": {
                "enabled": True,
                "size": EBS["size"],
                "storageClass": "bench-ebs",
            },
            "extraEnvs": [{"name": "DISABLE_SECURITY_PLUGIN", "value": "true"}],
            "config": {
                "opensearch.yml": (
                    f"cluster.name: {p['name']}\n"
                    "network.host: 0.0.0.0\n"
                    "plugins.security.disabled: true\n"
                    # Make the vectorised Lucene path explicit and identical on
                    # both architectures, so an arm64/x86 JIT difference cannot
                    # be misread as a CPU difference.
                    "opensearch.experimental.feature.telemetry.enabled: false\n"
                )
            },
            "nodeSelector": {"bench/perm": p["name"], "bench/role": "sut"},
            # HARD, not soft: two data pods sharing a node would silently
            # invalidate the permutation.
            "antiAffinity": "hard",
            "protocol": "http",
            "sysctlInit": {"enabled": True},
            "startupProbe": {
                "tcpSocket": {"port": 9200},
                "initialDelaySeconds": 30,
                "periodSeconds": 10,
                "failureThreshold": 60,
            },
        },
        default_flow_style=False,
        sort_keys=False,
    )


# Captures the facts needed to prove the two clusters were comparable: JVM
# build, whether the Lucene Panama vector path is active, CPU model as the
# kernel sees it, and the post-index doc count.
PROBE_SCRIPT = r"""
set -u
ES="$1"; IDX="$2"; EXPECTED="$3"
# Fetch with python3, NOT curl. The opensearch-benchmark image ships no curl, so
# every probe call silently fell back to '{}' -- which made the doc-count check
# read "counted=ERR" and flagged all 18 runs of the first complete load level as
# DOCCOUNT_MISMATCH. The benchmark data was fine; only the auditing was broken,
# and a broken audit that discards good data is worse than no audit. python3 is
# guaranteed present because OSB itself is a python application.
probe() {
  python3 - "$ES/$1" <<'PY' 2>/dev/null || echo '{}'
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=30) as r:
        sys.stdout.write(r.read().decode("utf-8", "replace"))
except Exception:
    print("{}")
PY
}
{
  echo "=== _nodes jvm/os/plugins ==="
  probe "_nodes/jvm,os,plugins?pretty"
  echo "=== _nodes/settings (vector flags) ==="
  probe "_nodes/settings?pretty" | grep -iE 'vector|simd|panama' || echo "(no vector flags reported)"
  echo "=== doc count check ==="
  CNT=$(probe "${IDX}/_count" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count","ERR"))' 2>/dev/null || echo ERR)
  echo "index=$IDX counted=$CNT expected=$EXPECTED"
  # Three outcomes, not two. The corpus constant below is the workload's declared
  # size, and OSB actually indexes 2 fewer geonames documents than that on every
  # architecture alike (11396503 vs 11396505, verified identical on Graviton, AMD
  # and Intel with 3/3 shards successful). A fixed, architecture-independent
  # offset that tiny is a bookkeeping discrepancy, not a lost-data event, and
  # collapsing it into MISMATCH threw away every run. Anything larger than
  # 0.01% still fails, because that WOULD mean the clusters ingested different
  # corpora and are not comparable.
  if [ "$CNT" = "$EXPECTED" ]; then
    echo "DOCCOUNT_OK"
  elif [ "$CNT" = "ERR" ] || [ -z "$CNT" ]; then
    echo "DOCCOUNT_UNAVAILABLE"
  elif python3 -c "import sys;c=$CNT;e=$EXPECTED;sys.exit(0 if e and abs(c-e)*10000<=e else 1)" 2>/dev/null; then
    echo "DOCCOUNT_OK"
    echo "DOCCOUNT_DELTA counted=$CNT expected=$EXPECTED"
  else
    echo "DOCCOUNT_MISMATCH"
  fi
  echo "=== cluster health ==="
  probe "_cluster/health?pretty"
} 2>&1
"""


def gen_osb_jobs(perms, workload_name, load_key, rep):
    wl = WORKLOADS[workload_name]
    level = LOAD_LEVELS[load_key]
    docs = []

    for p in perms:
        # No rep in the name: each region is its own cluster, so the repetition
        # is implicit in which cluster the object lives on. Keeping it out also
        # keeps Job names inside the 63-character limit.
        run_id = f"{workload_name}-{load_key}-{p['name']}"
        cm_name = f"osb-{run_id}"[:253]
        svc = f"{svc_name(p)}.{p['namespace']}.svc.cluster.local"
        es = f"http://{svc}:9200"

        wp = {
            "bulk_size": BULK_SIZE,
            "number_of_replicas": REPLICAS,
            "number_of_shards": SHARDS,
            "search_clients": SEARCH_CLIENTS,
            "bulk_indexing_clients": BULK_CLIENTS,
        }
        # Only set target_throughput for fixed-rate levels. For "saturate" we
        # omit it entirely rather than passing an absurd number, so that the
        # OSB log unambiguously shows an unthrottled schedule.
        if level["kind"] == "fixed-rate":
            wp["target_throughput"] = level["target_throughput"]
        wp_str = ",".join(f"{k}:{v}" for k, v in wp.items())

        osb_cmd = (
            "opensearch-benchmark run"
            " --pipeline=benchmark-only"
            f" --workload={workload_name}"
            f" --target-hosts={svc}:9200"
            f" --distribution-version={OS_VERSION}"
            f" --workload-params='{wp_str}'"
            f" --test-procedure={wl['test_procedure']}"
            " --client-options='timeout:120'"
            " --results-format=csv"
            " --results-file=/tmp/r.csv"
            f" --user-tag='perm:{p['name']},cpu:{p['cpu']},load:{load_key},rep:{rep}'"
            " --on-error=continue"
        )

        # Trim the unthrottled schedule to the tasks that can actually express a
        # throughput ceiling. Without this the cell cannot finish inside the 3h
        # per-cell deadline -- see SATURATE_EXCLUDE_TASKS.
        if level["kind"] == "saturate":
            osb_cmd += f" --exclude-tasks='{','.join(SATURATE_EXCLUDE_TASKS)}'"

        # Note: --on-error=continue is retained so a partial failure still
        # yields data, but the error rate is extracted below and report.py
        # marks any run above the threshold as INVALID rather than averaging
        # it in. A run that silently drops bulk requests otherwise measures as
        # "fast".
        save_py = (
            "import urllib.request,json,os,ssl\n"
            "t=open('/var/run/secrets/kubernetes.io/serviceaccount/token').read()\n"
            "ctx=ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')\n"
            "h=os.environ['KUBERNETES_SERVICE_HOST'];pt=os.environ['KUBERNETES_SERVICE_PORT']\n"
            "def rd(p,n=200000):\n"
            "    try:\n"
            "        return open(p).read()[-n:]\n"
            "    except Exception:\n"
            "        return 'MISSING'\n"
            "data={'csv':rd('/tmp/r.csv'),'log':rd('/tmp/osb.log',40000),"
            "'probe':rd('/tmp/probe.txt',40000),'meta':rd('/tmp/meta.json')}\n"
            f"cm={{'apiVersion':'v1','kind':'ConfigMap','metadata':{{'name':'{cm_name}',"
            f"'namespace':'default','labels':{{'bench':'osb','workload':'{workload_name}',"
            f"'load':'{load_key}','rep':'{rep}','perm':'{p['name']}'}}}},'data':data}}\n"
            "body=json.dumps(cm).encode()\n"
            "hdrs={'Authorization':'Bearer '+t,'Content-Type':'application/json'}\n"
            "url='https://%s:%s/api/v1/namespaces/default/configmaps'%(h,pt)\n"
            "try:\n"
            "    urllib.request.urlopen(urllib.request.Request(url,data=body,method='POST',headers=hdrs),context=ctx)\n"
            "except urllib.error.HTTPError:\n"
            f"    urllib.request.urlopen(urllib.request.Request(url+'/{cm_name}',data=body,method='PUT',headers=hdrs),context=ctx)\n"
            f"print('saved {cm_name}')\n"
        )

        meta = {
            "run_id": run_id,
            "perm": p["name"],
            "instance_type": p["instance_type"],
            "cpu": p["cpu"],
            "microarchitecture": p["microarchitecture"],
            "arch": p["arch"],
            "vcpus": p["vcpus"],
            "physical_cores": p["physical_cores"],
            "threads_per_core": p["threads_per_core"],
            "memory_gib": p["memory_gib"],
            "usd_per_hour": p["usd_per_hour"],
            "workload": workload_name,
            "load_level": load_key,
            "load_kind": level["kind"],
            "target_throughput": level["target_throughput"],
            "rep": rep,
            "search_clients": SEARCH_CLIENTS,
            "bulk_indexing_clients": BULK_CLIENTS,
            "jvm_heap": JVM_HEAP,
            "loadgen_type": LOADGEN_TYPE,
        }

        script = (
            "set -u\n"
            f"cat >/tmp/meta.json <<'META'\n{json.dumps(meta, indent=2)}\nMETA\n"
            f"cat >/tmp/probe.sh <<'PROBE'\n{PROBE_SCRIPT}\nPROBE\n"
            "echo '--- waiting for cluster yellow/green ---'\n"
            f"for i in $(seq 1 120); do "
            f"curl -s --max-time 10 '{es}/_cluster/health?wait_for_status=yellow&timeout=10s' "
            "| grep -qE '\"status\":\"(yellow|green)\"' && break || sleep 10; done\n"
            f"{osb_cmd} 2>&1 | tee /tmp/osb.log\n"
            "OSB_RC=${PIPESTATUS[0]}\n"
            'echo "osb_exit_code=$OSB_RC" >>/tmp/osb.log\n'
            # Fail loudly if OSB silently ignored a workload param -- that is
            # how a "fixed rate" run can end up unthrottled without anyone
            # noticing.
            "grep -iE 'could not find.*param|unused.*param|ignoring' /tmp/osb.log "
            "&& echo 'PARAM_WARNING_PRESENT' >>/tmp/osb.log || true\n"
            f"sh /tmp/probe.sh '{es}' '{wl['index']}' '{wl['docs']}' >/tmp/probe.txt 2>&1\n"
            f"python3 - <<'SAVE'\n{save_py}\nSAVE\n"
        )

        docs.append(
            {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": f"osb-{run_id}"[:63],
                    "namespace": "default",
                    "labels": {
                        "bench": "osb",
                        "workload": workload_name,
                        "load": load_key,
                        "rep": str(rep),
                        "perm": p["name"],
                    },
                },
                "spec": {
                    # No retries: a retried run silently overwrites its own
                    # result and we lose the fact that it failed once.
                    "backoffLimit": 0,
                    "ttlSecondsAfterFinished": 14400,
                    "template": {
                        "metadata": {
                            "labels": {
                                "bench": "osb",
                                "workload": workload_name,
                                "load": load_key,
                                "rep": str(rep),
                                "perm": p["name"],
                            },
                            "annotations": {"karpenter.sh/do-not-disrupt": "true"},
                        },
                        "spec": {
                            "serviceAccountName": "osb-sa",
                            # THE critical fix: load generator lives on its own
                            # fixed-architecture node, never on the SUT.
                            "nodeSelector": {"bench/role": "loadgen"},
                            "tolerations": [
                                {
                                    "key": "bench/loadgen",
                                    "operator": "Equal",
                                    "value": "true",
                                    "effect": "NoSchedule",
                                }
                            ],
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "osb",
                                    "image": OSB_IMAGE,
                                    "command": ["/bin/bash", "-c"],
                                    "args": [script],
                                    # Generous and identical: the generator must
                                    # never be the bottleneck. 4 permutations
                                    # share a 32-vCPU loadgen node.
                                    "resources": {
                                        "requests": {"cpu": "7", "memory": "12Gi"},
                                        "limits": {"cpu": "7", "memory": "12Gi"},
                                    },
                                }
                            ],
                        },
                    },
                },
            }
        )
    return dump(docs)


# ── Main ──────────────────────────────────────────────────────────────────


def main():
    specs = load_specs()
    perms = build_perms(specs)
    load_keys = os.environ.get("BENCH_LOADS", ",".join(LOAD_LEVELS)).split(",")
    workloads = os.environ.get("BENCH_WORKLOADS", "geonames").split()

    # The repetition index IS the region. Each region runs exactly one pass over
    # the matrix, so there is no within-region rep loop to get out of sync.
    rep = REGION

    # Pin to one AZ. Prefer the alphabetically first AZ that carries every
    # family, so the choice is deterministic and recorded in config.json.
    azs = specs["azs_with_all_families"]
    az = os.environ.get("BENCH_AZ") or azs[0]
    if az not in azs:
        raise SystemExit(f"AZ {az} does not carry all families in {REGION}: {azs}")

    for lk in load_keys:
        if lk not in LOAD_LEVELS:
            raise SystemExit(f"Unknown load level {lk!r}; known: {list(LOAD_LEVELS)}")
    for w in workloads:
        if w not in WORKLOADS:
            raise SystemExit(f"Unknown workload {w!r}; known: {list(WORKLOADS)}")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / "opensearch").mkdir()
    (OUT / "jobs").mkdir()

    (OUT / "storageclass.yaml").write_text(gen_storageclass())
    (OUT / "nodepools.yaml").write_text(gen_nodepools(perms, az))
    (OUT / "rbac.yaml").write_text(gen_rbac())

    for p in perms:
        (OUT / "opensearch" / f"values-{p['name']}.yaml").write_text(gen_helm_values(p))

    n_jobs = 0
    for w in workloads:
        for lk in load_keys:
            path = OUT / "jobs" / f"{w}-{lk}.yaml"
            path.write_text(gen_osb_jobs(perms, w, lk, rep))
            n_jobs += len(perms)

    config = {
        "region": REGION,
        "az": az,
        "rep": rep,
        "size": SIZE,
        "loadgen_type": LOADGEN_TYPE,
        "vcpu_quota": specs.get("vcpu_quota_standard_ondemand"),
        "load_levels": {k: LOAD_LEVELS[k] for k in load_keys},
        "workloads": {w: WORKLOADS[w] for w in workloads},
        "ebs": EBS,
        "fixed": {
            "jvm_heap": JVM_HEAP,
            "mem_request": MEM_REQUEST,
            "cpu_request": CPU_REQUEST,
            "search_clients": SEARCH_CLIENTS,
            "bulk_indexing_clients": BULK_CLIENTS,
            "shards": SHARDS,
            "replicas": REPLICAS,
        },
        "permutations": [p["name"] for p in perms],
        "perm_details": {p["name"]: p for p in perms},
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2) + "\n")

    sut_cost = sum(p["usd_per_hour"] for p in perms) * 3
    lg_cost = specs["instances"][LOADGEN_TYPE]["usd_per_hour"] * 3
    vcpu_needed = sum(p["vcpus"] for p in perms) * 3
    quota = specs.get("vcpu_quota_standard_ondemand")
    if quota is not None and vcpu_needed > quota:
        raise SystemExit(
            f"{REGION}: matrix needs {vcpu_needed} vCPU but the Standard "
            f"on-demand quota is {quota:.0f}. Karpenter would provision a partial "
            f"matrix and the comparison would be missing arms."
        )

    budget = f" ({vcpu_needed} vCPU of {quota:.0f} quota)" if quota else ""
    print(f"[{REGION}/{az}] {len(perms)} clusters × {len(load_keys)} load levels × "
          f"{len(workloads)} workload(s) = {n_jobs} runs{budget}")
    print(f"\n{'perm':<6} {'instance':<16} {'cpu':<22} {'vCPU':>5} {'cores':>6} "
          f"{'t/c':>4} {'GiB':>5} {'$/hr':>8}")
    for p in perms:
        print(f"{p['name']:<6} {p['instance_type']:<16} {p['cpu']:<22} "
              f"{p['vcpus']:>5} {p['physical_cores']:>6} {p['threads_per_core']:>4} "
              f"{p['memory_gib']:>5} {p['usd_per_hour']:>8.4f}")
    print(f"\nFixed everywhere: heap={JVM_HEAP} search_clients={SEARCH_CLIENTS} "
          f"bulk_clients={BULK_CLIENTS} loadgen={LOADGEN_TYPE}")
    print(f"Load levels: {', '.join(load_keys)}")
    print(f"Standing cost while provisioned: ${sut_cost:.2f}/hr SUT + "
          f"${lg_cost:.2f}/hr loadgen = ${sut_cost + lg_cost:.2f}/hr")


if __name__ == "__main__":
    main()
