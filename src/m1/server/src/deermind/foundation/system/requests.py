"""按登记动作委托所有者查收据；不读取业务表，不派发工作。

分层定位：foundation（公共运行底座 / 收据查询委托）
对外契约：RequestReceipts 按动作与资源类型把收据查询委托给对应所有者登记的读取器。
边界约束：本层不读业务表、不派发工作；未开放的动作/资源直接拒绝。
"""

from collections.abc import Awaitable, Callable, Mapping
from uuid import UUID

from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery
from pydantic import BaseModel

# 收据读取器签名：受理主体、会话、查询条件 → 收据视图。
type ReceiptReader = Callable[[UUID, UUID, ReceiptQuery], Awaitable[BaseModel]]


class RequestReceipts:
    """收据查询委托：持有按动作/资源类型登记的读取器。"""

    def __init__(self, readers: Mapping[tuple[str, str], ReceiptReader]) -> None:
        self.readers = dict(readers)

    async def read(self, principal: UUID, session: UUID, query: ReceiptQuery) -> BaseModel:
        """按查询条件定位读取器并委托查询；未登记则返回 400。"""
        reader = self.readers.get((query.action, query.resource_kind))
        # 该动作与资源类型未登记读取器，直接拒绝，不回退到默认实现。
        if reader is None:
            raise RequestError(400, "invalid_request", "该动作或资源尚未开放收据查询。")
        return await reader(principal, session, query)
