"""为显式集群创建分离的NATS凭据；复用已有值，不在输出或命令参数中暴露密码。"""

import base64
import json
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """只更新指定Secret；Helm部署和资源初始化由后续显式步骤完成。"""
    target = [
        "--kubeconfig",
        os.environ["M1_KUBECONFIG"],
        "--context",
        os.environ["M1_CONTEXT"],
        "--namespace",
        os.environ["M1_NAMESPACE"],
    ]
    subprocess.run(["bash", str(ROOT / "scripts/check-target.sh"), *target], check=True, timeout=60)
    name = os.environ["M1_MESSAGING_SECRET"]
    response = subprocess.run(
        ["kubectl", *target, "get", "secret", name, "--ignore-not-found", "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    data = json.loads(response.stdout)["data"] if response.stdout.strip() else {}
    # E01-02的token改作维护密码，运行账号获得独立随机密码。
    for key in ("maintenance-password", "app-password"):
        if key not in data:
            data[key] = (
                data.get("token")
                if key == "maintenance-password" and data.get("token")
                else base64.b64encode(secrets.token_urlsafe(32).encode()).decode()
            )
    body = {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "Opaque",
        "metadata": {"name": name, "namespace": os.environ["M1_NAMESPACE"]},
        "data": data,
    }
    # stdin传输，禁止shell拼接；不把Secret放到仓库或日志中。
    subprocess.run(
        ["kubectl", *target, "apply", "-f", "-"],
        input=json.dumps(body),
        text=True,
        check=True,
        timeout=20,
    )
    print("Messaging credentials prepared; existing passwords retained")


if __name__ == "__main__":
    main()
