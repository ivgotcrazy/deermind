"""一次重置 DeerMind-M1 WSL 开发库。只作用于本机固定集群与当前开发业务库。"""

import argparse
import fcntl
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
WORKER_SCRIPT = ROOT / "deploy/environments/local-wsl/reset/in_cluster.py"
ACCOUNTS = Path("/root/.config/deermind-review-e02/accounts.json")
DB = "deermind_task_text"
POD = "deermind-local-reset"
APPS = ["deployment/deermind-app-api", "deployment/deermind-app-worker"]
KUBE = [
    "kubectl",
    "--kubeconfig=/root/.kube/deermind-m1.yaml",
    "--context=deermind-m1",
    "--namespace=deermind-m1",
    "--request-timeout=6m",
]
CONFIG = {
    "M1_DB_HOST": "deermind-postgres",
    "M1_DB_NAME": DB,
    "M1_DB_USER": "deermind_app",
    "M1_DB_PORT": "5432",
    "M1_NATS_DEPLOYMENT": "local-wsl",
    "M1_NATS_ADDRESS": "nats://deermind-nats:4222",
    "M1_TEMPORAL_ADDRESS": "deermind-temporal-frontend:7233",
    "M1_TEMPORAL_NAMESPACE": "dm-local-wsl",
}
ORIGIN = "http://127.0.0.1:5184"


def kube(*args: str, data: str | None = None, capture: bool = False) -> str:
    result = subprocess.run(
        [*KUBE, *args],
        input=data,
        text=True,
        check=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout or ""


def credentials() -> dict[str, str]:
    """重复重置复用私有凭据文件。首次安装生成随机密码，不把密码写到终端。"""
    if not ACCOUNTS.exists():
        ACCOUNTS.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        initial = {
            key: value
            for role in ("admin", "student")
            for key, value in [
                (role + "_login", role),
                (role + "_password", secrets.token_urlsafe(24)),
            ]
        }
        with os.fdopen(os.open(ACCOUNTS, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
            json.dump(initial, f)
    if ACCOUNTS.stat().st_mode & 0o077:
        raise ValueError("本机凭据文件须仅所有者可读写")
    values = json.loads(ACCOUNTS.read_text())
    for role in ("admin", "student"):
        login, password = values[role + "_login"], values[role + "_password"]
        if not (
            isinstance(login, str)
            and 1 <= len(login.strip()) <= 256
            and isinstance(password, str)
            and 15 <= len(password) <= 128
        ):
            raise ValueError("本机测试账号配置无效")
    if values["admin_login"].strip().casefold() == values["student_login"].strip().casefold():
        raise ValueError("两个测试账号须使用不同登录名")
    return {
        role + suffix: values[role + suffix]
        for role in ("admin", "student")
        for suffix in ("_login", "_password")
    }


def preflight() -> str:
    """验证实际连到的集群、两个写入进程及数据库所有者，再允许停服。"""
    target = kube(
        "config", "view", "--minify", "-o", "jsonpath={.clusters[0].cluster.server}", capture=True
    )
    if target != "https://127.0.0.1:6443" or os.environ.get("WSL_DISTRO_NAME") != "DeerMind-M1":
        raise RuntimeError("仅支持 DeerMind-M1 WSL 中的本机 K3s")
    images = set()
    for app in APPS:
        spec = json.loads(kube("get", app, "-o", "json", capture=True))["spec"]
        container = spec["template"]["spec"]["containers"][0]
        env = {e["name"]: e.get("value") for e in container["env"]}
        if spec["replicas"] not in (0, 1) or any(env.get(k) != v for k, v in CONFIG.items()):
            raise RuntimeError(f"{app} 与本机重置目标不匹配")
        images.add(container["image"])
    if len(images) != 1:
        raise RuntimeError("API 和 Worker 镜像不一致")
    owner = sql(
        "postgres", f"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='{DB}';"
    )
    if owner not in ("", "deermind_migrator"):
        raise RuntimeError("目标业务库的所有者不匹配")
    return images.pop()


def sql(database: str, statement: str) -> str:
    return kube(
        "exec",
        "-i",
        "deermind-postgres-0",
        "--",
        "psql",
        "-XqAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-d",
        database,
        data=statement,
        capture=True,
    ).strip()


def maintenance_pod(image: str) -> None:
    """只授予迁移、开户和本机消息维护所需的 Secret 引用。"""
    env = {**CONFIG, "M1_DB_USER": "deermind_migrator", "M1_NATS_USER": "maintenance"}
    variables: list[dict[str, object]] = [
        {"name": key, "value": value} for key, value in env.items()
    ]
    for key, secret, field in (
        ("M1_DB_PASSWORD", "deermind-postgres", "migration-password"),
        ("RESET_APP_PASSWORD", "deermind-postgres", "app-password"),
        ("M1_NATS_PASSWORD", "deermind-nats", "maintenance-password"),
    ):
        variables.append(
            {"name": key, "valueFrom": {"secretKeyRef": {"name": secret, "key": field}}}
        )
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": POD},
        "spec": {
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
            "activeDeadlineSeconds": 1200,
            "nodeSelector": {"kubernetes.io/hostname": "deermind-m1"},
            "securityContext": {"runAsNonRoot": True, "runAsUser": 10001},
            "containers": [
                {
                    "name": "reset",
                    "image": image,
                    "imagePullPolicy": "IfNotPresent",
                    "command": ["sleep", "1200"],
                    "env": variables,
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                }
            ],
        },
    }
    kube("delete", "pod", POD, "--ignore-not-found", "--wait", "--timeout=60s")
    kube("create", "-f", "-", data=json.dumps(pod))
    kube("wait", "--for=condition=Ready", "pod/" + POD, "--timeout=120s")


def run_in_pod(action: str, *args: str, data: str | None = None) -> None:
    kube(
        "exec", "-i", POD, "--", "python", "-c", WORKER_SCRIPT.read_text(), action, *args, data=data
    )


def local_migration_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT / "server/migrations/versions").glob("[0-9]*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_text().encode() + b"\0")
    return digest.hexdigest()


def stop_writers() -> None:
    kube("scale", *APPS, "--replicas=0")
    selector = "app.kubernetes.io/instance=deermind-app,app.kubernetes.io/component in (api,worker)"
    until = time.monotonic() + 120
    while kube("get", "pods", "-l", selector, "-o", "name", capture=True).strip():
        if time.monotonic() >= until:
            raise RuntimeError("原 API 或 Worker 仍在运行，停止重置")
        time.sleep(2)


def rebuild_database() -> None:
    sql(
        "postgres",
        f"""
        DROP DATABASE IF EXISTS {DB} WITH (FORCE);
        CREATE DATABASE {DB} OWNER deermind_migrator;
        REVOKE ALL ON DATABASE {DB} FROM PUBLIC;
        GRANT CONNECT ON DATABASE {DB} TO deermind_app;
    """,
    )
    sql(DB, "REVOKE CREATE ON SCHEMA public FROM PUBLIC;")


def verify_login(accounts: dict[str, str], role: str) -> None:
    browser = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))

    def request(path: str, body: dict | None = None, headers: dict | None = None) -> dict:
        req = Request(
            ORIGIN + "/api/m1/auth/" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Origin": ORIGIN, "Content-Type": "application/json", **(headers or {})},
        )
        with browser.open(req, timeout=10) as response:
            return json.load(response)

    request(
        "sign-in",
        {"login_identifier": accounts[role + "_login"], "password": accounts[role + "_password"]},
    )
    session = request("session")
    if session["account"]["role"] != role:
        raise RuntimeError(f"{role} 登录角色不符")
    request(
        "sign-out",
        {},
        {"X-Expected-Session": session["session_id"], "X-CSRF-Token": session["csrf_token"]},
    )


