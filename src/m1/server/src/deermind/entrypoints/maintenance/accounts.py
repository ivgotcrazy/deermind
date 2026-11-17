"""受控账号命令：明确数据库目标、隐藏密码、验证管理员；不增加网页管理入口。"""

import argparse
import asyncio
import getpass
import logging
import sys
from pathlib import Path
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.bootstrap.accounts import configure_account_management, configure_usage
from deermind.bootstrap.database import DatabaseSettings
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.database.connection import application_engine
from deermind.product.public.authentication import AuthError
from deermind.product.public.errors import RequestConflict
from deermind.product.public.notice import TEST_NOTICE, TEST_NOTICE_TEXT
from deermind.product.public.usage import ConfirmationInput, ConfirmUsageRequest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

LOGGER = logging.getLogger("product.accounts")


def password(label: str, *, confirm: bool = False) -> str:
    if not sys.stdin.isatty():
        raise ValueError("Passwords require an interactive terminal")
    value = getpass.getpass(label)
    if confirm and value != getpass.getpass("再次输入密码："):
        raise ValueError("两次密码不同")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="M1受控账号管理；仅支持合成学生账号")
    commands = result.add_subparsers(dest="action", required=True)
    bootstrap = commands.add_parser("bootstrap-admin")
    bootstrap.add_argument("--operator", required=True)
    bootstrap.add_argument("--login", required=True)
    bootstrap.add_argument("--name", required=True)
    create = commands.add_parser("create-student")
    create.add_argument("--admin", required=True)
    create.add_argument("--request-id", type=UUID, required=True)
    create.add_argument("--login", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--guardian-name", required=True)
    create.add_argument("--verification", required=True)
    create.add_argument("--synthetic", action="store_true", required=True)
    update = commands.add_parser("update-student")
    update.add_argument("--admin", required=True)
    update.add_argument("--request-id", type=UUID, required=True)
    update.add_argument("--account-id", type=UUID, required=True)
    update.add_argument("--expected-revision", type=int, required=True)
    update.add_argument("--login", required=True)
    update.add_argument("--name", required=True)
    consent = commands.add_parser("record-guardian-consent")
    consent.add_argument("--admin", required=True)
    consent.add_argument("--request-id", type=UUID, required=True)
    consent.add_argument("--account-id", type=UUID, required=True)
    consent.add_argument("--expected-revision", type=int, required=True)
    consent.add_argument("--verification", required=True)
    consent.add_argument("--decision", choices=["accepted", "declined", "pending"], required=True)
    consent.add_argument("--files-root", type=Path, required=True)
    for name in ("reset-student-password", "recover-admin"):
        reset = commands.add_parser(name)
        reset.add_argument(
            "--admin" if name == "reset-student-password" else "--operator", required=True
        )
        reset.add_argument("--request-id", type=UUID, required=True)
        reset.add_argument("--account-id", type=UUID, required=True)
        reset.add_argument("--expected-revision", type=int, required=True)
        reset.add_argument("--verification", required=True)
    return result


async def execute(args: argparse.Namespace) -> None:
    settings = DatabaseSettings.from_environment()
    print(f"目标数据库：{settings.host}:{settings.port}/{settings.name}；操作：{args.action}")
    engine = application_engine(settings.url())
    login = None
    auth = None
    try:
        manager, auth = await configure_account_management(engine)
        if args.action == "bootstrap-admin":
            receipt = await manager.bootstrap(
                login=args.login,
                name=args.name,
                operator=args.operator,
                password=password("初始管理员密码：", confirm=True),
            )
        else:
            if args.action != "recover-admin":
                login = await auth.sign_in(
                    args.admin, password("管理员密码："), "management-cli", None
                )
            verification = Ref(
                owner="product",
                type="synthetic_verification",
                id=getattr(args, "verification", "not-used"),
            )
            if args.action == "create-student" and login:
                receipt = await manager.create_student(
                    login.view,
                    request_id=args.request_id,
                    login=args.login,
                    name=args.name,
                    password=password("测试学生密码：", confirm=True),
                    guardian_name=args.guardian_name,
                    verification_ref=verification,
                    synthetic=args.synthetic,
                )
            elif args.action == "update-student" and login:
                receipt = await manager.update_student(
                    login.view,
                    account_id=args.account_id,
                    request_id=args.request_id,
                    expected_revision=args.expected_revision,
                    login=args.login,
                    name=args.name,
                )
            elif args.action == "record-guardian-consent" and login:
                print(TEST_NOTICE_TEXT)
                if input("确认已按这份测试告知核实该决定？输入 yes：") != "yes":
                    raise ValueError("未确认，不保存")
                service = configure_usage(engine, args.files_root)
                result = await service.confirm(
                    login.view,
                    ConfirmUsageRequest(
                        request_id=args.request_id,
                        expected_revision=args.expected_revision,
                        confirmation=ConfirmationInput(
                            student_id=args.account_id,
                            kind="guardian_consent",
                            notice_ref=TEST_NOTICE,
                            decision=args.decision,
                            source_ref=verification,
                        ),
                    ),
                )
                print(result.model_dump_json())
                return
            else:
                receipt = await manager.recover(
                    login.view if login else None,
                    account_id=args.account_id,
                    request_id=args.request_id,
                    expected_revision=args.expected_revision,
                    verification_ref=verification,
                    password=password("新密码：", confirm=True),
                    operator=getattr(args, "operator", None),
                )
        print(
            f"已保存。收据：{receipt.request_ref}；"
            f"结果：{receipt.result_ref.model_dump_json() if receipt.result_ref else ''}"
        )
    finally:
        if login and auth:
            await auth.sign_out(login.token, str(login.view.session_id), login.view.csrf_token)
        await engine.dispose()


def main() -> None:
    args = parser().parse_args()
    configure_logging()
    try:
        asyncio.run(execute(args))
    except AuthError as error:
        print(error.message, file=sys.stderr)
        raise SystemExit(1) from None
    except (ValueError, ValidationError, RequestConflict, IntegrityError):
        print("输入或记录发生冲突；未保存本次变更，请核对后重试。", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        # 数据库错误可能带业务参数，命令不直接打印异常对象或密码。
        LOGGER.error(
            "账号操作失败，请检查数据库及运行日志",
            extra={
                "action": args.action,
                "outcome": "failed",
                "error_code": "ACCOUNT_COMMAND_FAILED",
            },
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
