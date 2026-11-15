"""Prove the checks reject defects, rather than merely accepting clean files."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from quality.check_boundaries import inspect_imports

ROOT = Path(__file__).resolve().parents[2]


class QualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="check-fixture-", dir=ROOT / "quality")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=60)

    def write(self, name: str, content: str) -> Path:
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_python_lint_format_and_types(self) -> None:
        path = self.write("sample.py", "def size() -> int:\n    return 1\n")
        for tool in [("ruff", "check"), ("pyright",)]:
            result = self.run_tool(*tool, str(path))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path.write_text('import os\n\ndef size() -> int:\n    return "wrong"\n', encoding="utf-8")
        self.assertNotEqual(self.run_tool("ruff", "check", str(path)).returncode, 0)
        self.assertNotEqual(self.run_tool("pyright", str(path)).returncode, 0)
        path.write_text("x=  1\n", encoding="utf-8")
        self.assertNotEqual(self.run_tool("ruff", "format", "--check", str(path)).returncode, 0)

    def test_vue_lint_and_template_types(self) -> None:
        path = self.write(
            "SampleCard.vue",
            '<script setup lang="ts">\ndefineProps<{ title: string }>();\n</script>\n'
            "<template><p>{{ title }}</p></template>\n",
        )
        config = self.write(
            "tsconfig.json",
            json.dumps({"extends": "../tsconfig.base.json", "include": ["*.vue", "*.ts"]}),
        )
        lint = ("eslint", "--config", "quality/eslint.config.mjs", "--max-warnings", "0")
        result = self.run_tool(*lint, str(path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.run_tool("vue-tsc", "-p", str(config))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path.write_text(
            path.read_text(encoding="utf-8").replace("{{ title }}", "{{ missing }}"),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_tool("vue-tsc", "-p", str(config)).returncode, 0)
        bad = self.write("sample.ts", "export const value: any = 1;\n")
        self.assertNotEqual(self.run_tool(*lint, str(bad)).returncode, 0)
        shared = self.write("shared/sample.ts", "export { value } from '../admin/private';\n")
        result = self.run_tool(*lint, str(shared))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no-restricted-imports", result.stdout)

    def test_shell_quoting_and_format(self) -> None:
        path = self.write(
            "sample.sh", '#!/usr/bin/env bash\nvalue="a b"\nprintf "%s\\n" "$value"\n'
        )
        self.assertEqual(self.run_tool("shellcheck", str(path)).returncode, 0)
        path.write_text('#!/usr/bin/env bash\nvalue="a b"\necho $value\n', encoding="utf-8")
        result = self.run_tool("shellcheck", str(path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SC2086", result.stdout)
        path.write_text("#!/usr/bin/env bash\nif true;then echo ok;fi\n", encoding="utf-8")
        self.assertNotEqual(self.run_tool("shfmt", "-d", "-i", "2", "-ci", str(path)).returncode, 0)

    def test_yaml_and_json(self) -> None:
        path = self.write("sample.yaml", "name: example\nreplicas: 1\n")
        args = ("yamllint", "-s", "-c", "quality/yamllint.yaml")
        self.assertEqual(self.run_tool(*args, str(path)).returncode, 0)
        path.write_text("name: first\nname: second\n", encoding="utf-8")
        self.assertNotEqual(self.run_tool(*args, str(path)).returncode, 0)
        bad = self.write("sample.json", '{"name": }\n')
        self.assertNotEqual(self.run_tool("prettier", "--check", str(bad)).returncode, 0)

    def test_chart_values_types(self) -> None:
        args = (
            "helm",
            "--kubeconfig=/dev/null",
            "--kube-context=offline-check",
            "--namespace=deermind-check",
            "template",
            "deermind-postgres",
            "deploy/helm/postgres",
            "-f",
            "deploy/environments/local-wsl/postgres.values.yaml",
        )
        good = self.run_tool(*args)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        bad = self.run_tool(*args, "--set-string", "maxConnections=many")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("maxConnections", bad.stderr)

    def test_entrypoints_reject_missing_or_invalid_arguments(self) -> None:
        self.assertNotEqual(self.run_tool("bash", "scripts/check.sh", "--fix").returncode, 0)
        env = {key: value for key, value in os.environ.items() if not key.startswith("M1_")}
        for group in ("target", "components", "unknown"):
            result = subprocess.run(
                ["bash", "scripts/test.sh", group],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
        for args in ([], ["--release"], ["--release", "one", "--release", "two"]):
            self.assertNotEqual(self.run_tool("bash", "scripts/deploy.sh", *args).returncode, 0)

    def test_python_module_boundaries(self) -> None:
        cases = [
            (
                "deermind.foundation.events.store",
                "from deermind.spaces.domain.public import Task",
                True,
            ),
            (
                "deermind.spaces.interaction.memory.read",
                "from ...domain.persistence import tables",
                True,
            ),
            ("deermind.spaces.interaction.memory.read", "from ...domain.public import Task", False),
            ("deermind.spaces.domain.intake.save", "from ..persistence import tables", False),
            ("deermind.spaces.domain.public.models", "from sqlalchemy import Table", True),
            ("deermind.spaces.evaluation.belief.update", "import httpx", True),
            ("deermind.spaces.evaluation.belief.update", "import math", False),
        ]
        for module, source, rejected in cases:
            with self.subTest(module=module, source=source):
                self.assertEqual(bool(inspect_imports(module, source)), rejected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