def reset() -> None:
    image = preflight()
    accounts = credentials()
    print(f"重置本机开发库 {DB}，镜像 {image}", flush=True)
    try:
        maintenance_pod(image)
        run_in_pod("check", local_migration_digest())
        stop_writers()
        print("API 和 Worker 已停止，正在清理旧工作和消息。", flush=True)
        run_in_pod("queues")
        rebuild_database()
        run_in_pod("initialize", data=json.dumps(accounts))
        counts = sql(
            DB,
            """SELECT (SELECT count(*) FROM product.accounts),
            (SELECT count(*) FROM product.textbook), (SELECT count(*) FROM product.learning_space),
            (SELECT count(*) FROM product.learning_target_version);""",
        )
        if counts != "2|0|0|0":
            raise RuntimeError("初始化后账号、教材、空间或目标数量不符合预期")
        kube("scale", *APPS, "--replicas=1")
        for app in APPS:
            kube("rollout", "status", app, "--timeout=180s")
        for role in ("admin", "student"):
            verify_login(accounts, role)
        print(
            f"重置成功。账号 2，教材、目标、学习空间均为 0；两种角色登录验证通过。凭据：{ACCOUNTS}"
        )
    finally:
        kube("delete", "pod", POD, "--ignore-not-found", "--wait=false")


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    with Path("/run/lock/deermind-local-db-reset.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        reset()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        # kubectl exec 的参数可能含维护脚本，避免在错误输出中复述整条命令。
        print(f"重置未完成，退出码 {error.returncode}。请排除以上错误后重跑。", file=sys.stderr)
        sys.exit(1)
