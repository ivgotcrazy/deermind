"""在JSON解析前限制HTTP正文；同时检查声明长度与实际分块字节。"""

from deermind.entrypoints.api.auth import safe_error
from deermind.product.public.authentication import AuthError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HTTP_BODY_LIMIT = 2 * 1024 * 1024


class RequestBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        lengths = [value for key, value in scope["headers"] if key.lower() == b"content-length"]
        try:
            declared = int(lengths[0]) if len(lengths) == 1 else 0
            if len(lengths) > 1 or declared < 0:
                raise ValueError("Invalid content length")
        except ValueError:
            await safe_error(AuthError(400, "invalid_request", "请求长度不正确。"))(
                scope, receive, send
            )
            return
        if declared > HTTP_BODY_LIMIT:
            await self.reject(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            part = message.get("body", b"")
            if len(body) + len(part) > HTTP_BODY_LIMIT:
                await self.reject(scope, receive, send)
                return
            body.extend(part)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)

    @staticmethod
    async def reject(scope: Scope, receive: Receive, send: Send) -> None:
        await safe_error(AuthError(413, "payload_too_large", "请求正文超过2MiB上限。"))(
            scope, receive, send
        )
