"""在临时维护 Pod 中初始化当前应用使用的工作队列、迁移和合成账号。"""

import asyncio
import hashlib
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from deermind.abstractions.events import Ref
from deermind.bootstrap.accounts import configure_account_management, configure_usage
from deermind.bootstrap.database import DatabaseSettings
from deermind.bootstrap.messaging import subscriptions
from deermind.entrypoints.maintenance.database import migration_config, upgrade
from deermind.foundation.system.delivery.contracts import specifications
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.nats.connection import MessagingSettings, connect
from deermind.product.public.notice import TEST_NOTICE
from deermind.product.public.usage import ConfirmationInput, ConfirmUsageRequest
from google.protobuf.duration_pb2 import Duration
from nats.js.errors import NotFoundError
from temporalio.api.operatorservice.v1 import DeleteNamespaceRequest
from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest, RegisterNamespaceRequest
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode


def migration_digest(directory: Path) -> str:
    """比较部署包与工作树的迁移，忽略 Windows 和 Linux 的换行差异。"""
    digest = hashlib.sha256()
    for path in sorted(directory.glob("[0-9]*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_text().encode() + b"\0")
    return digest.hexdigest()


async def reset_temporal() -> None:
    """新命名空间沿用名称，使用新的内部 ID，旧工作无法被新 Worker 接走。"""
    name = os.environ["M1_TEMPORAL_NAMESPACE"]
    client = await Client.connect(os.environ["M1_TEMPORAL_ADDRESS"], namespace=name)
    service = client.workflow_service
    request = DescribeNamespaceRequest(namespace=name)
    old_id = None
    try:
        old_id = (await service.describe_namespace(request)).namespace_info.id
    except RPCError as error:
        if error.status != RPCStatusCode.NOT_FOUND:
            raise
    if old_id:
        await client.operator_service.delete_namespace(DeleteNamespaceRequest(namespace_id=old_id))
    async with asyncio.timeout(150):
        while True:
            try:
                await service.register_namespace(
                    RegisterNamespaceRequest(
                        namespace=name,
                        workflow_execution_retention_period=Duration(seconds=30 * 86400),
                    )
                )
            except RPCError as error:
                if error.status != RPCStatusCode.ALREADY_EXISTS:
                    raise
            try:
                current = await service.describe_namespace(request)
                if current.namespace_info.id and current.namespace_info.id != old_id:
                    return
            except RPCError as error:
                if error.status != RPCStatusCode.NOT_FOUND:
                    raise
            await asyncio.sleep(2)


async def reset_streams() -> None:
    settings = MessagingSettings.from_environment()
    async with connect(settings) as transport:
        for name in (settings.stream, settings.failures):
            try:
                await transport.js.delete_stream(name)
            except NotFoundError:
                pass
        await transport.initialize(specifications(subscriptions()))
        for name in (settings.stream, settings.failures):
            if (await transport.js.stream_info(name)).state.messages:
                raise RuntimeError(f"重新建立的消息流仍有待处理消息：{name}")


async def seed(accounts: dict[str, str]) -> None:
    """管理员引导和学生开户均经过正式的保存事件、投影与散列流程。"""
    settings = DatabaseSettings.from_environment()
    migrator = application_engine(settings.url())
    try:
        manager, _ = await configure_account_management(migrator)
        await manager.bootstrap(
            login=accounts["admin_login"],
            name="测试管理员",
            operator="local-wsl-reset",
            password=accounts["admin_password"],
        )
    finally:
        await migrator.dispose()
    url = settings.url().set(username="deermind_app", password=os.environ["RESET_APP_PASSWORD"])
    app = application_engine(url)
    try:
        manager, auth = await configure_account_management(app)
        admin = await auth.sign_in(
            accounts["admin_login"], accounts["admin_password"], "local-reset", None
        )
        source = Ref(owner="product", type="synthetic_verification", id="local-wsl-reset")
        receipt = await manager.create_student(
            admin.view,
            request_id=uuid4(),
            login=accounts["student_login"],
            name="测试学生",
            password=accounts["student_password"],
            guardian_name="合成监护人",
            verification_ref=source,
            synthetic=True,
        )
        if receipt.result_ref is None:
            raise RuntimeError("学生开户未返回账号")
        await configure_usage(app, Path("/tmp")).confirm(
            admin.view,
            ConfirmUsageRequest(
                request_id=uuid4(),
                expected_revision=1,
                confirmation=ConfirmationInput(
                    student_id=UUID(receipt.result_ref.id),
                    kind="guardian_consent",
                    notice_ref=TEST_NOTICE,
                    decision="accepted",
                    source_ref=source,
                ),
            ),
        )
        await auth.sign_out(admin.token, str(admin.view.session_id), admin.view.csrf_token)
    finally:
        await app.dispose()


async def main() -> None:
    action = sys.argv[1]
    if action == "check":
        path = migration_config().get_main_option("script_location")
        if not path or migration_digest(Path(path) / "versions") != sys.argv[2]:
            raise RuntimeError("部署镜像与工作树的迁移不同，请先部署对应服务端镜像")
    elif action == "queues":
        async with asyncio.timeout(timedelta(minutes=4).total_seconds()):
            await reset_temporal()
            await reset_streams()
    elif action == "initialize":
        upgrade(DatabaseSettings.from_environment().url())
        await seed(json.load(sys.stdin))
    else:
        raise ValueError("未知维护步骤")


if __name__ == "__main__":
    asyncio.run(main())
