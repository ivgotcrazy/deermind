"""Single-line JSON application logs; no message bodies or credentials by default."""

import json
import logging
import sys
import traceback
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Keep framework logs readable while enforcing the shared required fields."""

    def format(self, record: logging.LogRecord) -> str:
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
        for key in (
            "error_code",
            "request_id",
            "execution_id",
            "duration_ms",
            "event_id",
            "scope_id",
            "subscriber_id",
            "handoff_id",
        ):
            if hasattr(record, key):
                result[key] = getattr(record, key)
        if record.levelno >= logging.ERROR and "error_code" not in result:
            result["error_code"] = "SERVICE_ERROR"
        if record.exc_info and record.exc_info[0]:
            result["error_type"] = record.exc_info[0].__name__
            result["error_message"] = record.getMessage()
            # Frames retain location information without exception text or local values.
            result["stack_trace"] = "".join(traceback.format_tb(record.exc_info[2]))
        return json.dumps(result, ensure_ascii=False)


def configure_logging() -> None:
    """Called only by process entrypoints; importing a module never changes logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
