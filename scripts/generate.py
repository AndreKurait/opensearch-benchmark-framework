#!/usr/bin/env python3
"""Generate K8s manifests for OpenSearch benchmark permutations.

Edit INSTANCES, EBS_TIERS, WORKLOADS below to customize.
Run: python3 scripts/generate.py
"""
import json, os, shutil
from pathlib import Path

import yaml

# ── Permutation axes (edit these) ─────────────────────────────────────────

INSTANCES = {
    "m8g": {"type": "m8g.2xlarge", "cpu": "Graviton4", "arch": "arm64", "family": "m", "price": 0.2450},
    "m8a": {"type": "m8a.2xlarge", "cpu": "AMD Turin",  "arch": "amd64", "family": "m", "price": 0.2682},
    "m8i": {"type": "m8i.2xlarge", "cpu": "Intel Emerald Rapids", "arch": "amd64", "family": "m", "price": 0.2856},
    "c8g": {"type": "c8g.2xlarge", "cpu": "Graviton4", "arch": "arm64", "family": "c", "price": 0.1928},
    "c8a": {"type": "c8a.2xlarge", "cpu": "AMD Turin",  "arch": "amd64", "family": "c", "price": 0.2199},
    "c8i": {"type": "c8i.2xlarge", "cpu": "Intel Emerald Rapids", "arch": "amd64", "family": "c", "price": 0.2380},
    "r8g": {"type": "r8g.2xlarge", "cpu": "Graviton4", "arch": "arm64", "family": "r", "price": 0.3005},
    "r8a": {"type": "r8a.2xlarge", "cpu": "AMD Turin",  "arch": "amd64", "family": "r", "price": 0.3380},
    "r8i": {"type": "r8i.2xlarge", "cpu": "Intel Emerald Rapids", "arch": "amd64", "family": "r", "price": 0.3780},
}

EBS_TIERS = {
    "gp3-default": {"throughput": 125,  "iops": 3000,  "size": "100Gi"},
    "gp3-fast":    {"throughput": 1000, "iops": 10000, "size": "100Gi"},
}

WORKLOADS = {
    "geonames":  {"docs": "11.4M", "test_procedure": "append-no-conflicts"},
    "pmc":       {"docs": "574K",  "test_procedure": "append-no-conflicts"},
    "nyc_taxis": {"docs": "165M",  "test_procedure": "append-no-conflicts-index-only"},
    "http_logs": {"docs": "247M",  "test_procedure": "append-no-conflicts-index-only"},
}

JVM_HEAP       = {"m": "4g", "c": "2g", "r": "8g"}
MEM_REQUEST    = {"m": "12Gi", "c": "6Gi", "r": "24Gi"}
SEARCH_CLIENTS = {"m": 4, "c": 2, "r": 8}
OS_VERSION     = "3.5.0"

OSB_IMAGE = os.environ.get("OSB_IMAGE", "public.ecr.aws/opensearchproject/opensearch-benchmark:latest")
OUT = Path(__file__).resolve().parent.parent / "k8s" / "generated"

# ── Helpers ───────────────────────────────────────────────────────────────

def perm_id(inst_key, ebs_key):
    return f"{inst_key}-{ebs_key}"

def ns_for(perm):
    return f"os-{perm}"

def dump(docs):
    return "---\n".join(yaml.dump(d, default_flow_style=False, sort_keys=False) for d in docs)

def build_perms():
    perms = []
    for ik, inst in INSTANCES.items():
        for ek, ebs in EBS_TIERS.items():
            pid = perm_id(ik, ek)
            perms.append({
                "name": pid, "namespace": ns_for(pid),
                "instance_key": ik, "instance_type": inst["type"],
                "cpu": inst["cpu"], "arch": inst["arch"],
                "family": inst["family"], "price": inst["price"],
                "ebs_key": ek, "ebs_throughput": ebs["throughput"],
                "ebs_iops": ebs["iops"], "ebs_size": ebs["size"],
                "jvm_heap": JVM_HEAP[inst["family"]],
                "search_clients": SEARCH_CLIENTS[inst["family"]],
            })
    return perms

