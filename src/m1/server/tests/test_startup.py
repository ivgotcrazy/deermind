"""Exercise startup rejection, SDK connection rejection and the storage probe."""

import json
import logging
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from deermind.bootstrap.services import create_worker
from deermind.bootstrap.settings import Settings
from deermind.entrypoints.api.app import create_app
from deermind.foundation.system.logging import JsonFormatter
from deermind.infrastructure.files.check import check_storage
from deermind.infrastructure.temporal.probe_activity import ProbeActivity
from pydantic import ValidationError
from temporalio.client import Client


class StartupTests(unittest.IsolatedAsyncioTestCase):
    """No network is contacted: the lazy Temporal client must not be accepted as ready."""

    def test_required_configuration(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings.from_environment()
        with self.assertRaises(ValidationError):
            Settings(
                files_root=Path("relative"),
                temporal_address="host:7233",
                temporal_namespace="dm-test",
                task_queue="test",
            )

    def test_storage_and_path_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            check_storage(root, require_mount=False)
            self.assertEqual(list(root.iterdir()), [])
            probe = ProbeActivity(root)
            with self.assertRaises(ValueError):
                probe.reply("../../private")
            token = uuid4().hex
            (root / f".probe-{token}.request").write_text(token)
            self.assertEqual(probe.reply(token), token)
            self.assertEqual((root / f".probe-{token}.reply").read_text(), token)

    def test_logs_are_single_line_json(self) -> None:
        record = logging.LogRecord("runtime", logging.INFO, __file__, 1, "完成\n测试", (), None)
        record.wait_id = "test-wait"
        line = JsonFormatter().format(record)
        self.assertNotIn("\n", line)
        payload = json.loads(line)
        self.assertEqual(payload["message"], "完成\n测试")
        self.assertEqual(payload["wait_id"], "test-wait")
        self.assertTrue(payload["timestamp"].endswith("Z"))

    async def test_api_requires_usable_storage(self) -> None:
        app = create_app()
        with patch.dict("os.environ", {}, clear=True):
            # Offline schema export must not require a running database or mount.
            self.assertIn("/health/ready", app.openapi()["paths"])
            with self.assertRaises(ValidationError):
                async with app.router.lifespan_context(app):
                    self.fail("Missing configuration was accepted")

    async def test_worker_rejects_unconnected_client(self) -> None:
        client = await Client.connect("127.0.0.1:1", namespace="dm-test", lazy=True)
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                files_root=Path(directory),
                temporal_address="127.0.0.1:1",
                temporal_namespace="dm-test",
                task_queue="test",
            )
            with ThreadPoolExecutor(2) as workflows, ThreadPoolExecutor(4) as activities:
                with self.assertRaisesRegex(RuntimeError, "Lazy clients"):
                    create_worker(client, settings, workflows, activities)


if __name__ == "__main__":
    unittest.main(verbosity=2)
