"""Small DeepSeek JSON adapter with explicit limits, no retries, and safe evidence."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from uuid import uuid4


class ModelFailure(RuntimeError):
    pass


def strict_json(text):
    def reject_constant(value):
        raise ValueError("Non-finite JSON number")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_pairs)


@dataclass(frozen=True)
class LLMConfig:
    api_key: str = field(repr=False)
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    max_calls: int = 2
    max_output_tokens: int = 1024
    timeout_seconds: float = 60

    def __post_init__(self):
        url = urlsplit(self.base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("LLM base URL must be an HTTPS endpoint without embedded credentials or query")
        if (not self.model or type(self.max_calls) is not int or self.max_calls < 1
                or type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 393216
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError("Invalid model or call/token/timeout limit")

    def public(self):
        return {"provider": "deepseek", "base_url": self.base_url, "model": self.model,
                "max_calls": self.max_calls, "max_output_tokens": self.max_output_tokens,
                "timeout_seconds": self.timeout_seconds, "retries": 0,
                "thinking": "disabled", "temperature": 0, "max_input_chars": 16000,
                "credential_source": "DEERMIND_LLM_API_KEY", "key_configured": bool(self.api_key)}


def load_config(repo: Path, environment=None):
    values = {}
    env_file = repo / ".env"
    if env_file.exists():
        for line_number, raw in enumerate(env_file.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if not separator:
                raise ValueError(f"Invalid .env assignment at line {line_number}")
            name, value = name.strip(), value.strip()
            if name.startswith("DEERMIND_LLM_"):
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[name] = value
    values.update({k: v for k, v in (os.environ if environment is None else environment).items()
                   if k.startswith("DEERMIND_LLM_")})
    try:
        return LLMConfig(values.get("DEERMIND_LLM_API_KEY", "").strip(),
                         values.get("DEERMIND_LLM_BASE_URL", "https://api.deepseek.com").rstrip("/"),
                         values.get("DEERMIND_LLM_MODEL", "deepseek-flash"),
                         int(values.get("DEERMIND_LLM_MAX_CALLS", "2")),
                         int(values.get("DEERMIND_LLM_MAX_OUTPUT_TOKENS", "1024")),
                         float(values.get("DEERMIND_LLM_TIMEOUT_SECONDS", "60")))
    except (TypeError, ValueError):
        # Never echo a malformed environment value; it could contain a pasted key.
        raise ValueError("Invalid DeepSeek configuration; check endpoint and numeric limits") from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_transport(url, key, payload, timeout):
    request = Request(url, data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            data = response.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                raise ModelFailure("ProviderResponseTooLarge")
            return strict_json(data)
    except HTTPError as exc:
        raise ModelFailure(f"ProviderHTTPError:{exc.code}") from None
    except (URLError, TimeoutError):
        raise ModelFailure("ProviderNetworkOrTimeoutFailure") from None
    except (UnicodeDecodeError, ValueError):
        raise ModelFailure("InvalidProviderResponse") from None


class DeepSeekAdapter:
    def __init__(self, config, transport=http_transport):
        self.config, self.transport = config, transport
        self.calls = 0
        self.records = []

    def complete(self, messages, purpose):
        if not self.config.api_key:
            raise ModelFailure("MissingAPIKey: configure DEERMIND_LLM_API_KEY locally")
        if self.calls >= self.config.max_calls:
            raise ModelFailure("ModelCallBudgetExhausted")
        if len(json.dumps(messages, ensure_ascii=False)) > 16000:
            raise ModelFailure("InputLimitExceeded")
        self.calls += 1
        record = {"execution_id": uuid4().hex, "purpose": purpose,
                  "started_at": datetime.now(timezone.utc).isoformat(), "config": self.config.public(),
                  "messages": messages, "status": "STARTED"}
        self.records.append(record)
        request = {"model": self.config.model, "messages": messages, "stream": False,
                   "thinking": {"type": "disabled"}, "temperature": 0,
                   "response_format": {"type": "json_object"}, "max_tokens": self.config.max_output_tokens}
        try:
            response = self.transport(self.config.base_url + "/chat/completions", self.config.api_key,
                                      request, self.config.timeout_seconds)
            choice = response["choices"][0]
            content = choice["message"].get("content")
            # Deliberately omit reasoning_content and HTTP headers from retained evidence.
            record.update({"response_id": response.get("id"), "model": response.get("model"),
                           "system_fingerprint": response.get("system_fingerprint"),
                           "usage": response.get("usage"), "finish_reason": choice.get("finish_reason"),
                           "content": content})
            if choice.get("finish_reason") != "stop":
                raise ModelFailure("IncompleteModelOutput")
            if not isinstance(content, str) or not content.strip():
                raise ModelFailure("EmptyModelOutput")
            parsed = strict_json(content)
            if not isinstance(parsed, dict):
                raise ModelFailure("InvalidStructuredOutput")
            record["status"] = "COMPLETED"
            return parsed, record["execution_id"]
        except ModelFailure as exc:
            record.update(status="FAILED", failure=str(exc))
            raise
        except (KeyError, IndexError, TypeError, ValueError):
            record.update(status="FAILED", failure="InvalidStructuredOutput")
            raise ModelFailure("InvalidStructuredOutput") from None
        except Exception:
            record.update(status="FAILED", failure="ProviderTransportFailure")
            raise ModelFailure("ProviderTransportFailure") from None
        finally:
            record["completed_at"] = datetime.now(timezone.utc).isoformat()
