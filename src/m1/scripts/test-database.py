"""在显式集群内验证构建包，避免断连测试影响本机转发通道。

临时Pod通过Secret引用获得测试凭据；只创建随机UUID命名的测试库。
失败返回非零并清理本次Pod，不修改已有业务数据。
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
CONTENT_CASES = ROOT.parent / "mvp_foundation/m1/content-representation/structure-draft-v0.1/cases"
POD_CONTENT_OUTPUT = "/tmp/deermind-content-restored.json"


def main() -> int:
    """核对目标，运行临时测试Pod；任一步失败均返回非零并清理本次Pod。"""
    group = sys.argv[1] if len(sys.argv) == 2 else "database"
    if (
        group
        not in {
            "database",
            "facts",
            "files",
            "reads",
            "rebuild",
            "auth",
            "usage",
            "receipts",
            "delivery",
            "execution",
            "waits",
            "ai",
            "payload",
            "content",
        }
        or len(sys.argv) > 2
    ):
        raise ValueError(
            "Expected database, facts, files, reads, rebuild, "
            "auth, usage, receipts, delivery, execution, waits, ai, payload or content test group"
        )
    target = [
        "kubectl",
        f"--kubeconfig={os.environ['M1_KUBECONFIG']}",
        f"--context={os.environ['M1_CONTEXT']}",
        f"--namespace={os.environ['M1_NAMESPACE']}",
    ]
    subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/check-target.sh"),
            "--kubeconfig",
            os.environ["M1_KUBECONFIG"],
            "--context",
            os.environ["M1_CONTEXT"],
            "--namespace",
            os.environ["M1_NAMESPACE"],
        ],
        check=True,
        timeout=60,
    )
    name = "deermind-db-test-" + uuid4().hex[:12]
    environment: list[dict[str, object]] = [
        {"name": "M1_DB_HOST", "value": os.environ["M1_POSTGRES_RELEASE"]},
        {"name": "M1_DB_PORT", "value": "5432"},
    ]
    for role, key in {
        "ADMIN": "postgres-password",
        "MIGRATION": "migration-password",
        "APP": "app-password",
        "TEMPORAL": "temporal-password",
        "VISIBILITY": "visibility-password",
    }.items():
        environment.append(
            {
                "name": f"M1_TEST_{role}_PASSWORD",
                "valueFrom": {
                    "secretKeyRef": {"name": os.environ["M1_DATABASE_SECRET"], "key": key},
                },
            }
        )
    if group == "delivery":
        environment.extend(
            [
                {"name": "M1_TEST_NATS_ADDRESS", "value": os.environ["M1_TEST_NATS_ADDRESS"]},
                {
                    "name": "M1_TEST_NATS_PASSWORD",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": os.environ["M1_MESSAGING_SECRET"],
                            "key": "maintenance-password",
                        }
                    },
                },
            ]
        )
    if group in {"execution", "waits", "ai", "payload"}:
        environment.extend(
            {"name": name, "value": os.environ[name]}
            for name in ("M1_TEST_TEMPORAL_ADDRESS", "M1_TEST_TEMPORAL_NAMESPACE")
        )
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": name},
        "spec": {
            "restartPolicy": "Never",
            "terminationGracePeriodSeconds": 1,
            "activeDeadlineSeconds": 240,
            "automountServiceAccountToken": False,
            "nodeSelector": {"kubernetes.io/hostname": os.environ["M1_TEST_NODE"]},
            "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001},
            "containers": [
                {
                    "name": "test",
                    "image": os.environ["M1_DATABASE_TEST_IMAGE"],
                    "imagePullPolicy": "IfNotPresent",
                    "command": ["sleep", "240"],
                    "env": environment,
                    "securityContext": {
                        "readOnlyRootFilesystem": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": "500m", "memory": "256Mi"},
                    },
                    "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],
                }
            ],
            "volumes": [{"name": "tmp", "emptyDir": {}}],
        },
    }
    if group in {"files", "payload", "content"}:
        environment.append({"name": "M1_TEST_FILES_ROOT", "value": "/data/files"})
        pod["spec"]["volumes"].append(
            {
                "name": "files",
                "persistentVolumeClaim": {"claimName": os.environ["M1_FILES_CLAIM"]},
            }
        )
        pod["spec"]["containers"][0]["volumeMounts"].append(
            {
                "name": "files",
                "mountPath": "/data/files",
            }
        )
    if group == "content":
        environment.append({"name": "M1_TEST_CONTENT_OUTPUT", "value": POD_CONTENT_OUTPUT})
    if group == "payload":
        # 同一测试容器运行调用端和独立Worker子进程，分别采集峰值。
        pod["spec"]["activeDeadlineSeconds"] = 390
        pod["spec"]["containers"][0]["command"] = ["sleep", "390"]
        pod["spec"]["containers"][0]["resources"] = {
            "requests": {"cpu": "500m", "memory": "512Mi"},
            "limits": {"cpu": "2000m", "memory": "2Gi"},
        }
    subprocess.run(
        [*target, "create", "-f", "-"], input=json.dumps(pod), text=True, check=True, timeout=30
    )
    try:
        subprocess.run(
            [*target, "wait", "--for=condition=Ready", f"pod/{name}", "--timeout=60s"],
            check=True,
            timeout=75,
        )
        fixtures = ROOT / "tests/migrations"
        pattern = {
            "database": "test_database.py",
            "facts": "test_atomic_facts.py",
            "files": "test_file_facts.py",
            "reads": "test_event_reads.py",
            "rebuild": "test_projection_rebuild.py",
            "auth": "test_authentication.py",
            "usage": "test_account_usage.py",
            "receipts": "test_receipts.py",
            "delivery": "test_event_delivery.py",
            "execution": "test_execution.py",
            "waits": "test_waits.py",
            "ai": "test_ai_*.py",
            "payload": "test_payload_codec_integration.py",
            "content": "test_rich_content.py",
        }[group]
        inputs = {path.name: path.read_text(encoding="utf-8") for path in fixtures.glob("*.py")}
        if group == "content":
            # 四个已有结构稿只进临时测试Pod，不复制到镜像或应用数据。
            for case_file in ("C02.json", "C03.json", "C05.json", "C06.json"):
                inputs[case_file] = (CONTENT_CASES / case_file).read_text(encoding="utf-8")
        # 将测试文件放进临时目录；生产包仍只从镜像读取，不挂载源码。
        driver = """
import json
import pathlib
import sys
import tempfile
import unittest

with tempfile.TemporaryDirectory() as directory:
    for name, content in json.load(sys.stdin).items():
        path = pathlib.Path(directory, name)
        path.write_text(content, encoding='utf-8')
    suite = unittest.defaultTestLoader.discover(directory, pattern=sys.argv[1])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
"""
        result = subprocess.run(
            [*target, "exec", "-i", name, "--", "python", "-c", driver, pattern],
            input=json.dumps(inputs),
            text=True,
            timeout=300 if group == "payload" else 150,
        )
        if group == "content" and result.returncode == 0:
            restored = subprocess.run(
                [*target, "exec", name, "--", "cat", POD_CONTENT_OUTPUT],
                capture_output=True,
                check=True,
                timeout=30,
            )
            output = Path(os.environ["M1_TEST_CONTENT_OUTPUT"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(restored.stdout)
        return result.returncode
    finally:
        # 只删除本次创建的Pod，不按选择器或命名空间批量删除。
        subprocess.run(
            [*target, "delete", "pod", name, "--wait=true", "--timeout=30s"], check=True, timeout=45
        )


if __name__ == "__main__":
    raise SystemExit(main())
