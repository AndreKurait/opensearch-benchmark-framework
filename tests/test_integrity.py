import ast
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from scripts import generate, report


class ReportTests(unittest.TestCase):
    def test_missing_and_service_time_are_not_latency(self):
        metrics = {("50th percentile service time", "term"): (3, "ms")}
        self.assertEqual(report.measurement(metrics, "50th percentile latency", "term", "ms"), "—")
        self.assertEqual(report.measurement({}, "Max Throughput", "term", "ops/s"), "—")

    def test_zero_and_units_remain_distinct_from_missing(self):
        metrics = {("error rate", "term"): (0, "%")}
        self.assertEqual(report.measurement(metrics, "error rate", "term", "%"), "0.00 %")
        self.assertEqual(report.measurement(metrics, "error rate", "term", "ms"), "—")

    def test_nonfinite_negative_and_conflicting_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.csv"
            path.write_text("Metric,Task,Value,Unit\nBad,a,nan,ms\nBad,b,inf,ms\nBad,c,-1,ms\nGood,d,0,ms\n")
            self.assertEqual(report.parse_csv(path), {("Good", "d"): (0, "ms")})
            path.write_text("Metric,Task,Value,Unit\nTime,a,1,ms\nTime,a,2,ms\n")
            with self.assertRaisesRegex(ValueError, "conflicting"):
                report.parse_csv(path)

    def test_partial_index_only_results_do_not_invent_cpu_winner(self):
        permutations = generate.build_perms()[:2]
        config = {"permutations": [p["name"] for p in permutations], "perm_details": permutations}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workload = root / "nyc_taxis"
            workload.mkdir()
            (workload / f"{permutations[0]['name']}.csv").write_text(
                "Metric,Task,Value,Unit\nCumulative indexing time of primary shards,,12,min\n"
            )
            text = report.report(config, root)
            self.assertIn("**1/2**", text)
            self.assertIn("12.00 min", text)
            self.assertIn("missing/invalid", text)
            self.assertNotIn("advantage", text)
            self.assertNotIn("best", text)

    def test_absent_results_preserve_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text('{"permutations": [], "perm_details": []}')
            output = root / "REPORT.md"
            output.write_text("historical results")
            result = subprocess.run(
                [sys.executable, str(report.ROOT / "scripts/report.py"), "--config", str(config),
                 "--results", str(root), "--output", str(output)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), "historical results")


