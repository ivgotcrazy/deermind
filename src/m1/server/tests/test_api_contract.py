"""公共错误和响应合同验证；通过真实ASGI入口，不启动数据库或模型。"""

import json
import unittest

from deermind.entrypoints.api.app import create_app
from deermind.entrypoints.api.errors import api_error
from deermind.foundation.system.public.errors import ErrorResponse, RequestError
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from starlette.types import Message


class ApiContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_route_and_invalid_response_use_safe_envelope(self) -> None:
        app = create_app()

        class Declared(BaseModel):
            count: int

        @app.get("/test-invalid", response_model=Declared)
        def invalid() -> dict[str, str]:
            return {"count": "private-output-must-not-leak"}

        for path, expected in (("/unknown", 404), ("/test-invalid", 500)):
            messages: list[Message] = []

            async def receive() -> Message:
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message: Message, sink: list[Message] = messages) -> None:
                sink.append(message)

            try:
                await app(
                    {
                        "type": "http",
                        "method": "GET",
                        "path": path,
                        "raw_path": path.encode(),
                        "query_string": b"",
                        "headers": [],
                        "scheme": "http",
                        "server": ("localhost", 80),
                    },
                    receive,
                    send,
                )
            except Exception:
                # ServerErrorMiddleware发送500后仍向服务器报告异常。
                if not any(m.get("status") == 500 for m in messages):
                    raise
            self.assertEqual(messages[0]["status"], expected)
            body = b"".join(m.get("body", b"") for m in messages)
            ErrorResponse.model_validate_json(body)
            self.assertNotIn(b"private-output", body)
            self.assertIn((b"cache-control", b"no-store"), messages[0]["headers"])

    async def test_storage_failure_is_not_not_found(self) -> None:
        request = Request({"type": "http"})
        response = await api_error(request, OperationalError("secret SQL", {}, Exception("secret")))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            json.loads(bytes(response.body))["error"]["code"], "temporarily_unavailable"
        )
        self.assertNotIn(b"secret", bytes(response.body))
        limited = await api_error(request, RequestError(429, "rate_limited", "稍后重试", 30))
        self.assertEqual(limited.headers["Retry-After"], "30")

    async def test_content_validation_reports_locations_without_input(self) -> None:
        error = RequestValidationError(
            [
                {
                    "loc": ("body", "definition", "description", "blocks", 0, "chart", "payload"),
                    "type": "invalid_value",
                    "input": "private-content",
                    "msg": "includes private-content",
                },
                {
                    "loc": ("body", "definition", "coverage", "private-key"),
                    "type": "extra_forbidden",
                },
            ]
        )
        response = await api_error(Request({"type": "http"}), error)
        self.assertEqual(response.status_code, 400)
        parsed = ErrorResponse.model_validate_json(bytes(response.body))
        self.assertEqual(
            [issue.path for issue in parsed.error.issues],
            ["/definition/description/blocks/0/payload", "/definition/coverage"],
        )
        self.assertNotIn(b"private-", bytes(response.body))

    def test_business_routes_declare_common_error_and_exact_receipt_result(self) -> None:
        schema = create_app().openapi()
        for path, verbs in schema["paths"].items():
            if not path.startswith("/api/m1/"):
                continue
            for operation in verbs.values():
                self.assertIn("500", operation["responses"])
                self.assertIn("404", operation["responses"])
                if "422" in operation["responses"]:
                    detail = operation["responses"]["422"]["content"]["application/json"]["schema"]
                    self.assertEqual(detail, {"$ref": "#/components/schemas/ErrorResponse"})
        receipt = schema["paths"]["/api/m1/requests/receipt"]["get"]["responses"]["200"]
        receipt_type = receipt["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
        receipt_properties = schema["components"]["schemas"][receipt_type]["properties"]
        result_types = receipt_properties["result"]["anyOf"]
        self.assertEqual(
            {item["$ref"] for item in result_types if "$ref" in item},
            {
                "#/components/schemas/AdoptedMaterialResult",
                "#/components/schemas/AnalysisReceipt",
                "#/components/schemas/ChapterAssociationResult",
                "#/components/schemas/ConfirmationResult",
                "#/components/schemas/ConfirmKCPathResult",
                "#/components/schemas/InstanceView",
                "#/components/schemas/IntakeActionResult",
                "#/components/schemas/IntakeSubmissionView",
                "#/components/schemas/MaterialDeletionResult",
                "#/components/schemas/MaterialResult",
                "#/components/schemas/MaterialTurnResult",
                "#/components/schemas/SaveResult",
            },
        )
        saves = schema["components"]["schemas"]["SaveResult"]["anyOf"]
        self.assertEqual(
            {item["$ref"] for item in saves},
            {
                "#/components/schemas/CreateDomainResult",
                "#/components/schemas/SaveKnowledgeResult",
                "#/components/schemas/SaveTaskResult",
                "#/components/schemas/SaveSolutionResult",
            },
        )
