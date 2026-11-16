"""E01-03 checks against an explicitly selected, already deployed test cluster.

Creates only a short-lived test workflow and probe files. No business data is
written. kubectl port-forward is stopped when the HTTP checks finish.
"""

import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENABLED = os.environ.get("M1_APPLICATION_TESTS") == "1"


@unittest.skipUnless(ENABLED, "Set M1_APPLICATION_TESTS=1 for the test cluster")
class ApplicationTests(unittest.TestCase):
    """Require real package, SDK and browser assets; a mocked response cannot pass."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.target = [
            "kubectl",
            f"--kubeconfig={os.environ['M1_KUBECONFIG']}",
            f"--context={os.environ['M1_CONTEXT']}",
            f"--namespace={os.environ['M1_NAMESPACE']}",
        ]
        cls.release = os.environ["M1_APPLICATION_RELEASE"]

    def kubectl(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*self.target, *args],
            capture_output=True,
            text=True,
            timeout=90,
            check=True,
        )

    def test_worker_and_shared_volume(self) -> None:
        result = self.kubectl(
            "exec",
            f"deployment/{self.release}-api",
            "--",
            "deermind-probe",
            "run",
        )
        self.assertIn('"outcome": "success"', result.stdout)
        print(result.stdout.strip())

    def test_sdk_registration(self) -> None:
        fixture = ROOT / "tests/deployment/fixtures/check_worker.py"
        result = subprocess.run(
            [*self.target, "exec", "-i", f"deployment/{self.release}-api", "--", "python", "-"],
            input=fixture.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: real SDK assembly", result.stdout)

    def test_package_and_startup_rejection(self) -> None:
        package = self.kubectl(
            "exec",
            f"deployment/{self.release}-api",
            "--",
            "python",
            "-c",
            "import deermind; print(deermind.__file__)",
        )
        self.assertIn("site-packages/deermind/__init__.py", package.stdout)
        for assignments in (
            ("-u", "M1_TEMPORAL_NAMESPACE"),
            ("M1_TEMPORAL_ADDRESS=127.0.0.1:1",),
        ):
            with self.subTest(assignments=assignments):
                result = subprocess.run(
                    [
                        *self.target,
                        "exec",
                        f"deployment/{self.release}-api",
                        "--",
                        "env",
                        *assignments,
                        "deermind-worker",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('"error_code": "WORKER_FAILED"', result.stdout)

    def test_pages_and_api_proxy(self) -> None:
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        with tempfile.TemporaryFile(mode="w+") as output:
            forward = subprocess.Popen(
                [
                    *self.target,
                    "port-forward",
                    f"service/{self.release}-client",
                    f"{port}:8080",
                    "--address=127.0.0.1",
                ],
                stdout=output,
                stderr=output,
            )
            try:
                base = f"http://127.0.0.1:{port}"
                for _ in range(50):
                    if forward.poll() is not None:
                        self.fail("port-forward exited before becoming ready")
                    try:
                        with urllib.request.urlopen(base + "/health/live", timeout=1):
                            break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    self.fail("port-forward did not become ready")

                for page, title in (("admin", "管理端"), ("student", "学生端")):
                    with urllib.request.urlopen(f"{base}/{page}/", timeout=5) as response:
                        html = response.read().decode()
                    self.assertIn(title, html)
                    self.assertIn("/assets/", html)
                    self.assertNotIn("/src/", html)
                with urllib.request.urlopen(base + "/api/health/ready", timeout=5) as response:
                    self.assertEqual(json.load(response), {"status": "ok"})
                # 使用已批准的浏览器来源，核对代理保留完整API路径及Host端口。
                origin = os.environ["M1_AUTH_TEST_ORIGIN"]
                headers = {"Host": urllib.parse.urlsplit(origin).netloc, "Origin": origin}
                query = urllib.request.Request(base + "/api/m1/auth/session", headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as anonymous:
                    urllib.request.urlopen(query, timeout=5)
                self.assertEqual(anonymous.exception.code, 401)
                self.assertEqual(json.load(anonymous.exception)["error"]["code"], "unauthenticated")
                self.assertEqual(anonymous.exception.headers["Cache-Control"], "no-store")
                oversized = urllib.request.Request(
                    base + "/api/m1/auth/sign-in",
                    data=b"",
                    headers={
                        **headers,
                        "Content-Type": "application/json",
                        "Content-Length": str(2 * 1024 * 1024 + 1),
                    },
                )
                with self.assertRaises(urllib.error.HTTPError) as too_large:
                    urllib.request.urlopen(oversized, timeout=5)
                self.assertEqual(too_large.exception.code, 413)
                self.assertEqual(
                    json.load(too_large.exception)["error"]["code"], "payload_too_large"
                )
                with self.assertRaises(urllib.error.HTTPError) as missing:
                    urllib.request.urlopen(base + "/assets/missing.js", timeout=5)
                self.assertEqual(missing.exception.code, 404)
            finally:
                forward.terminate()
                forward.wait(timeout=10)

    def test_chart_rejects_missing_configuration(self) -> None:
        for key in ("images.server", "filesClaim", "temporal.namespace"):
            result = subprocess.run(
                [
                    "helm",
                    "--kubeconfig=/dev/null",
                    "--kube-context=offline-check",
                    "--namespace=check",
                    "template",
                    "app",
                    "deploy/helm/application",
                    "-f",
                    "deploy/environments/local-wsl/application.values.yaml",
                    "--set-string",
                    f"{key}=",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(result.returncode, 0, key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
