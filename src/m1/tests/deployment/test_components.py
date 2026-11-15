"""Opt-in integration checks. Restarts ONLY the three named M1 test releases."""

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import time
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
ENABLED = os.environ.get("M1_COMPONENT_TESTS") == "1"


def nats_request(port, token, subject, body):
    """One NATS request using the documented text protocol, no client dependency."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        with connection.makefile("rwb", buffering=0) as wire:
            if not wire.readline().startswith(b"INFO "):
                raise RuntimeError("Missing NATS greeting")
            inbox = "_INBOX.e0102." + uuid.uuid4().hex
            payload = json.dumps(body).encode()
            wire.write(b"CONNECT " + json.dumps({"auth_token": token}).encode() + b"\r\n")
            wire.write(f"SUB {inbox} 1\r\n".encode())
            wire.write(f"PUB {subject} {inbox} {len(payload)}\r\n".encode() + payload + b"\r\n")
            while True:
                line = wire.readline()
                if not line or line.startswith(b"-ERR"):
                    raise RuntimeError("NATS refused or closed the request")
                if line == b"PING\r\n":
                    wire.write(b"PONG\r\n")
                elif line.startswith(b"MSG "):
                    length = int(line.split()[-1])
                    # Buffered reader can return a short chunk; read the whole frame.
                    data = b""
                    while len(data) < length + 2:
                        chunk = wire.read(length + 2 - len(data))
                        if not chunk:
                            raise RuntimeError("Incomplete NATS response")
                        data += chunk
                    result = json.loads(data[:-2])
                    if "error" in result:
                        raise RuntimeError(str(result["error"]))
                    return result


@unittest.skipUnless(ENABLED, "Set M1_COMPONENT_TESTS=1 on the isolated test cluster")
class ChartTests(unittest.TestCase):
    def render(self, release, chart, values, extra=()):
        result = subprocess.run(["helm", f"--kubeconfig={os.environ['M1_KUBECONFIG']}",
                                 f"--kube-context={os.environ['M1_CONTEXT']}",
                                 f"--namespace={os.environ['M1_NAMESPACE']}", "template", release,
                                 str(chart), "-f", str(values), "--no-hooks", "--skip-tests", *extra],
                                capture_output=True, text=True, check=True, timeout=30)
        checked = subprocess.run(["kubectl", f"--kubeconfig={os.environ['M1_KUBECONFIG']}",
                                  f"--context={os.environ['M1_CONTEXT']}",
                                  f"--namespace={os.environ['M1_NAMESPACE']}", "create",
                                  "--dry-run=client", "-f", "-", "-o", "json"],
                                 input=result.stdout, capture_output=True, text=True, check=True, timeout=30)
        resources, remaining = [], checked.stdout.strip()
        decoder = json.JSONDecoder()
        while remaining:
            data, end = decoder.raw_decode(remaining)
            resources.extend(data.get("items", [data]))
            remaining = remaining[end:].lstrip()
        return resources

    def test_rendered_boundaries_and_required_configuration(self):
        values = ROOT / "deploy/environments/local-wsl"
        vendor = Path(os.environ["M1_CHART_CACHE"])
        for name, chart in [("postgres", ROOT / "deploy/helm/postgres"),
                            ("temporal", vendor / "temporal-1.8.0.tgz"),
                            ("nats", vendor / "nats-2.15.2.tgz")]:
            resources = self.render("deermind-" + name, chart, values / (name + ".values.yaml"))
            workloads = [r for r in resources if r["kind"] in ("Deployment", "StatefulSet")]
            self.assertEqual(len(workloads), 4 if name == "temporal" else 1)
            self.assertFalse(any(r["kind"] in ("Secret", "Job", "Pod") for r in resources))
            for resource in workloads:
                self.assertEqual(resource["spec"]["replicas"], 1)
                for container in resource["spec"]["template"]["spec"]["containers"]:
                    self.assertIn("sha256:", container["image"])
                    self.assertIn("memory", container["resources"]["limits"])
            if name == "temporal":
                configs = "\n".join(str(r.get("data", {})) for r in resources if r["kind"] == "ConfigMap")
                self.assertIn("connectProtocol: tcp", configs)
        bootstrap = self.render("deermind-postgres", ROOT / "deploy/helm/postgres",
                                values / "postgres.values.yaml",
                                ("--set", "bootstrap.enabled=true", "--set", "bootstrap.runId=validation"))
        script = bootstrap[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]
        self.assertIn("DO $ownership$", script)
        self.assertNotIn("DO $$", script)  # kubelet reduces $$ in container args.
        with self.assertRaises(subprocess.CalledProcessError):
            self.render("bad-postgres", ROOT / "deploy/helm/postgres", values / "postgres.values.yaml",
                        ("--set", "image="))


@unittest.skipUnless(ENABLED, "Set M1_COMPONENT_TESTS=1 on the isolated test cluster")
class ComponentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target = [f"--kubeconfig={os.environ['M1_KUBECONFIG']}",
                      f"--context={os.environ['M1_CONTEXT']}",
                      f"--namespace={os.environ['M1_NAMESPACE']}"]
        cls.run_id = uuid.uuid4().hex[:8]
        cls.tools = "e0102-tools-" + cls.run_id
        cls.node = os.environ["M1_TEST_NODE"]
        cls.passwords = json.loads(cls.kube("get", "secret", "deermind-postgres", "-o", "json"))["data"]
        cls.token = base64.b64decode(json.loads(cls.kube("get", "secret", "deermind-nats", "-o", "json"))["data"]["token"]).decode()
        image = "docker.io/temporalio/admin-tools:1.32.2@sha256:4a95866efba29d7e17ab012df5232795e8b0ad0f7d5f9d1ec4df321f7792a754"
        cls.create_pod(cls.tools, image, ["sleep", "3600"])
        cls.addClassCleanup(cls.kube, "delete", "pod", cls.tools, "--ignore-not-found", "--wait=false")
        cls.kube("wait", "--for=condition=Ready", "pod/" + cls.tools, "--timeout=60s")

    @classmethod
    def kube(cls, *args, data=None, check=True):
        result = subprocess.run(["kubectl", *cls.target, *args], input=data,
                                text=True, capture_output=True, timeout=330)
        if check and result.returncode:
            # Never print stdin, which may contain a credential for a SQL probe.
            raise RuntimeError(f"kubectl {args[:3]} failed: {result.stderr.strip()}")
        return result.stdout.strip() if check else result

    @classmethod
    def create_pod(cls, name, image, command, volumes=None, mounts=None, extra_env=None):
        pod = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name}, "spec": {
            "restartPolicy": "Never", "automountServiceAccountToken": False,
            "nodeSelector": {"kubernetes.io/hostname": cls.node},
            "containers": [{"name": "probe", "image": image, "imagePullPolicy": "IfNotPresent",
                            "command": command, "resources": {
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                                "limits": {"cpu": "500m", "memory": "256Mi"}},
                            "volumeMounts": mounts or [], "env": extra_env or []}],
            "volumes": volumes or []}}
        cls.kube("create", "-f", "-", data=json.dumps(pod))

    @classmethod
    def sql(cls, sql, user="postgres", database="postgres", password_key="postgres-password", wrong=False):
        password = "deliberately-wrong" if wrong else base64.b64decode(cls.passwords[password_key]).decode()
        script = ("export PGPASSWORD=" + shlex.quote(password) + "\n"
                  f"exec psql -X -At -v ON_ERROR_STOP=1 -h deermind-postgres -U {user} -d {database} <<'SQL'\n"
                  + sql + "\nSQL\n")
        return cls.kube("exec", "-i", "deermind-postgres-0", "--", "sh", "-s", data=script, check=False)

    @classmethod
    def temporal(cls, *args, check=True):
        return cls.kube("exec", cls.tools, "--", "temporal", "--address", "deermind-temporal-frontend:7233",
                        "--command-timeout", "120s", "--client-connect-timeout", "10s", *args, check=check)

    @classmethod
    @contextmanager
    def nats_port(cls):
        # Port 0 asks kubectl to allocate a free loopback port.
        with tempfile.TemporaryFile(mode="w+") as log:
            process = subprocess.Popen(["kubectl", *cls.target, "port-forward", "--address=127.0.0.1",
                                        "service/deermind-nats", "0:4222"], stdout=log, stderr=log, text=True)
            try:
                for _ in range(100):
                    log.seek(0)
                    lines = log.read().splitlines()
                    ready = next((line for line in lines if line.startswith("Forwarding from 127.0.0.1:")), None)
                    if ready:
                        yield int(ready.split(":")[1].split()[0])
                        return
                    if process.poll() is not None:
                        raise RuntimeError("Port forwarding failed")
                    time.sleep(0.1)
                raise TimeoutError("Port forwarding did not become ready")
            finally:
                process.terminate()
                process.wait(timeout=10)

    def test_01_postgres_persistence_and_account_isolation(self):
        table = "e0102_" + self.run_id
        result = self.sql(f"CREATE TABLE {table}(value text); INSERT INTO {table} VALUES ('{self.run_id}');")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.addCleanup(self.sql, f"DROP TABLE IF EXISTS {table};")
        self.kube("rollout", "restart", "statefulset/deermind-postgres")
        self.kube("rollout", "status", "statefulset/deermind-postgres", "--timeout=180s")
        self.assertEqual(self.sql(f"SELECT value FROM {table};").stdout.strip(), self.run_id)
        for user, db, key in [("deermind_app", "deermind", "app-password"),
                              ("temporal", "temporal", "temporal-password"),
                              ("temporal_visibility", "temporal_visibility", "visibility-password")]:
            self.assertEqual(self.sql("SELECT 1;", user, db, key).returncode, 0)
            self.assertNotEqual(self.sql("SELECT 1;", user, db, key, wrong=True).returncode, 0)
        self.assertNotEqual(self.sql("SELECT 1;", "temporal", "deermind", "temporal-password").returncode, 0)
        self.assertNotEqual(self.sql("SELECT 1;", "deermind_app", "temporal", "app-password").returncode, 0)
        self.assertNotEqual(self.sql("CREATE TABLE forbidden(id int);", "deermind_app", "deermind", "app-password").returncode, 0)
        self.assertEqual(self.sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public';", database="deermind").stdout.strip(), "0")

    def test_02_nats_persistence_and_authentication(self):
        stream = "E0102_" + self.run_id
        subject = "e0102." + self.run_id
        with self.nats_port() as port:
            with self.assertRaises(RuntimeError):
                nats_request(port, "deliberately-wrong", "$JS.API.INFO", {})
            nats_request(port, self.token, "$JS.API.STREAM.CREATE." + stream,
                         {"name": stream, "subjects": [subject], "storage": "file", "num_replicas": 1,
                          "max_bytes": 1048576, "max_msgs": 10})
            ack = nats_request(port, self.token, subject, {"marker": self.run_id})
            self.assertEqual(ack["seq"], 1)
        self.kube("rollout", "restart", "statefulset/deermind-nats")
        self.kube("rollout", "status", "statefulset/deermind-nats", "--timeout=180s")
        with self.nats_port() as port:
            try:
                result = nats_request(port, self.token, "$JS.API.STREAM.MSG.GET." + stream, {"seq": 1})
                self.assertEqual(json.loads(base64.b64decode(result["message"]["data"])), {"marker": self.run_id})
            finally:
                nats_request(port, self.token, "$JS.API.STREAM.DELETE." + stream, {})

    def test_03_temporal_keeps_workflow_after_restart(self):
        for service in ("frontend", "history", "matching", "worker"):
            self.kube("rollout", "status", "deployment/deermind-temporal-" + service, "--timeout=180s")
        self.temporal("operator", "cluster", "health")
        namespace = "e01-02-validation"
        result = self.temporal("operator", "namespace", "describe", "--namespace", namespace, check=False)
        if result.returncode:
            self.temporal("operator", "namespace", "create", "--namespace", namespace, "--retention", "720h")
        workflow = "e0102-" + self.run_id
        self.temporal("workflow", "start", "--namespace", namespace, "--workflow-id", workflow,
                      "--type", "E01Probe", "--task-queue", "e01-02-validation")
        self.addCleanup(self.temporal, "workflow", "terminate", "--namespace", namespace,
                        "--workflow-id", workflow, "--reason", "E01-02 verification finished")
        self.kube("rollout", "restart", "deployment", "-l", "app.kubernetes.io/instance=deermind-temporal")
        for service in ("frontend", "history", "matching", "worker"):
            self.kube("rollout", "status", "deployment/deermind-temporal-" + service, "--timeout=180s")
        result = self.temporal("workflow", "describe", "--namespace", namespace, "--workflow-id", workflow, "--output", "json")
        info = json.loads(result)["workflowExecutionInfo"]
        self.assertEqual(info["execution"]["workflowId"], workflow)
        self.assertEqual(info["status"], "WORKFLOW_EXECUTION_STATUS_RUNNING")

    def test_04_shared_file_volume_and_missing_secret(self):
        image = "docker.io/rancher/mirrored-library-busybox:1.37.0"
        volumes = [{"name": "files", "persistentVolumeClaim": {"claimName": "deermind-files"}}]
        mounts = [{"name": "files", "mountPath": "/files"}]
        writer, reader = "e0102-writer-" + self.run_id, "e0102-reader-" + self.run_id
        for name in (writer, reader):
            self.create_pod(name, image, ["sleep", "600"], volumes, mounts)
            self.addCleanup(self.kube, "delete", "pod", name, "--ignore-not-found", "--wait=false")
            self.kube("wait", "--for=condition=Ready", "pod/" + name, "--timeout=60s")
        path = "/files/.e0102-" + self.run_id
        self.kube("exec", writer, "--", "sh", "-ec", f"printf '%s' {self.run_id} > {path}")
        self.addCleanup(self.kube, "exec", reader, "--", "rm", "-f", path)
        self.assertEqual(self.kube("exec", reader, "--", "cat", path), self.run_id)
        self.kube("delete", "pod", writer, "--wait=true")
        self.assertEqual(self.kube("exec", reader, "--", "cat", path), self.run_id)
        bad = "e0102-bad-" + self.run_id
        self.create_pod(bad, image, ["sleep", "600"], extra_env=[{
            "name": "MISSING", "valueFrom": {"secretKeyRef": {"name": bad, "key": "not-present"}}}])
        self.addCleanup(self.kube, "delete", "pod", bad, "--ignore-not-found", "--wait=false")
        result = self.kube("wait", "--for=condition=Ready", "pod/" + bad, "--timeout=10s", check=False)
        self.assertNotEqual(result.returncode, 0)
        status = json.loads(self.kube("get", "pod", bad, "-o", "json"))["status"]["containerStatuses"][0]
        self.assertEqual(status["state"]["waiting"]["reason"], "CreateContainerConfigError")


if __name__ == "__main__":
    unittest.main(verbosity=2)
