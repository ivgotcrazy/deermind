"""验证 E01-01 目标预检及 E01-02 部署入口的目标隔离和失败边界。

本地用独立命令夹具记录调用，不访问集群。LiveTargetTests 仅在显式提供
M1_KUBECONFIG、M1_CONTEXT、M1_NAMESPACE 时启用，只读真实集群。
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check-target.sh"
FIXTURES = Path(__file__).parent / "fixtures"


class TargetTests(unittest.TestCase):
    """用命令替身证明参数、只读边界和部署失败时的停止行为。"""

    def setUp(self) -> None:
        """隔离 PATH、配置和调用记录，测试结束后移除整个临时目录。"""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "config with spaces"
        self.config.write_text("test config unchanged\n", encoding="utf-8")
        self.calls = self.root / "calls"
        kubectl = self.root / "kubectl"
        shutil.copyfile(FIXTURES / "kubectl_stub.py", kubectl)
        kubectl.chmod(0o700)

        # 带空格的路径用于验证脚本正确引用参数；替身不能回退到真实 kubectl。
        self.env = dict(
            os.environ,
            PATH=f"{self.root}:{os.environ['PATH']}",
            CALLS=str(self.calls),
            CONFIG=str(self.config),
        )
        self.args = [
            "--kubeconfig",
            str(self.config),
            "--context",
            "test",
            "--namespace",
            "deermind-m1",
        ]

    def run_check(
        self, args: list[str] | None = None, mode: str = ""
    ) -> subprocess.CompletedProcess[str]:
        """运行目标预检并保留输出；失败由测试断言，而不是直接抛异常。"""
        return subprocess.run(
            ["bash", str(SCRIPT), *(self.args if args is None else args)],
            env=dict(self.env, CASE=mode),
            text=True,
            capture_output=True,
            timeout=20,
        )

    def test_repeated_success_is_read_only(self) -> None:
        """重复预检不改配置，每次只执行四个只读查询。"""
        before = self.config.read_bytes()
        for _ in range(2):
            result = self.run_check()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS:", result.stdout)

        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(len(self.calls.read_text().splitlines()), 8)

    def test_invalid_arguments_never_contact_cluster(self) -> None:
        """输入不合法时，应在第一次访问集群前停止。"""
        for args in [
            [],
            self.args[:-2],
            ["--context"],
            self.args + ["--unknown"],
            self.args + ["--context", "other"],
            self.args[:-1] + ["INVALID"],
            ["--kubeconfig", "/missing", *self.args[2:]],
        ]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_check(args).returncode, 0)

        self.assertFalse(self.calls.exists())

    def test_unusable_targets_never_pass(self) -> None:
        """不同失败原因均不能输出成功标记。"""
        for mode in [
            "bad-context",
            "unreachable",
            "missing-namespace",
            "terminating",
            "empty-nodes",
            "not-ready",
        ]:
            with self.subTest(mode=mode):
                result = self.run_check(mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("PASS:", result.stdout)

    def test_deployment_requires_successful_preflight_and_lint(self) -> None:
        """失败不执行安装；成功时完整传递目标和禁止 hooks 的参数。"""
        helm = self.root / "helm"
        shutil.copyfile(FIXTURES / "helm_stub.py", helm)
        helm.chmod(0o700)
        helm_calls = self.root / "helm-calls"
        chart = self.root / "chart with spaces"
        chart.mkdir()
        values = self.root / "values with spaces.yaml"
        values.write_text("{}\n", encoding="utf-8")
        args = [*self.args, "--release", "probe", "--chart", str(chart), "--values", str(values)]

        for mode, fail_lint, expected_calls in [
            ("unreachable", "0", 0),
            ("", "1", 1),
            ("", "0", 2),
        ]:
            with self.subTest(mode=mode, fail_lint=fail_lint):
                helm_calls.unlink(missing_ok=True)
                result = subprocess.run(
                    ["bash", str(ROOT / "scripts/deploy.sh"), *args],
                    env=dict(self.env, CASE=mode, FAIL_LINT=fail_lint, HELM_CALLS=str(helm_calls)),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                calls = (
                    [json.loads(line) for line in helm_calls.read_text().splitlines()]
                    if helm_calls.exists()
                    else []
                )
                self.assertEqual(len(calls), expected_calls, result.stdout + result.stderr)
                self.assertEqual(result.returncode == 0, expected_calls == 2)

                target = [
                    f"--kubeconfig={self.config}",
                    "--kube-context=test",
                    "--namespace=deermind-m1",
                ]
                if calls:
                    self.assertEqual(calls[0], [*target, "lint", str(chart), "-f", str(values)])
                if expected_calls == 2:
                    self.assertEqual(
                        calls[1],
                        [
                            *target,
                            "upgrade",
                            "--install",
                            "probe",
                            str(chart),
                            "-f",
                            str(values),
                            "--no-hooks",
                            "--wait",
                            "--wait-for-jobs",
                            "--timeout",
                            "5m",
                        ],
                    )


@unittest.skipUnless(
    all(os.environ.get(key) for key in ("M1_KUBECONFIG", "M1_CONTEXT", "M1_NAMESPACE")),
    "Set M1_KUBECONFIG, M1_CONTEXT, M1_NAMESPACE for live checks",
)
class LiveTargetTests(unittest.TestCase):
    """在显式目标上检查真实可达性，不部署或修改集群。"""

    def test_real_target_and_failures_preserve_configs(self) -> None:
        """真实查询不改原配置或默认 context，故障只注入临时配置副本。"""
        original = Path(os.environ["M1_KUBECONFIG"])
        original_bytes = original.read_bytes()
        context = os.environ["M1_CONTEXT"]
        namespace = os.environ["M1_NAMESPACE"]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "target.kubeconfig"
            shutil.copyfile(original, config)
            config.chmod(0o600)

            # 故意设置一个无效默认目标，证明脚本只使用显式参数。
            default = root / "default.kubeconfig"
            default.write_text("apiVersion: v1\nkind: Config\ncurrent-context: do-not-use\n")
            default.chmod(0o600)
            default_bytes = default.read_bytes()
            env = dict(os.environ, KUBECONFIG=str(default))
            cases = [
                (context, namespace, True),
                (context, namespace, True),
                ("nonexistent-e01-01", namespace, False),
                (context, "nonexistent-e01-01", False),
            ]
            for selected_context, selected_namespace, success in cases:
                result = subprocess.run(
                    [
                        "bash",
                        str(SCRIPT),
                        "--kubeconfig",
                        str(config),
                        "--context",
                        selected_context,
                        "--namespace",
                        selected_namespace,
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=70,
                )
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
            self.assertEqual(config.read_bytes(), original_bytes)

            # 只修改临时副本，模拟 API 不可达；原始 kubeconfig 必须保持不变。
            cluster = subprocess.check_output(
                [
                    "kubectl",
                    f"--kubeconfig={config}",
                    f"--context={context}",
                    f"--namespace={namespace}",
                    "config",
                    "view",
                    "--minify",
                    "-o",
                    "jsonpath={.contexts[0].context.cluster}",
                ],
                text=True,
                timeout=20,
            )
            subprocess.run(
                [
                    "kubectl",
                    f"--kubeconfig={config}",
                    f"--context={context}",
                    f"--namespace={namespace}",
                    "config",
                    "set-cluster",
                    cluster,
                    "--server=https://127.0.0.1:1",
                ],
                check=True,
                capture_output=True,
                timeout=20,
            )
            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPT),
                    "--kubeconfig",
                    str(config),
                    "--context",
                    context,
                    "--namespace",
                    namespace,
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=70,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(default.read_bytes(), default_bytes)
        self.assertEqual(original.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
