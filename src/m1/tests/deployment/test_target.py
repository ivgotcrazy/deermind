"""Target preflight tests; optional live cases only read the selected cluster."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check-target.sh"


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "config with spaces"
        self.config.write_text("test config unchanged\n")
        self.calls = self.root / "calls"
        kubectl = self.root / "kubectl"
        kubectl.write_text('''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps(args) + '\\n')
assert args[:4] == ['--kubeconfig=' + os.environ['CONFIG'], '--context=test', '--namespace=deermind-m1', '--request-timeout=10s']
mode = os.environ.get('CASE', '')
command = args[4:]
if command[:2] == ['config', 'view']:
    if mode == 'bad-context': sys.exit(1)
    print('https://127.0.0.1:6443')
elif command == ['get', '--raw=/readyz']:
    if mode == 'unreachable': sys.exit(1)
    print('ok')
elif command[:2] == ['get', 'namespace']:
    if mode == 'missing-namespace': sys.exit(1)
    print('Terminating' if mode == 'terminating' else 'Active')
elif command[:2] == ['get', 'nodes']:
    if mode != 'empty-nodes': print('node-1\\t' + ('False' if mode == 'not-ready' else 'True'))
else:
    raise AssertionError('Unexpected or mutating command: ' + repr(command))
''')
        kubectl.chmod(0o700)
        self.env = dict(os.environ, PATH=f"{self.root}:{os.environ['PATH']}",
                        CALLS=str(self.calls), CONFIG=str(self.config))
        self.args = ["--kubeconfig", str(self.config), "--context", "test",
                     "--namespace", "deermind-m1"]

    def run_check(self, args=None, mode=""):
        return subprocess.run(["bash", str(SCRIPT), *(self.args if args is None else args)],
                              env=dict(self.env, CASE=mode), text=True,
                              capture_output=True, timeout=20)

    def test_repeated_success_is_read_only(self):
        before = self.config.read_bytes()
        for _ in range(2):
            result = self.run_check()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS:", result.stdout)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(len(self.calls.read_text().splitlines()), 8)

    def test_invalid_arguments_never_contact_cluster(self):
        for args in [[], self.args[:-2], ["--context"], self.args + ["--unknown"],
                     self.args + ["--context", "other"], self.args[:-1] + ["INVALID"],
                     ["--kubeconfig", "/missing", *self.args[2:]]]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_check(args).returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_unusable_targets_never_pass(self):
        for mode in ["bad-context", "unreachable", "missing-namespace",
                     "terminating", "empty-nodes", "not-ready"]:
            with self.subTest(mode=mode):
                result = self.run_check(mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("PASS:", result.stdout)


@unittest.skipUnless(all(os.environ.get(key) for key in
                        ("M1_KUBECONFIG", "M1_CONTEXT", "M1_NAMESPACE")),
                     "Set M1_KUBECONFIG, M1_CONTEXT, M1_NAMESPACE for live checks")
class LiveTargetTests(unittest.TestCase):
    def test_real_target_and_failures_preserve_configs(self):
        original = Path(os.environ["M1_KUBECONFIG"])
        original_bytes = original.read_bytes()
        context = os.environ["M1_CONTEXT"]
        namespace = os.environ["M1_NAMESPACE"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "target.kubeconfig"
            shutil.copyfile(original, config)
            config.chmod(0o600)
            # A different global default must neither be used nor modified.
            default = root / "default.kubeconfig"
            default.write_text("apiVersion: v1\nkind: Config\ncurrent-context: do-not-use\n")
            default.chmod(0o600)
            default_bytes = default.read_bytes()
            env = dict(os.environ, KUBECONFIG=str(default))
            cases = [(context, namespace, True), (context, namespace, True),
                     ("nonexistent-e01-01", namespace, False),
                     (context, "nonexistent-e01-01", False)]
            for ctx, ns, success in cases:
                result = subprocess.run(["bash", str(SCRIPT), "--kubeconfig", str(config),
                                         "--context", ctx, "--namespace", ns],
                                        env=env, capture_output=True, text=True, timeout=70)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
            self.assertEqual(config.read_bytes(), original_bytes)
            # Only the disposable copy is changed for the unreachable-server case.
            cluster = subprocess.check_output(
                ["kubectl", f"--kubeconfig={config}", f"--context={context}",
                 f"--namespace={namespace}", "config", "view", "--minify", "-o",
                 "jsonpath={.contexts[0].context.cluster}"], text=True)
            subprocess.run(["kubectl", f"--kubeconfig={config}", f"--context={context}",
                            f"--namespace={namespace}", "config", "set-cluster", cluster,
                            "--server=https://127.0.0.1:1"], check=True, capture_output=True)
            result = subprocess.run(["bash", str(SCRIPT), "--kubeconfig", str(config),
                                     "--context", context, "--namespace", namespace],
                                    env=env, capture_output=True, text=True, timeout=70)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(default.read_bytes(), default_bytes)
        self.assertEqual(original.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