class JobTests(unittest.TestCase):
    def job(self):
        permutation = generate.build_perms()[0]
        return permutation, next(yaml.safe_load_all(generate.gen_osb_jobs([permutation], "geonames")))

    def test_target_matches_helm_cluster_name(self):
        permutation, job = self.job()
        values = yaml.safe_load(generate.gen_helm_values(permutation))
        command = job["spec"]["template"]["spec"]["containers"][0]["args"][0]
        self.assertIn(f"http://{values['clusterName']}-{values['nodeGroup']}.{permutation['namespace']}.svc.cluster.local:9200", command)

    def test_all_default_workloads_have_valid_matching_resource_names(self):
        for workload in generate.WORKLOADS:
            for job in yaml.safe_load_all(generate.gen_osb_jobs(generate.build_perms(), workload)):
                name = job["metadata"]["name"]
                self.assertLessEqual(len(name), 63)
                self.assertIsNotNone(re.fullmatch(r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?", name))
                self.assertEqual(job["metadata"]["labels"]["workload"], workload)
                command = job["spec"]["template"]["spec"]["containers"][0]["args"][0]
                self.assertIn(f"--workload={workload} ", command)
                words = shlex.split(command)
                uploader = words[words.index("python3") + 2]
                self.assertIn(f"'name': {name!r}", uploader)

    def test_generated_uploader_is_valid_python(self):
        _, job = self.job()
        command = job["spec"]["template"]["spec"]["containers"][0]["args"][0]
        words = shlex.split(command)
        code = words[words.index("python3") + 2]
        ast.parse(code)
        self.assertIn("error.code != 409", code)
        self.assertIn("'exit_code'", code)

    def test_benchmark_failure_survives_successful_log_upload(self):
        _, job = self.job()
        command = job["spec"]["template"]["spec"]["containers"][0]["args"][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, body in [("opensearch-benchmark", "echo benchmark-failed; exit 42"),
                               ("python3", "exit 0")]:
                script = root / name
                script.write_text("#!/bin/sh\n" + body + "\n")
                script.chmod(0o755)
            command = command.replace("/tmp/osb.log", str(root / "osb.log"))
            result = subprocess.run(
                ["/bin/sh", "-c", command], capture_output=True, text=True,
                env={**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"]},
            )
            self.assertEqual(result.returncode, 42)
            self.assertIn("benchmark-failed", result.stdout)

    def test_job_cannot_retry_into_dirty_index_or_run_forever(self):
        _, job = self.job()
        self.assertEqual(job["spec"]["backoffLimit"], 0)
        self.assertGreater(job["spec"]["activeDeadlineSeconds"], 0)
        self.assertEqual(job["spec"]["template"]["spec"]["restartPolicy"], "Never")

    def test_invalid_cli_arguments_fail_before_infrastructure(self):
        script = report.ROOT / "scripts/run-all.sh"
        for arguments in [["--workloads"], ["--workloads", "--skip-infra"], ["--unexpected"]]:
            result = subprocess.run(["bash", str(script), *arguments], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("STEP 1", result.stdout)


class ShellTests(unittest.TestCase):
    def fixture(self, root, workload="geonames"):
        """Copy scripts into a scratch tree; every kubectl invocation is a local stub."""
        scripts = root / "scripts"
        scripts.mkdir()
        for name in ["run.sh", "collect.sh"]:
            shutil.copyfile(report.ROOT / "scripts" / name, scripts / name)
        (scripts / "report.py").write_text("print('Offline report stub')\n")
        generated = root / "k8s/generated"
        generated.mkdir(parents=True)
        permutations = generate.build_perms()[:2]
        (generated / "config.json").write_text(json.dumps({
            "permutations": [item["name"] for item in permutations]
        }))
        (generated / f"osb-jobs-{workload}.yaml").write_text(
            generate.gen_osb_jobs(permutations, workload)
        )
        commands = root / "bin"
        commands.mkdir()
        kubectl = commands / "kubectl"
        kubectl.write_text(f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ["MOCK_COMMAND_LOG"]).open("a") as log:
    log.write(json.dumps(args) + "\\n")
if "exec" in args:
    namespace = args[args.index("-n") + 1]
    sys.exit(1 if namespace == os.environ.get("MOCK_CLEANUP_FAILURE") else 0)
if args[:2] == ["get", "jobs"]:
    print(json.dumps({{"items": [
        {{"status": {{"conditions": [{{"type": "Complete", "status": "True"}}]}}}},
        {{"status": {{"conditions": [{{"type": "Complete", "status": "True"}}]}}}}
    ]}}))
elif args[:2] == ["get", "cm"]:
    if args[-1] == "jsonpath={{.data.exit_code}}":
        print("0", end="")
    elif args[-1] == "jsonpath={{.data.csv}}":
        print("Metric,Task,Value,Unit\\nCumulative indexing time of primary shards,,1,min")
    elif args[-1] == "jsonpath={{.data.log}}":
        print("offline test")
    else:
        raise SystemExit("Unexpected ConfigMap request")
elif args[0] not in ["delete", "apply"]:
    raise SystemExit("Unexpected kubectl request")
""")
        kubectl.chmod(0o755)
        return {
            **os.environ,
            "PATH": os.pathsep.join([str(commands), str(Path(sys.executable).parent), os.environ["PATH"]]),
            "MOCK_COMMAND_LOG": str(root / "commands.jsonl"),
        }, permutations

    def commands(self, root):
        return [json.loads(line) for line in (root / "commands.jsonl").read_text().splitlines()]

    def test_failed_parallel_cleanup_preserves_results_and_prevents_job_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env, permutations = self.fixture(root)
            # The first cleanup fails and the last succeeds: waiting for only the last PID is unsafe.
            env["MOCK_CLEANUP_FAILURE"] = permutations[0]["namespace"]
            result = subprocess.run(["bash", str(root / "scripts/run.sh"), "geonames"],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Index cleanup failed", result.stderr)
            commands = self.commands(root)
            self.assertEqual(sum("exec" in command for command in commands), 2)
            self.assertFalse(any(command[0] == "apply" for command in commands))
            self.assertFalse(any(command[:2] == ["delete", "cm"] for command in commands))

    def test_previous_job_pods_stop_before_cleanup_and_new_jobs_follow_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env, _ = self.fixture(root)
            result = subprocess.run(["bash", str(root / "scripts/run.sh"), "geonames"],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            commands = self.commands(root)
            self.assertEqual(commands[0][:2], ["delete", "jobs"])
            self.assertIn("--cascade=foreground", commands[0])
            cleanup = [index for index, command in enumerate(commands) if "exec" in command]
            apply = next(index for index, command in enumerate(commands) if command[0] == "apply")
            self.assertTrue(all(index < apply for index in cleanup))
            self.assertIn("geonames complete", result.stdout)

    def test_collector_normalizes_only_resource_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env, permutations = self.fixture(root, workload="nyc_taxis")
            result = subprocess.run(["bash", str(root / "scripts/collect.sh"), "nyc_taxis"],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            names = {command[2] for command in self.commands(root)}
            self.assertEqual(names, {
                generate.result_resource_name("nyc_taxis", item["name"]) for item in permutations
            })
            for item in permutations:
                self.assertTrue((root / "results/nyc_taxis" / f"{item['name']}.csv").is_file())
            self.assertFalse((root / "results/nyc-taxis").exists())


if __name__ == "__main__":
    unittest.main()
