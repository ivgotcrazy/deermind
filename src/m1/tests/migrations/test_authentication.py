"""认证真实数据库用例；账号及密码仅存在于每例随机测试库。"""

import asyncio
import json
import tempfile
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from deermind.abstractions.events import ProducerAccess, Ref
from deermind.bootstrap.events import event_store
from deermind.bootstrap.projections import account_rebuilder
from deermind.entrypoints.api.app import create_app
from deermind.entrypoints.maintenance.database import upgrade
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from deermind.product.accounts.auth import AuthError, AuthService
from deermind.product.accounts.save import save_initial_account
from deermind.product.public.auth_config import AuthConfig
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from starlette.types import Message, Scope
from test_database import DatabaseTestCase

PASSWORD = "test-only-not-a-real-secret"


class AuthenticationTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)

    async def execute(self, scenario: Callable[[AuthService], Awaitable[None]]) -> None:
        engine = application_engine(self.app)
        service = AuthService(engine)
        try:
            await service.initialize()
            for login in ("alpha", "beta"):
                identity = uuid4()
                await save_initial_account(
                    engine,
                    event_store(),
                    ProducerAccess(
                        "product",
                        Ref(owner="runtime", type="service", id="test"),
                        frozenset({("account", identity)}),
                    ),
                    request_id=str(identity),
                    account_id=identity,
                    login_identifier=login,
                    display_name=login,
                )
                # 仅隔离测试夹具可写凭据；正式预置账号入口属于E01-10。
                with self.engine.begin() as connection:
                    connection.execute(
                        text("INSERT INTO product.credentials VALUES (:id,:hash,1,now())"),
                        {"id": identity, "hash": service.hasher.hash(PASSWORD)},
                    )
            await scenario(service)
        finally:
            await engine.dispose()

    def test_login_restart_switch_logout_and_secrets(self) -> None:
        async def scenario(service: AuthService) -> None:
            first = await service.sign_in(" ALPHA ", PASSWORD, "127.0.0.1", None)
            recreated = AuthService(service.engine)
            self.assertEqual(await recreated.session(first.token), first.view)
            second = await service.sign_in("beta", PASSWORD, "127.0.0.1", first.token)
            with self.assertRaises(AuthError) as revoked:
                await service.session(first.token)
            self.assertEqual(revoked.exception.status, 401)
            with self.assertRaises(AuthError) as stale:
                await service.sign_out(
                    second.token, str(first.view.session_id), first.view.csrf_token
                )
            self.assertEqual(stale.exception.status, 409)
            with self.assertRaises(AuthError) as forged:
                await service.sign_out(second.token, str(second.view.session_id), "wrong")
            self.assertEqual(forged.exception.status, 403)
            await service.sign_out(
                second.token, str(second.view.session_id), second.view.csrf_token
            )
            await service.sign_out(second.token, None, None)
            with self.engine.connect() as connection:
                facts = str(connection.execute(text("SELECT payload FROM runtime.events")).all())
                for secret in (PASSWORD, first.token, first.view.csrf_token, "$argon2id$"):
                    self.assertNotIn(secret, facts)
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM product.auth_sessions")), 2
                )
                self.assertEqual(connection.scalar(text("SELECT count(*) FROM runtime.events")), 6)

        asyncio.run(self.execute(scenario))

    def test_account_limit_survives_restart_and_expires(self) -> None:
        async def scenario(service: AuthService) -> None:
            for _ in range(5):
                with self.assertRaises(AuthError) as failure:
                    await service.sign_in("alpha", "incorrect-password-value", "127.0.0.1", None)
                self.assertEqual(failure.exception.status, 401)
            restarted = AuthService(service.engine)
            await restarted.initialize()
            with self.assertRaises(AuthError) as blocked:
                await restarted.sign_in("alpha", PASSWORD, "127.0.0.2", None)
            self.assertEqual(blocked.exception.status, 429)
            self.assertGreater(blocked.exception.retry_after or 0, 0)
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE product.login_attempts SET admitted_at=now()-interval '16 minutes'"
                    )
                )
            await restarted.sign_in("alpha", PASSWORD, "127.0.0.1", None)

        asyncio.run(self.execute(scenario))

    def test_account_switch_does_not_revoke_another_browser(self) -> None:
        async def scenario(service: AuthService) -> None:
            first = await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
            other = await service.sign_in("alpha", PASSWORD, "127.0.0.2", None)
            await service.sign_in("beta", PASSWORD, "127.0.0.1", first.token)
            with self.assertRaises(AuthError):
                await service.session(first.token)
            self.assertEqual(await service.session(other.token), other.view)

        asyncio.run(self.execute(scenario))

    def test_source_limit_and_unknown_account(self) -> None:
        async def scenario(service: AuthService) -> None:
            for number in range(60):
                with self.assertRaises(AuthError) as invalid:
                    await service.sign_in(f"unknown-{number}", PASSWORD, "127.0.0.1", None)
                self.assertEqual(invalid.exception.status, 401)
            with self.assertRaises(AuthError) as blocked:
                await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
            self.assertEqual(blocked.exception.status, 429)
            with self.assertRaises(AuthError) as unknown:
                await service.sign_in("missing", PASSWORD, "127.0.0.2", None)
            self.assertEqual(unknown.exception.message, "账号或密码不正确。")

        asyncio.run(self.execute(scenario))

    def test_expiry_password_change_and_disabled_account(self) -> None:
        async def scenario(service: AuthService) -> None:
            login = await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
            with self.engine.begin() as connection:
                connection.execute(text("UPDATE product.credentials SET credential_revision=2"))
            with self.assertRaises(AuthError):
                await service.session(login.token)
            login = await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE product.auth_sessions SET created_at=now()-interval '25 hours', "
                        "expires_at=now()-interval '1 hour'"
                    )
                )
            with self.assertRaises(AuthError):
                await service.session(login.token)
            with self.engine.begin() as connection:
                connection.execute(text("UPDATE product.accounts SET status='disabled'"))
            with self.assertRaises(AuthError) as disabled:
                await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
            self.assertEqual(disabled.exception.status, 401)

        asyncio.run(self.execute(scenario))

    def test_hash_capacity_and_password_change_during_verification(self) -> None:
        async def scenario(service: AuthService) -> None:
            with patch.object(service, "_hashes", 2):
                with self.assertRaises(AuthError) as busy:
                    await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
                self.assertEqual(busy.exception.status, 503)
            original = service.hasher.verify

            def change(password: str, hashed: str) -> bool:
                valid = original(password, hashed)
                with self.engine.begin() as connection:
                    connection.execute(text("UPDATE product.credentials SET credential_revision=2"))
                return valid

            with patch.object(service.hasher, "verify", side_effect=change):
                with self.assertRaises(AuthError) as changed:
                    await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
            self.assertEqual(changed.exception.status, 401)
            with self.engine.connect() as connection:
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM product.auth_sessions")), 0
                )

        asyncio.run(self.execute(scenario))

    def test_event_failure_rolls_back_session_and_old_revocation(self) -> None:
        async def scenario(service: AuthService) -> None:
            login = await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
            with patch.object(service.store, "append", side_effect=RuntimeError("test")):
                with self.assertRaises(RuntimeError):
                    await service.sign_in("beta", PASSWORD, "127.0.0.1", login.token)
            self.assertEqual(await service.session(login.token), login.view)
            with self.engine.connect() as connection:
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM product.auth_sessions")), 1
                )
            async with service.engine.begin() as connection:
                with self.assertRaises(DBAPIError):
                    await connection.execute(text("UPDATE product.accounts SET role='admin'"))

        asyncio.run(self.execute(scenario))

    def test_only_two_password_checks_run_at_once(self) -> None:
        async def scenario(service: AuthService) -> None:
            loop = asyncio.get_running_loop()
            both_started = asyncio.Event()
            release = threading.Event()
            lock = threading.Lock()
            started = 0
            original = service.hasher.verify

            def controlled(password: str, hashed: str) -> bool:
                nonlocal started
                with lock:
                    started += 1
                    if started == 2:
                        loop.call_soon_threadsafe(both_started.set)
                if not release.wait(10):
                    raise RuntimeError("Test did not release verification")
                return original(password, hashed)

            with patch.object(service.hasher, "verify", side_effect=controlled):
                tasks = [
                    asyncio.create_task(service.sign_in(name, PASSWORD, "127.0.0.1", None))
                    for name in ("alpha", "beta")
                ]
                try:
                    await asyncio.wait_for(both_started.wait(), timeout=5)
                    with self.assertRaises(AuthError) as busy:
                        await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
                    self.assertEqual(busy.exception.status, 503)
                    self.assertEqual(started, 2)
                finally:
                    release.set()
                    await asyncio.gather(*tasks)

        asyncio.run(self.execute(scenario))

    def test_http_cookie_csrf_origin_and_error_redaction(self) -> None:
        async def scenario(service: AuthService) -> None:
            app = create_app()
            app.state.auth = service
            app.state.auth_config = AuthConfig(frozenset({"http://127.0.0.1"}), True)

            async def request(
                path: str,
                body: dict[str, object] | None = None,
                headers: dict[str, str] | None = None,
            ) -> tuple[int, dict[str, str], str]:
                outgoing: list[Message] = []
                raw = json.dumps(body).encode() if body is not None else b""
                values = {
                    "host": "127.0.0.1",
                    "origin": "http://127.0.0.1",
                    "content-type": "application/json",
                    **(headers or {}),
                }
                scope: Scope = {
                    "type": "http",
                    "asgi": {"version": "3.0"},
                    "http_version": "1.1",
                    "method": "POST" if body is not None else "GET",
                    "scheme": "http",
                    "path": "/api/m1/auth/" + path,
                    "raw_path": b"",
                    "query_string": b"",
                    "headers": [(k.encode(), v.encode()) for k, v in values.items()],
                    "client": ("127.0.0.1", 1234),
                    "server": ("127.0.0.1", 80),
                }

                async def receive() -> Message:
                    return {"type": "http.request", "body": raw, "more_body": False}

                async def send(message: Message) -> None:
                    outgoing.append(message)

                await app(scope, receive, send)
                response = outgoing[0]
                return (
                    response["status"],
                    {k.decode(): v.decode() for k, v in response["headers"]},
                    b"".join(m.get("body", b"") for m in outgoing[1:]).decode(),
                )

            status, headers, body = await request(
                "sign-in", {"login_identifier": "alpha", "password": PASSWORD}
            )
            self.assertEqual(status, 200, body)
            cookie = headers["set-cookie"]
            for flag in ("HttpOnly", "SameSite=lax", "Max-Age=86400", "Path=/"):
                self.assertIn(flag, cookie)
            self.assertNotIn("Secure", cookie)
            self.assertNotIn("csrf_token", body)
            status, _, body = await request("session", headers={"cookie": cookie.split(";")[0]})
            self.assertEqual(status, 200, body)
            status, _, body = await request("sign-out", {}, {"cookie": cookie.split(";")[0]})
            self.assertEqual(status, 403)
            status, _, _ = await request(
                "sign-in",
                {"login_identifier": "alpha", "password": PASSWORD},
                {"origin": "https://evil.test"},
            )
            self.assertEqual(status, 403)
            status, _, body = await request("sign-in", {"password": PASSWORD, "role": "admin"})
            self.assertEqual(status, 400)
            self.assertNotIn(PASSWORD, body)
            app.state.auth_config = AuthConfig(frozenset({"https://127.0.0.1"}), False)
            status, headers, _ = await request(
                "sign-in",
                {"login_identifier": "beta", "password": PASSWORD},
                {"origin": "https://127.0.0.1"},
            )
            self.assertEqual(status, 200)
            self.assertIn("__Host-dm_session", headers["set-cookie"])
            self.assertIn("Secure", headers["set-cookie"])

        asyncio.run(self.execute(scenario))

    def test_rebuild_does_not_restore_logged_out_sessions(self) -> None:
        async def scenario(service: AuthService) -> None:
            login = await service.sign_in("alpha", PASSWORD, "127.0.0.1", None)
            await service.sign_out(login.token, str(login.view.session_id), login.view.csrf_token)
            maintenance = create_async_engine(self.migrator, poolclass=NullPool)
            try:
                with tempfile.TemporaryDirectory() as directory:
                    rebuilder = account_rebuilder(
                        maintenance, LocalFiles(Path(directory), backend="local")
                    )
                    job = await rebuilder.prepare(
                        uuid4(),
                        2,
                        [login.view.account.account_id],
                        operator="test",
                        authorization="test",
                    )
                    job = await rebuilder.resume(
                        job.rebuild_id, operator="test", authorization="test"
                    )
                    self.assertEqual(job.state, "completed")
                with self.assertRaises(AuthError):
                    await service.session(login.token)
            finally:
                await maintenance.dispose()

        asyncio.run(self.execute(scenario))
