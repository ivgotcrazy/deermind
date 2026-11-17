"""认证合同的秘密隔离和账号归属；不连接数据库或部署登录入口。"""

import unittest
from ipaddress import ip_network
from uuid import uuid4

from deermind.abstractions.events import EventDraft, Ref
from deermind.entrypoints.api.auth import source_address
from deermind.product.accounts.auth_facts import AccountSignedIn, validate_auth_fact
from deermind.product.public.auth_config import AuthConfig
from deermind.product.public.authentication import SignInRequest
from pydantic import ValidationError
from starlette.requests import Request


class AuthContractTests(unittest.TestCase):
    def test_http_is_local_only_and_origins_are_exact(self) -> None:
        for origin in ("http://example.com", "http://127.0.0.1/path", "http://user@localhost"):
            with self.assertRaises(ValueError):
                AuthConfig(frozenset({origin}), True)
        with self.assertRaises(ValueError):
            AuthConfig(frozenset({"http://localhost"}), False)
        self.assertEqual(
            AuthConfig(frozenset({"https://example.com"}), False).cookie_name, "__Host-dm_session"
        )

    def test_forwarded_ip_requires_trusted_proxy(self) -> None:
        request = Request(
            {
                "type": "http",
                "client": ("10.42.0.15", 1234),
                "headers": [(b"x-real-ip", b"192.0.2.10")],
            }
        )
        config = AuthConfig(frozenset({"http://localhost"}), True)
        self.assertEqual(source_address(request, config), "10.42.0.15")
        config = AuthConfig(frozenset({"http://localhost"}), True, (ip_network("10.42.0.0/24"),))
        self.assertEqual(source_address(request, config), "192.0.2.10")

    def test_password_is_masked_and_role_is_not_accepted(self) -> None:
        """请求表示隐藏密码，客户端不能额外声明管理员角色。"""
        value = {"login_identifier": "test-user", "password": "synthetic-password"}
        request = SignInRequest.model_validate(value)
        self.assertNotIn(value["password"], repr(request))
        self.assertNotIn(value["password"], request.model_dump_json())
        self.assertEqual(request.password.get_secret_value(), value["password"])
        with self.assertRaises(ValidationError):
            SignInRequest.model_validate({**value, "role": "admin"})

    def test_authentication_fact_has_no_credentials_and_must_match_account(self) -> None:
        """成功登录留痕只含非秘密身份，不能错挂到其他账号。"""
        account = uuid4()
        payload = AccountSignedIn(records=[], account_id=account, session_id=uuid4())
        owner = Ref(owner="product", type="account", id=str(account))
        draft = EventDraft(
            uuid4(),
            "AccountSignedIn",
            1,
            "account",
            account,
            owner,
            payload.model_dump(mode="json"),
            None,
        )
        validate_auth_fact(draft, payload)
        with self.assertRaises(ValidationError):
            AccountSignedIn.model_validate({**payload.model_dump(), "token": "not-allowed"})
        with self.assertRaises(ValueError):
            validate_auth_fact(draft, payload.model_copy(update={"account_id": uuid4()}))
