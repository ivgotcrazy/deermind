"""运行进程和维护工具共享 Temporal 载荷转换配置。"""

from deermind.bootstrap.settings import Settings
from deermind.foundation.system.files.payloads import RuntimePayloadFiles
from deermind.foundation.system.files.registry import FileRegistry
from deermind.infrastructure.files.local import LocalFiles
from deermind.infrastructure.files.payload_codec import RuntimePayloadCodec
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio.client import Client
from temporalio.converter import DataConverter


async def connect_temporal(settings: Settings, engine: AsyncEngine) -> Client:
    """连接使用同一数据库登记和共享文件区的 Temporal 客户端。"""
    files = LocalFiles(settings.files_root, backend=settings.files_backend)
    storage = RuntimePayloadFiles(FileRegistry(engine), files)
    return await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        data_converter=DataConverter(payload_codec=RuntimePayloadCodec(storage)),
        plugins=[PydanticAIPlugin()],
    )