# ── Generators ────────────────────────────────────────────────────────────

def gen_storageclasses():
    return dump([{
        "apiVersion": "storage.k8s.io/v1", "kind": "StorageClass",
        "metadata": {"name": k},
        "provisioner": "ebs.csi.eks.amazonaws.com",
        "volumeBindingMode": "WaitForFirstConsumer",
        "reclaimPolicy": "Delete",
        "parameters": {"type": "gp3", "throughput": str(t["throughput"]), "iops": str(t["iops"])},
    } for k, t in EBS_TIERS.items()])

def gen_nodepools(perms):
    return dump([{
        "apiVersion": "karpenter.sh/v1", "kind": "NodePool",
        "metadata": {"name": p["name"]},
        "spec": {
            "template": {
                "metadata": {"labels": {"bench/perm": p["name"]}},
                "spec": {
                    "nodeClassRef": {"group": "eks.amazonaws.com", "kind": "NodeClass", "name": "default"},
                    "requirements": [
                        {"key": "node.kubernetes.io/instance-type", "operator": "In", "values": [p["instance_type"]]},
                        {"key": "karpenter.sh/capacity-type", "operator": "In", "values": ["on-demand"]},
                    ],
                },
            },
            "limits": {"cpu": "32"},
            "disruption": {"consolidateAfter": "Never", "budgets": [{"nodes": "0"}]},
        },
    } for p in perms])

def gen_rbac():
    return dump([
        {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "osb-sa", "namespace": "default"}},
        {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role",
         "metadata": {"name": "osb-writer", "namespace": "default"},
         "rules": [{"apiGroups": [""], "resources": ["configmaps"], "verbs": ["create","update","patch","get"]}]},
        {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding",
         "metadata": {"name": "osb-writer", "namespace": "default"},
         "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "osb-writer"},
         "subjects": [{"kind": "ServiceAccount", "name": "osb-sa", "namespace": "default"}]},
    ])

def gen_helm_values(p):
    return yaml.dump({
        "clusterName": p["name"],
        "nodeGroup": "master",
        "replicas": 3,
        "roles": ["master","ingest","data","remote_cluster_client"],
        "resources": {"requests": {"memory": MEM_REQUEST[p["family"]], "cpu": "6"}},
        "opensearchJavaOpts": f"-Xms{p['jvm_heap']} -Xmx{p['jvm_heap']}",
        "persistence": {"enabled": True, "size": p["ebs_size"], "storageClass": p["ebs_key"]},
        "extraEnvs": [{"name": "DISABLE_SECURITY_PLUGIN", "value": "true"}],
        "config": {"opensearch.yml": f"cluster.name: {p['name']}\nnetwork.host: 0.0.0.0\nplugins.security.disabled: true\n"},
        "nodeSelector": {"bench/perm": p["name"]},
        "antiAffinity": "soft",
        "protocol": "http",
        "sysctlInit": {"enabled": True},
        "startupProbe": {"tcpSocket": {"port": 9200}, "initialDelaySeconds": 30, "periodSeconds": 10, "failureThreshold": 30},
    }, default_flow_style=False, sort_keys=False)

