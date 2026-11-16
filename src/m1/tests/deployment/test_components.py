"""验证 E01-02 Chart 边界及基础组件的鉴权、重启持久化和共享卷。

必须显式设置 M1_COMPONENT_TESTS=1 及目标环境。测试会重启本命名空间的
三个 deermind 测试 release；不会安装应用，也不能用于生产环境。
"""

import base64
import json
import os
import shlex
import socket
import subprocess
import tempfile
import time
import unittest
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, overload

ROOT = Path(__file__).resolve().parents[2]
ENABLED = os.environ.get("M1_COMPONENT_TESTS") == "1"

# Kubernetes/Temporal probe responses have vendor-defined shapes, asserted by each test.
# This test-only boundary is not a business DTO or a production input validator.
JsonObject = dict[str, Any]


def nats_request(port: int, password: str, subject: str, body: Mapping[str, object]) -> JsonObject:
    """通过本地转发端口发送一次 NATS 请求，返回解码后的响应。

    仅实现本组探测需要的协议，不替代正式客户端。鉴权拒绝、连接关闭、
    不完整帧或 JetStream 错误均抛 RuntimeError；凭据不得写入错误文本。
    """
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        with connection.makefile("rwb", buffering=0) as wire:
            if not wire.readline().startswith(b"INFO "):
                raise RuntimeError("Missing NATS greeting")

            # 独立回复 inbox 避免并行探测混淆；维护密码只写入连接，不打印。
            inbox = "_INBOX.e0102." + uuid.uuid4().hex
            payload = json.dumps(body).encode()
            wire.write(
                b"CONNECT "
                + json.dumps({"user": "maintenance", "pass": password}).encode()
                + b"\r\n"
            )
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
                    # socket 可能短读；必须读满正文及末尾 CRLF 后才能解码。
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
    """渲染实际 Chart，检查资源边界和缺失配置；不创建渲染出的资源。"""

    def render(
        self, release: str, chart: Path, values: Path, extra: tuple[str, ...] = ()
    ) -> list[JsonObject]:
        """用 Helm 渲染，再由 kubectl 客户端校验并解码资源列表。

        两个命令失败都会抛 CalledProcessError。dry-run 不保存资源；
        kubectl 可能读取 API 发现信息，因此本组仍要求显式测试目标。
        """
        result = subprocess.run(
            [
                "helm",
                f"--kubeconfig={os.environ['M1_KUBECONFIG']}",
                f"--kube-context={os.environ['M1_CONTEXT']}",
                f"--namespace={os.environ['M1_NAMESPACE']}",
                "template",
                release,
                str(chart),
                "-f",
                str(values),
                "--no-hooks",
                "--skip-tests",
                *extra,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        checked = subprocess.run(
            [
                "kubectl",
                f"--kubeconfig={os.environ['M1_KUBECONFIG']}",
                f"--context={os.environ['M1_CONTEXT']}",
                f"--namespace={os.environ['M1_NAMESPACE']}",
                "create",
                "--dry-run=client",
                "-f",
                "-",
                "-o",
                "json",
            ],
            input=result.stdout,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        # kubectl 可输出多个相邻 JSON 对象，不能假设整段 stdout 只有一个对象。
        resources: list[JsonObject] = []
        remaining = checked.stdout.strip()
        decoder = json.JSONDecoder()
        while remaining:
            data, end = decoder.raw_decode(remaining)
            resources.extend(data.get("items", [data]))
            remaining = remaining[end:].lstrip()
        return resources

    def test_rendered_boundaries_and_required_configuration(self) -> None:
        """验证副本、镜像、资源限制及显式初始化边界，拒绝缺失镜像。"""
        values = ROOT / "deploy/environments/local-wsl"
        vendor = Path(os.environ["M1_CHART_CACHE"])
        for name, chart in [
            ("postgres", ROOT / "deploy/helm/postgres"),
            ("temporal", vendor / "temporal-1.8.0.tgz"),
            ("nats", vendor / "nats-2.15.2.tgz"),
        ]:
            resources = self.render("deermind-" + name, chart, values / (name + ".values.yaml"))
            workloads = [
                resource
                for resource in resources
                if resource["kind"] in ("Deployment", "StatefulSet")
            ]
            self.assertEqual(len(workloads), 4 if name == "temporal" else 1)
            self.assertFalse(
                any(resource["kind"] in ("Secret", "Job", "Pod") for resource in resources)
            )
            for resource in workloads:
                self.assertEqual(resource["spec"]["replicas"], 1)
                for container in resource["spec"]["template"]["spec"]["containers"]:
                    self.assertIn("sha256:", container["image"])
                    self.assertIn("memory", container["resources"]["limits"])
            if name == "temporal":
                configs = "\n".join(
                    str(resource.get("data", {}))
                    for resource in resources
                    if resource["kind"] == "ConfigMap"
                )
                self.assertIn("connectProtocol: tcp", configs)

        # 初始化必须是单独调用；PG ownership 块不能使用会被 kubelet 替换的 $$。
        bootstrap = self.render(
            "deermind-postgres",
            ROOT / "deploy/helm/postgres",
            values / "postgres.values.yaml",
            ("--set", "bootstrap.enabled=true", "--set", "bootstrap.runId=validation"),
        )
        script = bootstrap[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]
        self.assertIn("DO $ownership$", script)
        self.assertNotIn("DO $$", script)

        with self.assertRaises(subprocess.CalledProcessError):
            self.render(
                "bad-postgres",
                ROOT / "deploy/helm/postgres",
                values / "postgres.values.yaml",
                ("--set", "image="),
            )


@unittest.skipUnless(ENABLED, "Set M1_COMPONENT_TESTS=1 on the isolated test cluster")
class ComponentsTests(unittest.TestCase):
    """在显式隔离环境中执行组件故障与恢复探测，资源名带本次运行标识。"""

    @classmethod
    def setUpClass(cls) -> None:
        """读取测试凭据并创建工具 Pod；登记清理，不输出 Secret 内容。"""
        cls.target = [
            f"--kubeconfig={os.environ['M1_KUBECONFIG']}",
            f"--context={os.environ['M1_CONTEXT']}",
            f"--namespace={os.environ['M1_NAMESPACE']}",
        ]
        cls.run_id = uuid.uuid4().hex[:8]
        cls.tools = "e0102-tools-" + cls.run_id
        cls.node = os.environ["M1_TEST_NODE"]

        cls.passwords = json.loads(cls.kube("get", "secret", "deermind-postgres", "-o", "json"))[
            "data"
        ]
        cls.nats_password = base64.b64decode(
            json.loads(cls.kube("get", "secret", "deermind-nats", "-o", "json"))["data"][
                "maintenance-password"
            ]
        ).decode()

        image = (
            "docker.io/temporalio/admin-tools:1.32.2@sha256:"
            "4a95866efba29d7e17ab012df5232795e8b0ad0f7d5f9d1ec4df321f7792a754"
        )
        cls.create_pod(cls.tools, image, ["sleep", "3600"])
        cls.addClassCleanup(
            cls.kube, "delete", "pod", cls.tools, "--ignore-not-found", "--wait=false"
        )
        cls.kube("wait", "--for=condition=Ready", "pod/" + cls.tools, "--timeout=60s")

    @classmethod
    @overload
    def kube(cls, *args: str, data: str | None = None, check: Literal[True] = True) -> str: ...

    @classmethod
    @overload
    def kube(
        cls, *args: str, data: str | None = None, check: Literal[False]
    ) -> subprocess.CompletedProcess[str]: ...

    @classmethod
    def kube(
        cls, *args: str, data: str | None = None, check: bool = True
    ) -> str | subprocess.CompletedProcess[str]:
        """在固定测试目标执行命令；check=False 时返回失败结果供断言。

        data 通过 stdin 传递，可能含探测凭据，错误信息只能包含命令摘要。
        超时保留为测试错误，不当成预期的业务拒绝。
        """
        result = subprocess.run(
            ["kubectl", *cls.target, *args], input=data, text=True, capture_output=True, timeout=330
        )
        if check and result.returncode:
            # Never print stdin, which may contain a credential for a SQL probe.
            raise RuntimeError(f"kubectl {args[:3]} failed: {result.stderr.strip()}")
        return result.stdout.strip() if check else result

    @classmethod
    def create_pod(
        cls,
        name: str,
        image: str,
        command: list[str],
        volumes: Sequence[Mapping[str, object]] | None = None,
        mounts: Sequence[Mapping[str, object]] | None = None,
        extra_env: Sequence[Mapping[str, object]] | None = None,
    ) -> None:
        """在指定节点创建有资源上限的探测 Pod，调用方登记对应清理。

        volumes、mounts 和 extra_env 只来自测试固定配置，不接受用户输入。
        """
        pod = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": name},
            "spec": {
                "restartPolicy": "Never",
                "automountServiceAccountToken": False,
                "nodeSelector": {"kubernetes.io/hostname": cls.node},
                "containers": [
                    {
                        "name": "probe",
                        "image": image,
                        "imagePullPolicy": "IfNotPresent",
                        "command": command,
                        "resources": {
                            "requests": {"cpu": "100m", "memory": "128Mi"},
                            "limits": {"cpu": "500m", "memory": "256Mi"},
                        },
                        "volumeMounts": mounts or [],
                        "env": extra_env or [],
                    }
                ],
                "volumes": volumes or [],
            },
        }
        cls.kube("create", "-f", "-", data=json.dumps(pod))

    @classmethod
    def sql(
        cls,
        sql: str,
        user: str = "postgres",
        database: str = "postgres",
        password_key: str = "postgres-password",
        wrong: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """在 PG Pod 内执行测试 SQL；wrong=True 用于验证错误密码会被拒绝。

        账号、库名和 SQL 均来自本文件固定探测。密码经 stdin 注入，
        不放入进程参数；返回码保留给测试断言。
        """
        password = (
            "deliberately-wrong"
            if wrong
            else base64.b64decode(cls.passwords[password_key]).decode()
        )
        script = (
            f"export PGPASSWORD={shlex.quote(password)}\n"
            "exec psql -X -At -v ON_ERROR_STOP=1 -h deermind-postgres "
            f"-U {user} -d {database} <<'SQL'\n"
            f"{sql}\n"
            "SQL\n"
        )
        return cls.kube(
            "exec", "-i", "deermind-postgres-0", "--", "sh", "-s", data=script, check=False
        )

    @classmethod
    @overload
    def temporal(cls, *args: str, check: Literal[True] = True) -> str: ...

    @classmethod
    @overload
    def temporal(cls, *args: str, check: Literal[False]) -> subprocess.CompletedProcess[str]: ...

    @classmethod
    def temporal(cls, *args: str, check: bool = True) -> str | subprocess.CompletedProcess[str]:
        """在工具 Pod 中调用 Temporal CLI，限制连接及命令等待时间。"""
        command = (
            "exec",
            cls.tools,
            "--",
            "temporal",
            "--address",
            "deermind-temporal-frontend:7233",
            "--command-timeout",
            "120s",
            "--client-connect-timeout",
            "10s",
            *args,
        )
        if check:
            return cls.kube(*command)
        return cls.kube(*command, check=False)

    @classmethod
    @contextmanager
    def nats_port(cls) -> Iterator[int]:
        """分配仅监听回环地址的端口转发，并保证退出时终止子进程。

        仅在读到 kubectl 的 ready 输出后交给探测使用；失败或等待超时抛错。
        """
        # 端口 0 由 kubectl 选择空闲端口，避免与其他本机服务争用。
        with tempfile.TemporaryFile(mode="w+") as log:
            process = subprocess.Popen(
                [
                    "kubectl",
                    *cls.target,
                    "port-forward",
                    "--address=127.0.0.1",
                    "service/deermind-nats",
                    "0:4222",
                ],
                stdout=log,
                stderr=log,
                text=True,
            )
            try:
                for _ in range(100):
                    log.seek(0)
                    lines = log.read().splitlines()
                    ready = next(
                        (line for line in lines if line.startswith("Forwarding from 127.0.0.1:")),
                        None,
                    )
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

    def test_01_postgres_persistence_and_account_isolation(self) -> None:
        """确认重启后数据仍在，账号不能越库或越权建表。"""
        table = "e0102_" + self.run_id
        result = self.sql(
            f"CREATE TABLE {table}(value text); INSERT INTO {table} VALUES ('{self.run_id}');"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.addCleanup(self.sql, f"DROP TABLE IF EXISTS {table};")

        # 先证明持久化，再分别检查凭据和账号授权，避免把连接失败误判为权限正确。
        self.kube("rollout", "restart", "statefulset/deermind-postgres")
        self.kube("rollout", "status", "statefulset/deermind-postgres", "--timeout=180s")
        self.assertEqual(self.sql(f"SELECT value FROM {table};").stdout.strip(), self.run_id)

        for user, database, password_key in [
            ("deermind_app", "deermind", "app-password"),
            ("temporal", "temporal", "temporal-password"),
            ("temporal_visibility", "temporal_visibility", "visibility-password"),
        ]:
            self.assertEqual(self.sql("SELECT 1;", user, database, password_key).returncode, 0)
            self.assertNotEqual(
                self.sql("SELECT 1;", user, database, password_key, wrong=True).returncode, 0
            )

        # 正确凭据也不能跨库访问；应用账号不能创建业务表。
        self.assertNotEqual(
            self.sql("SELECT 1;", "temporal", "deermind", "temporal-password").returncode, 0
        )
        self.assertNotEqual(
            self.sql("SELECT 1;", "deermind_app", "temporal", "app-password").returncode, 0
        )
        self.assertNotEqual(
            self.sql(
                "CREATE TABLE forbidden(id int);", "deermind_app", "deermind", "app-password"
            ).returncode,
            0,
        )
        self.assertEqual(
            self.sql(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';",
                database="deermind",
            ).stdout.strip(),
            "0",
        )

    def test_02_nats_persistence_and_authentication(self) -> None:
        """确认错误凭据被拒绝，已确认消息在重启后可读。"""
        stream = "E0102_" + self.run_id
        subject = "e0102." + self.run_id
        with self.nats_port() as port:
            with self.assertRaises(RuntimeError):
                nats_request(port, "deliberately-wrong", "$JS.API.INFO", {})
            nats_request(
                port,
                self.nats_password,
                "$JS.API.STREAM.CREATE." + stream,
                {
                    "name": stream,
                    "subjects": [subject],
                    "storage": "file",
                    "num_replicas": 1,
                    "max_bytes": 1048576,
                    "max_msgs": 10,
                },
            )
            ack = nats_request(port, self.nats_password, subject, {"marker": self.run_id})
            self.assertEqual(ack["seq"], 1)

        # 写入确认与重启后读取使用不同连接，证明消息来自持久卷。
        self.kube("rollout", "restart", "statefulset/deermind-nats")
        self.kube("rollout", "status", "statefulset/deermind-nats", "--timeout=180s")

        with self.nats_port() as port:
            try:
                result = nats_request(
                    port, self.nats_password, "$JS.API.STREAM.MSG.GET." + stream, {"seq": 1}
                )
                self.assertEqual(
                    json.loads(base64.b64decode(result["message"]["data"])), {"marker": self.run_id}
                )
            finally:
                nats_request(port, self.nats_password, "$JS.API.STREAM.DELETE." + stream, {})

    def test_03_temporal_keeps_workflow_after_restart(self) -> None:
        """确认无应用 Worker 时，等待中的测试工作流仍可在重启后查询。"""
        for service in ("frontend", "history", "matching", "worker"):
            self.kube(
                "rollout", "status", "deployment/deermind-temporal-" + service, "--timeout=180s"
            )
        self.temporal("operator", "cluster", "health")

        # 复用专用验证 namespace，每次工作流使用独立 ID。
        namespace = "e01-02-validation"
        result = self.temporal(
            "operator", "namespace", "describe", "--namespace", namespace, check=False
        )
        if result.returncode:
            self.temporal(
                "operator", "namespace", "create", "--namespace", namespace, "--retention", "720h"
            )

        workflow = "e0102-" + self.run_id
        self.temporal(
            "workflow",
            "start",
            "--namespace",
            namespace,
            "--workflow-id",
            workflow,
            "--type",
            "E01Probe",
            "--task-queue",
            "e01-02-validation",
        )
        self.addCleanup(
            self.temporal,
            "workflow",
            "terminate",
            "--namespace",
            namespace,
            "--workflow-id",
            workflow,
            "--reason",
            "E01-02 verification finished",
        )

        # 没有应用 Worker 消费 E01Probe；重启后应仍为 RUNNING，而非已执行完成。
        self.kube(
            "rollout", "restart", "deployment", "-l", "app.kubernetes.io/instance=deermind-temporal"
        )
        for service in ("frontend", "history", "matching", "worker"):
            self.kube(
                "rollout", "status", "deployment/deermind-temporal-" + service, "--timeout=180s"
            )

        result = self.temporal(
            "workflow",
            "describe",
            "--namespace",
            namespace,
            "--workflow-id",
            workflow,
            "--output",
            "json",
        )
        info = json.loads(result)["workflowExecutionInfo"]
        self.assertEqual(info["execution"]["workflowId"], workflow)
        self.assertEqual(info["status"], "WORKFLOW_EXECUTION_STATUS_RUNNING")

    def test_04_shared_file_volume_and_missing_secret(self) -> None:
        """验证两个 Pod 共用文件卷，并确认缺失 Secret 的 Pod 不会就绪。"""
        image = "docker.io/rancher/mirrored-library-busybox:1.37.0"
        volumes = [{"name": "files", "persistentVolumeClaim": {"claimName": "deermind-files"}}]
        mounts = [{"name": "files", "mountPath": "/files"}]
        writer = "e0102-writer-" + self.run_id
        reader = "e0102-reader-" + self.run_id
        for name in (writer, reader):
            self.create_pod(name, image, ["sleep", "600"], volumes, mounts)
            self.addCleanup(self.kube, "delete", "pod", name, "--ignore-not-found", "--wait=false")
            self.kube("wait", "--for=condition=Ready", "pod/" + name, "--timeout=60s")

        # cleanup 按后进先出执行：先删本次文件，再删 reader Pod，不删除 PVC。
        path = "/files/.e0102-" + self.run_id
        self.kube("exec", writer, "--", "sh", "-ec", f"printf '%s' {self.run_id} > {path}")
        self.addCleanup(self.kube, "exec", reader, "--", "rm", "-f", path)
        self.assertEqual(self.kube("exec", reader, "--", "cat", path), self.run_id)
        self.kube("delete", "pod", writer, "--wait=true")
        self.assertEqual(self.kube("exec", reader, "--", "cat", path), self.run_id)

        # 负例必须落在配置缺失，而非网络、镜像拉取等无关故障。
        bad = "e0102-bad-" + self.run_id
        self.create_pod(
            bad,
            image,
            ["sleep", "600"],
            extra_env=[
                {
                    "name": "MISSING",
                    "valueFrom": {"secretKeyRef": {"name": bad, "key": "not-present"}},
                }
            ],
        )
        self.addCleanup(self.kube, "delete", "pod", bad, "--ignore-not-found", "--wait=false")
        result = self.kube(
            "wait", "--for=condition=Ready", "pod/" + bad, "--timeout=10s", check=False
        )
        self.assertNotEqual(result.returncode, 0)
        status = json.loads(self.kube("get", "pod", bad, "-o", "json"))["status"][
            "containerStatuses"
        ][0]
        self.assertEqual(status["state"]["waiting"]["reason"], "CreateContainerConfigError")


if __name__ == "__main__":
    unittest.main(verbosity=2)
