"""合成学生首次使用的浏览器夹具；复用隔离库和真实API，不改正式库。"""

import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from auth_browser import main
from deermind.bootstrap.accounts import configure_account_management, configure_usage
from deermind.infrastructure.database.connection import application_engine
from deermind.product.public.notice import TEST_NOTICE
from deermind.product.public.usage import ConfirmationInput, ConfirmUsageRequest
from test_account_usage import PASSWORD, VERIFICATION
from test_database import DatabaseTestCase


async def seed(fixture: DatabaseTestCase) -> None:
    maintenance = application_engine(fixture.migrator)
    engine = application_engine(fixture.app)
    try:
        manager, _ = await configure_account_management(maintenance)
        await manager.bootstrap(
            login="operator", name="合成管理员", password=PASSWORD, operator="browser-test"
        )
        manager, auth = await configure_account_management(engine)
        login = await auth.sign_in("operator", PASSWORD, "127.0.0.1", None)
        created = await manager.create_student(
            login.view,
            request_id=uuid4(),
            login="student",
            name="合成学生",
            password=PASSWORD,
            guardian_name="合成监护人",
            verification_ref=VERIFICATION,
            synthetic=True,
        )
        assert created.result_ref is not None
        with tempfile.TemporaryDirectory() as directory:
            service = configure_usage(engine, Path(directory))
            await service.confirm(
                login.view,
                ConfirmUsageRequest(
                    request_id=uuid4(),
                    expected_revision=1,
                    confirmation=ConfirmationInput(
                        student_id=UUID(created.result_ref.id),
                        kind="guardian_consent",
                        notice_ref=TEST_NOTICE,
                        decision="accepted",
                        source_ref=VERIFICATION,
                    ),
                ),
            )
        await auth.sign_out(login.token, str(login.view.session_id), login.view.csrf_token)
    finally:
        await engine.dispose()
        await maintenance.dispose()


if __name__ == "__main__":
    main(seed)
