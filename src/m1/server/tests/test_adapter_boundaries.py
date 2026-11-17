"""技术外壳只依赖注入接口；错误转换不改变工作及等待身份。"""

import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import RunInput
from deermind.abstractions.waits import WaitCall
from deermind.infrastructure.temporal.executions import Lifecycle
from deermind.infrastructure.temporal.waits import Activities
from pydantic import ValidationError
from temporalio.exceptions import ApplicationError


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.incoming = RunInput(
            execution_id=uuid4(),
            attempt_id=uuid4(),
            input_ref=Ref(owner="test", type="input", id="one"),
            implementation_ref=Ref(owner="test", type="handler", id="one"),
            ai_config_ref=None,
            deadline_at=datetime.now(UTC),
        )

    async def test_lifecycle_uses_injected_service(self) -> None:
        service = AsyncMock()
        adapter = Lifecycle(service)
        await adapter.started(self.incoming.model_dump_json())
        service.started.assert_awaited_once_with(self.incoming)
        result = Ref(owner="test", type="result", id="one")
        await adapter.completed(self.incoming.model_dump_json(), result.model_dump_json())
        service.completed.assert_awaited_once_with(self.incoming, result)
        await adapter.failed(self.incoming.model_dump_json(), "failed")
        service.failed.assert_awaited_once_with(self.incoming, "failed")

    async def test_lifecycle_does_not_retry_authorization_rejection(self) -> None:
        service = AsyncMock()
        service.started.side_effect = PermissionError("private detail")
        with self.assertRaises(ApplicationError) as captured:
            await Lifecycle(service).started(self.incoming.model_dump_json())
        self.assertTrue(captured.exception.non_retryable)
        self.assertNotIn("private detail", str(captured.exception))

    async def test_wait_passes_original_identity_and_maps_rejection(self) -> None:
        service = AsyncMock()
        call = WaitCall(run=self.incoming, wait_id=uuid4())
        service.probe.side_effect = PermissionError("private detail")
        with self.assertRaises(ApplicationError) as captured:
            await Activities(service).probe(call.model_dump_json())
        service.probe.assert_awaited_once_with(call)
        self.assertTrue(captured.exception.non_retryable)
        self.assertNotIn("private detail", str(captured.exception))

    async def test_invalid_wire_input_keeps_validation_error(self) -> None:
        service = AsyncMock()
        for method in (Lifecycle(service).started, Activities(service).probe):
            with self.subTest(method=method.__name__), self.assertRaises(ValidationError):
                await method("{}")
        service.started.assert_not_awaited()
        service.probe.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
