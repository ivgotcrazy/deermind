"""单行 JSON 应用日志；默认不记录消息正文或凭据。

分层定位：foundation（公共运行底座 / 日志格式）
对外契约：JsonFormatter 输出带公共字段的单行 JSON；configure_logging 由进程入口装配日志。
边界约束：模块导入不改变全局日志；堆栈只保留位置信息，不带异常文本或局部变量。
"""

import json
import logging
import sys
import traceback
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Keep framework logs readable while enforcing the shared required fields."""

    def format(self, record: logging.LogRecord) -> str:
        """把日志记录格式化为单行 JSON，附加约定字段与异常类型/堆栈。"""
        result: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "component": record.name,
            "action": getattr(record, "action", "service_log"),
            "outcome": getattr(
                record, "outcome", "failed" if record.levelno >= logging.ERROR else "pending"
            ),
            "message": record.getMessage(),
        }
        # 约定上下文字段存在才透传，缺省不出现在 JSON 中。
        for key in (
            "error_code",
            "request_id",
            "execution_id",
            "duration_ms",
            "event_id",
            "scope_id",
            "subscriber_id",
            "handoff_id",
            "wait_id",
        ):
            if hasattr(record, key):
                result[key] = getattr(record, key)
        # ERROR 级未带错误码时补默认服务错误码，避免日志缺定位信息。
        if record.levelno >= logging.ERROR and "error_code" not in result:
            result["error_code"] = "SERVICE_ERROR"
        # 附带异常时记录类型、消息与堆栈位置；堆栈不带局部变量。
        if record.exc_info and record.exc_info[0]:
            result["error_type"] = record.exc_info[0].__name__
            result["error_message"] = record.getMessage()
            # Frames retain location information without exception text or local values.
            result["stack_trace"] = "".join(traceback.format_tb(record.exc_info[2]))
        return json.dumps(result, ensure_ascii=False)


def configure_logging() -> None:
    """由进程入口调用；模块导入本身不改变全局日志配置。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