def gen_osb_jobs(perms, workload_name):
    wl = WORKLOADS[workload_name]
    docs = []
    for p in perms:
        cm_name = f"osb-{workload_name}-{p['name']}"
        svc = f"opensearch-cluster-master.{p['namespace']}.svc.cluster.local"
        clients = p["search_clients"]
        wp = f"bulk_size:5000,number_of_replicas:1,number_of_shards:3,target_throughput:10000,search_clients:{clients},bulk_indexing_clients:{clients}"

        save_cmd = (
            "python3 -c \""
            "import urllib.request,json,os,ssl;"
            "t=open('/var/run/secrets/kubernetes.io/serviceaccount/token').read();"
            "ctx=ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt');"
            "h=os.environ['KUBERNETES_SERVICE_HOST'];p=os.environ['KUBERNETES_SERVICE_PORT'];"
            "csv=open('/tmp/r.csv').read() if os.path.exists('/tmp/r.csv') else 'MISSING';"
            "log=open('/tmp/osb.log').read()[-12000:] if os.path.exists('/tmp/osb.log') else 'MISSING';"
            f"cm=json.dumps({{'apiVersion':'v1','kind':'ConfigMap','metadata':{{'name':'{cm_name}','namespace':'default','labels':{{'bench':'osb','workload':'{workload_name}'}}}},'data':{{'csv':csv,'log':log}}}}).encode();"
            "hdrs={'Authorization':f'Bearer {t}','Content-Type':'application/json'};"
            f"url=f'https://{{h}}:{{p}}/api/v1/namespaces/default/configmaps';"
            "req=urllib.request.Request(url,data=cm,method='POST',headers=hdrs);"
            "try: urllib.request.urlopen(req,context=ctx)\n"
            "except urllib.error.HTTPError:"
            f" urllib.request.urlopen(urllib.request.Request(url+'/{cm_name}',data=cm,method='PUT',headers=hdrs),context=ctx);"
            f"print('Saved {cm_name}')"
            "\""
        )

        cmd = (
            f"opensearch-benchmark run "
            f"--pipeline=benchmark-only "
            f"--workload={workload_name} "
            f"--target-hosts=http://{svc}:9200 "
            f"--distribution-version={OS_VERSION} "
            f"--workload-params='{wp}' "
            f"--test-procedure={wl['test_procedure']} "
            f"--client-options='timeout:120' "
            f"--on-error=continue "
            f"--results-format=csv "
            f"--results-file=/tmp/r.csv "
            f"2>&1 | tee /tmp/osb.log; "
            f"{save_cmd}"
        )

        docs.append({
            "apiVersion": "batch/v1", "kind": "Job",
            "metadata": {"name": f"osb-{workload_name}-{p['name']}", "namespace": "default",
                         "labels": {"bench": "osb", "workload": workload_name, "perm": p["name"]}},
            "spec": {
                "backoffLimit": 2, "ttlSecondsAfterFinished": 7200,
                "template": {
                    "metadata": {"labels": {"bench": "osb", "workload": workload_name, "perm": p["name"]},
                                 "annotations": {"karpenter.sh/do-not-disrupt": "true"}},
                    "spec": {
                        "serviceAccountName": "osb-sa",
                        "nodeSelector": {"bench/perm": p["name"]},
                        "restartPolicy": "OnFailure",
                        "containers": [{
                            "name": "osb", "image": OSB_IMAGE,
                            "command": ["/bin/sh", "-c"], "args": [cmd],
                            "resources": {"requests": {"cpu": "1", "memory": "4Gi"}, "limits": {"cpu": "2", "memory": "6Gi"}},
                        }],
                    },
                },
            },
        })
    return dump(docs)

# ── Main ──────────────────────────────────────────────────────────────────

def main():
    perms = build_perms()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / "opensearch").mkdir()

    (OUT / "storageclasses.yaml").write_text(gen_storageclasses())
    (OUT / "nodepools.yaml").write_text(gen_nodepools(perms))
    (OUT / "rbac.yaml").write_text(gen_rbac())

    for p in perms:
        (OUT / "opensearch" / f"values-{p['name']}.yaml").write_text(gen_helm_values(p))

    for wl_name in WORKLOADS:
        (OUT / f"osb-jobs-{wl_name}.yaml").write_text(gen_osb_jobs(perms, wl_name))

    config = {"instances": INSTANCES, "ebs_tiers": EBS_TIERS, "workloads": WORKLOADS,
              "permutations": [p["name"] for p in perms], "perm_details": perms}
    (OUT / "config.json").write_text(json.dumps(config, indent=2))

    print(f"Generated {len(perms)} permutations × {len(WORKLOADS)} workloads into {OUT}")
    for p in perms:
        print(f"  {p['name']:30s} {p['instance_type']:20s} {p['ebs_key']:12s} heap={p['jvm_heap']}")
    print(f"\nWorkloads: {', '.join(WORKLOADS.keys())}")

if __name__ == "__main__":
    main()
