"""解析JSON前拒绝超大请求，包括缺失或伪造Content-Length。"""

import unittest

from deermind.entrypoints.api.body_limit import HTTP_BODY_LIMIT, RequestBodyLimit
from starlette.types import Message, Receive, Scope, Send


class HttpBodyLimitTests(unittest.IsolatedAsyncioTestCase):
    async def check(
        self,
        chunks: list[bytes],
        length: bytes | None = None,
        *,
        method: str = "POST",
        path: str = "/api/m1/test",
    ) -> tuple[int, int]:
        captured: list[Message] = []
        consumed = 0

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal consumed
            message = await receive()
            consumed = len(message["body"])
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        pending = iter(chunks)
        seen = 0

        async def receive() -> Message:
            nonlocal seen
            seen += 1
            return {"type": "http.request", "body": next(pending), "more_body": seen < len(chunks)}

        async def send(message: Message) -> None:
            captured.append(message)

        await RequestBodyLimit(app)(
            {
                "type": "http",
                "method": method,
                "path": path,
                "headers": [(b"content-length", length)] if length else [],
            },
            receive,
            send,
        )
        return captured[0]["status"], consumed

    async def test_exact_limit_is_preserved(self) -> None:
        self.assertEqual(await self.check([b"x" * HTTP_BODY_LIMIT]), (204, HTTP_BODY_LIMIT))

    async def test_declared_and_chunked_overflow_never_reach_parser(self) -> None:
        self.assertEqual(await self.check([], str(HTTP_BODY_LIMIT + 1).encode()), (413, 0))
        for length in (None, b"1"):
            self.assertEqual(await self.check([b"x" * HTTP_BODY_LIMIT, b"x"], length), (413, 0))

    async def test_invalid_length_is_rejected(self) -> None:
        self.assertEqual(await self.check([], b"-1"), (400, 0))
        self.assertEqual(await self.check([], b"invalid"), (400, 0))

    async def test_only_registered_binary_route_uses_the_streaming_handler(self) -> None:
        path = "/api/m1/file-uploads/00000000-0000-4000-8000-000000000000/content"
        payload = b"x" * (HTTP_BODY_LIMIT + 1)
        length = str(len(payload)).encode()
        self.assertEqual(
            await self.check([payload], length, method="PUT", path=path), (204, len(payload))
        )
        self.assertEqual(await self.check([], length, path=path), (413, 0))
