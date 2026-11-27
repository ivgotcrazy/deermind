"""开发库重置失败时须在删除前或恢复服务前停下。测试仅替换集群调用。"""

import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/reset-local-db.py"
spec = importlib.util.spec_from_file_location("reset_local_db", SCRIPT)
assert spec is not None and spec.loader is not None
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)


class ResetBoundaryTests(unittest.TestCase):
    def test_refuses_remote_cluster_before_reading_apps(self) -> None:
        with patch.object(reset, "kube", return_value="https://other:6443") as kube:
            with self.assertRaises(RuntimeError):
                reset.preflight()
            self.assertEqual(kube.call_count, 1)

    def test_refuses_to_stop_apps_if_database_differs(self) -> None:
        env = {**reset.CONFIG, "M1_DB_NAME": "another_database"}
        container = {"image": "test", "env": [{"name": k, "value": v} for k, v in env.items()]}
        spec = {"replicas": 1, "template": {"spec": {"containers": [container]}}}
        with (
            patch.dict(os.environ, WSL_DISTRO_NAME="DeerMind-M1"),
            patch.object(
                reset, "kube", side_effect=["https://127.0.0.1:6443", json.dumps({"spec": spec})]
            ),
            patch.object(reset, "sql") as sql,
            self.assertRaises(RuntimeError),
        ):
            reset.preflight()
        sql.assert_not_called()

    def test_failed_queue_reset_never_drops_database_or_resumes_writers(self) -> None:
        with (
            patch.object(reset, "preflight", return_value="test"),
            patch.object(reset, "credentials", return_value={}),
            patch.object(reset, "maintenance_pod"),
            patch.object(reset, "stop_writers") as stop,
            patch.object(
                reset, "run_in_pod", side_effect=[None, RuntimeError("queues unavailable")]
            ),
            patch.object(reset, "rebuild_database") as drop,
            patch.object(reset, "kube") as kube,
            self.assertRaisesRegex(RuntimeError, "queues unavailable"),
        ):
            reset.reset()
        stop.assert_called_once()
        drop.assert_not_called()
        kube.assert_called_once_with(
            "delete", "pod", reset.POD, "--ignore-not-found", "--wait=false"
        )
