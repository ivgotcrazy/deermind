"""真实 PostgreSQL 与生产 API 的领域根保存、归属和回滚验证。"""

import asyncio
import tempfile
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic import command
from deermind.abstractions.events import Ref, StoredEvent
from deermind.entrypoints.api.app import create_app
from deermind.entrypoints.maintenance.database import migration_config, upgrade
from deermind.foundation.system.public.errors import ErrorDetail
from deermind.product.public.authentication import SessionView
from fastapi.testclient import TestClient
from httpx2 import Response
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from test_account_usage import PASSWORD
from test_database import DatabaseTestCase
from test_realtime_integration import session_headers
from usage_browser import seed

_ORIGIN = "http://127.0.0.1"
_LIST = "/api/m1/domains"
_SAVE = "/api/m1/domain-definitions"
_RECEIPT = "/api/m1/requests/receipt"
_ACTION = "domain.save_definition"


def _body(request_id: UUID, name: str) -> dict[str, JsonValue]:
    return {
        "request_id": str(request_id),
        "object_kind": "domain",
        "action": "create",
        "definition": {"name": name, "coverage": None, "description": None},
        "change_note": "首次登记领域",
    }


def _content(text_value: str, *, with_formula: bool = False) -> dict[str, JsonValue]:
    spans: list[JsonValue] = [{"type": "text", "text": text_value}]
    if with_formula:
        spans.append(
            {"type": "math", "expression": {"op": "number", "value": "4", "cancel_to": []}}
        )
    return {
        "schema_version": "1",
        "role": "definition",
        "blocks": [
            {
                "type": "paragraph",
                "block_id": "p-1",
                "payload": {"spans": spans},
                "provenance": {"source_refs": [], "transformation": "generated"},
            },
        ],
        "data_tables": [],
        "source_refs": [],
    }


def _login(client: TestClient, identifier: str) -> SessionView:
    response = client.post(
        "/api/m1/auth/sign-in",
        headers={"Origin": _ORIGIN},
        json={"login_identifier": identifier, "password": PASSWORD},
    )
    response.raise_for_status()
    response = client.get("/api/m1/auth/session")
    return SessionView.model_validate_json(response.raise_for_status().content)


def _save(client: TestClient, session: SessionView, body: dict[str, JsonValue]) -> Response:
    return client.post(_SAVE, headers={"Origin": _ORIGIN, **session_headers(session)}, json=body)


def _receipt(
    client: TestClient, session: SessionView, request_id: UUID, owner_id: UUID
) -> Response:
    return client.get(
        _RECEIPT,
        headers=session_headers(session),
        params={
            "action": _ACTION,
            "resource_kind": "account",
            "resource_id": str(owner_id),
            "request_id": str(request_id),
        },
    )


class DomainTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        asyncio.run(seed(self))

    @contextmanager
    def api(self) -> Generator[TestClient]:
        """以隔离库启动真实认证、路由、收据登记和服务。"""
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                "M1_DB_HOST": str(self.app.host),
                "M1_DB_PORT": str(self.app.port),
                "M1_DB_NAME": self.name,
                "M1_DB_USER": "deermind_app",
                "M1_DB_PASSWORD": str(self.app.password),
                "M1_FILES_ROOT": directory,
                "M1_FILES_BACKEND": "local",
                "M1_TEMPORAL_ADDRESS": "127.0.0.1:1",
                "M1_TEMPORAL_NAMESPACE": "domain-test",
                "M1_TASK_QUEUE": "unused",
                "M1_AUTH_ORIGINS": _ORIGIN,
                "M1_AUTH_LOCAL_HTTP": "true",
                "M1_AUTH_TRUSTED_PROXIES": "",
            }
            with (
                patch.dict("os.environ", environment, clear=True),
                TestClient(
                    create_app(),
                    base_url=_ORIGIN,
                    client=("127.0.0.1", 41000),
                    raise_server_exceptions=False,
                ) as client,
            ):
                yield client

    def persisted_counts(self) -> tuple[int, ...]:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM domain.object_identity),"
                    " (SELECT count(*) FROM domain.object_version),"
                    " (SELECT count(*) FROM domain.command_receipt),"
                    " (SELECT count(*) FROM runtime.events"
                    " WHERE event_type='DomainDefinitionSaved'),"
                    " (SELECT count(*) FROM runtime.projection_receipts p JOIN runtime.events e"
                    " USING (event_id) WHERE e.event_type='DomainDefinitionSaved'),"
                    " (SELECT count(*) FROM runtime.scope_event_heads WHERE scope_kind='domain')"
                )
            ).one()
        return tuple(row)

    def test_knowledge_versions_catalog_and_original_receipt(self) -> None:
        """并行提交同一旧版，仅一个生效；删除后仍保留原文与原收据。"""
        request_id = uuid4()
        with self.api() as client:
            admin = _login(client, "operator")
            headers = session_headers(admin)
            root = _save(client, admin, _body(uuid4(), "数学")).raise_for_status().json()
            other = _save(client, admin, _body(uuid4(), "物理")).raise_for_status().json()
            domain_id, other_id = (
                item["result"]["object_ref"]["object_id"] for item in (root, other)
            )
            catalog = f"{_LIST}/{domain_id}/objects"
            definition: dict[str, JsonValue] = {
                "name": "等分",
                "definition": _content("分母", with_formula=True),
                "applicability": _content("平均分"),
            }
            create: dict[str, JsonValue] = {
                "request_id": str(request_id),
                "object_kind": "kc",
                "action": "create",
                "domain_id": domain_id,
                "change_note": "登记",
                "definition": definition,
            }
            invalid: dict[str, JsonValue] = {
                **create,
                "definition": {**definition, "applicability": {}},
            }
            rejected = _save(client, admin, invalid)
            self.assertEqual(rejected.status_code, 400)
            self.assertTrue(
                any(
                    issue["path"].startswith("/definition/applicability")
                    for issue in rejected.json()["error"]["issues"]
                )
            )
            original = _save(client, admin, create).raise_for_status().json()
            ref = original["result"]["object_ref"]
            object_id = ref["object_id"]
            path = f"{catalog}/{object_id}"
            before = client.get(path, headers=headers).raise_for_status().json()["object"]
            self.assertEqual(
                before["content"]["definition"]["blocks"][0]["payload"]["spans"][1],
                {"type": "math", "expression": {"op": "number", "value": "4", "cancel_to": []}},
            )
            self.assertEqual(
                client.get(f"{_LIST}/{other_id}/objects/{object_id}", headers=headers).status_code,
                404,
            )
            _save(
                client,
                admin,
                {
                    **create,
                    "request_id": str(uuid4()),
                    "definition": {
                        **before["content"],
                        "name": "细分",
                    },
                },
            ).raise_for_status()
            page = (
                client.get(catalog, headers=headers, params={"limit": 1}).raise_for_status().json()
            )
            self.assertTrue(page["next_cursor"])
            next_page = (
                client.get(
                    catalog, headers=headers, params={"cursor": page["next_cursor"], "limit": 1}
                )
                .raise_for_status()
                .json()
            )
            self.assertNotEqual(page["items"][0]["object_ref"], next_page["items"][0]["object_ref"])
            base = {
                "object_kind": "kc",
                "action": "update",
                "object_ref": ref,
                "expected_version": 1,
                "change_note": "补充适用条件",
            }

            def revise(text_value: str) -> Response:
                return _save(
                    client,
                    admin,
                    {
                        **base,
                        "request_id": str(uuid4()),
                        "definition": {**before["content"], "applicability": _content(text_value)},
                    },
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(revise, ("四块", "五块")))
            self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
            self.assertEqual(
                next(r for r in responses if r.status_code == 409).json()["error"]["code"],
                "version_conflict",
            )
            current = client.get(path, headers=headers).raise_for_status().json()["object"]
            self.assertEqual(current["object_ref"]["version"], 2)
            self.assertEqual(current["content"]["definition"], before["content"]["definition"])
            self.assertEqual(
                client.get(catalog, headers=headers, params={"cursor": page["next_cursor"]}).json()[
                    "error"
                ]["code"],
                "read_range_changed",
            )
            deletion = {
                **base,
                "request_id": str(uuid4()),
                "action": "soft_delete",
                "object_ref": current["object_ref"],
                "expected_version": 2,
            }
            removed = _save(client, admin, deletion).raise_for_status().json()
            self.assertEqual(removed["result"]["object_ref"]["version"], 3)
            self.assertEqual(client.get(path, headers=headers).status_code, 404)
            listing = client.get(catalog, headers=headers).raise_for_status().json()["items"]
            self.assertEqual([item["name"] for item in listing], ["细分"])
            history = client.get(path, headers=headers, params={"version": 1}).raise_for_status()
            self.assertEqual(history.json()["object"], {**before, "is_identity_deleted": True})
            replay = _receipt(client, admin, request_id, admin.account.account_id)
            self.assertEqual(replay.raise_for_status().json()["result"], original["result"])
            self.assertEqual(_save(client, admin, create).raise_for_status().json(), original)
            self.assertEqual(_save(client, admin, deletion).raise_for_status().json(), removed)
            self.assertEqual(self.persisted_counts(), (4, 6, 6, 6, 6, 2))

    def test_task_conditions_versions_and_separate_cognitive_responsibilities(self) -> None:
        """解释和计算各有身份；非法条件不保存，修订保留精确版本与原收据。"""
        with self.api() as client:
            admin = _login(client, "operator")
            headers = session_headers(admin)
            root = _save(client, admin, _body(uuid4(), "路程与速度")).raise_for_status().json()
            domain_id = root["result"]["object_ref"]["object_id"]
            catalog = f"{_LIST}/{domain_id}/objects"
            request_id = uuid4()
            definition: dict[str, JsonValue] = {
                "name": "解释匀速路程关系",
                "responsibility": _content("说明单位时间路程如何累积"),
                "expected_output": _content("说明速度、时间和路程之间的关系"),
                "completion_conditions": _content("能解释每个量的意义", with_formula=True),
                "applicability": _content("速度保持不变，单位相容"),
                "boundaries": _content("排除变速运动"),
                "parameters": [
                    {"name": "t", "meaning": "行进时间", "type": "数值", "constraints": "t > 0"}
                ],
            }
            create: dict[str, JsonValue] = {
                "request_id": str(request_id),
                "object_kind": "task",
                "action": "create",
                "domain_id": domain_id,
                "change_note": "定义解释责任",
                "definition": definition,
            }
            invalid_cases: tuple[tuple[str, JsonValue, str], ...] = (
                ("completion_conditions", _content("  "), "/definition/completion_conditions"),
                (
                    "applicability",
                    {**_content("条件"), "role": "statement"},
                    "/definition/applicability",
                ),
                (
                    "parameters",
                    [
                        {"name": "t", "meaning": "时间", "type": "数值", "constraints": "t > 0"},
                        {"name": " t ", "meaning": "时刻", "type": "数值", "constraints": "t > 1"},
                    ],
                    "/definition/parameters/1/name",
                ),
            )
            for field, value, expected_path in invalid_cases:
                rejected = _save(
                    client, admin, {**create, "definition": {**definition, field: value}}
                )
                self.assertEqual(rejected.status_code, 400)
                self.assertTrue(
                    any(
                        issue["path"].startswith(expected_path)
                        for issue in rejected.json()["error"]["issues"]
                    )
                )
            self.assertEqual(self.persisted_counts(), (1,) * 6)
            explanation = _save(client, admin, create).raise_for_status().json()
            self.assertEqual(
                [gap["path"] for gap in explanation["result"]["gaps"]], ["/method_refs"]
            )
            ref = explanation["result"]["object_ref"]
            path = f"{catalog}/{ref['object_id']}"
            before = client.get(path, headers=headers).raise_for_status().json()["object"]
            calculation = (
                _save(
                    client,
                    admin,
                    {
                        **create,
                        "request_id": str(uuid4()),
                        "definition": {
                            "name": "根据匀速与时间求路程",
                            "responsibility": _content("根据给定数值计算路程"),
                        },
                    },
                )
                .raise_for_status()
                .json()
            )
            self.assertNotEqual(calculation["result"]["object_ref"]["object_id"], ref["object_id"])
            self.assertIn(
                "/completion_conditions", [g["path"] for g in calculation["result"]["gaps"]]
            )
            listing = client.get(catalog, headers=headers, params={"kinds": "task"})
            self.assertEqual(len(listing.raise_for_status().json()["items"]), 2)
            knowledge = client.get(catalog, headers=headers, params={"kinds": "kc"})
            self.assertEqual(knowledge.raise_for_status().json()["items"], [])
            revision: dict[str, JsonValue] = {
                "request_id": str(uuid4()),
                "object_kind": "task",
                "action": "update",
                "object_ref": ref,
                "expected_version": 1,
                "change_note": "补充适用条件",
                "definition": {**before["content"], "applicability": _content("全程保持匀速")},
            }
            updated = _save(client, admin, revision).raise_for_status().json()
            current_ref = updated["result"]["object_ref"]
            self.assertEqual(current_ref["version"], 2)
            stale = _save(client, admin, {**revision, "request_id": str(uuid4())})
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(stale.json()["error"]["code"], "version_conflict")
            history = client.get(path, headers=headers, params={"version": 1}).raise_for_status()
            self.assertEqual(history.json()["object"], before)
            self.assertEqual(
                _receipt(client, admin, request_id, admin.account.account_id).json()["result"],
                explanation["result"],
            )
            self.assertEqual(_save(client, admin, create).raise_for_status().json(), explanation)
            removed = (
                _save(
                    client,
                    admin,
                    {
                        "request_id": str(uuid4()),
                        "object_kind": "task",
                        "action": "soft_delete",
                        "object_ref": current_ref,
                        "expected_version": 2,
                        "change_note": "移除试验定义",
                    },
                )
                .raise_for_status()
                .json()
            )
            self.assertEqual(removed["result"]["object_ref"]["version"], 3)
            self.assertEqual(client.get(path, headers=headers).status_code, 404)
            old = client.get(path, headers=headers, params={"version": 1}).raise_for_status().json()
            self.assertEqual(old["object"], {**before, "is_identity_deleted": True})
            self.assertEqual(self.persisted_counts(), (3, 5, 5, 5, 5, 1))

    def test_solution_relationships_exact_versions_scope_and_cycles(self) -> None:
        """固定版本可追溯，全量与方法过滤都不把先导知识纳入。"""
        with self.api() as client:
            admin = _login(client, "operator")
            headers = session_headers(admin)
            root = _save(client, admin, _body(uuid4(), "分数")).raise_for_status().json()
            other = _save(client, admin, _body(uuid4(), "另一领域")).raise_for_status().json()
            domain_id = root["result"]["object_ref"]["object_id"]
            other_id = other["result"]["object_ref"]["object_id"]

            def create(
                kind: str, content: dict[str, JsonValue], *, domain: str = domain_id
            ) -> Response:
                return _save(
                    client,
                    admin,
                    {
                        "request_id": str(uuid4()),
                        "object_kind": kind,
                        "action": "create",
                        "domain_id": domain,
                        "definition": content,
                        "change_note": "建立定义",
                    },
                )

            def revise(
                kind: str, ref: dict[str, JsonValue], content: dict[str, JsonValue]
            ) -> Response:
                return _save(
                    client,
                    admin,
                    {
                        "request_id": str(uuid4()),
                        "object_kind": kind,
                        "action": "update",
                        "object_ref": ref,
                        "expected_version": ref["version"],
                        "definition": content,
                        "change_note": "修订定义",
                    },
                )

            def saved(response: Response) -> dict[str, JsonValue]:
                self.assertEqual(response.status_code, 200, response.text)
                return response.json()["result"]["object_ref"]

            knowledge: dict[str, JsonValue] = {
                "name": "分数的意义",
                "definition": _content("把整体平均分成若干份"),
                "applicability": _content("可以确定参照整体"),
            }
            kc1 = saved(create("kc", knowledge))
            kc2 = saved(revise("kc", kc1, {**knowledge, "name": "分数的意义（修订）"}))
            another = saved(create("kc", {**knowledge, "name": "等量乘法"}))
            foreign = saved(create("kc", knowledge, domain=other_id))
            invalid = create("solution", {"name": "跨领域", "kc_refs": [foreign]})
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(invalid.json()["error"]["issues"][0]["path"], "/kc_refs/0")
            invalid = create("task", {"name": "直接挂KC", "kc_refs": [kc1]})
            self.assertEqual(invalid.status_code, 400)
            first = saved(
                create(
                    "solution",
                    {
                        "name": "先求增加量",
                        "key_process": _content("求出增加量再相加"),
                        "kc_refs": [kc1, another],
                    },
                )
            )
            second = saved(create("solution", {"name": "直接乘新比例", "kc_refs": [kc2]}))
            prior_kc = saved(create("kc", {**knowledge, "name": "参照整体"}))
            prior_method = saved(
                create("solution", {"name": "辨认参照整体", "kc_refs": [prior_kc]})
            )
            prior = saved(create("task", {"name": "识别参照整体", "method_refs": [prior_method]}))
            task1 = saved(create("task", {"name": "增加四分之一"}))
            link: dict[str, JsonValue] = {
                "task_ref": prior,
                "reason": "先辨认参照整体",
                "applies_to": "specified",
                "method_refs": [first],
            }
            definition: dict[str, JsonValue] = {
                "name": "增加四分之一",
                "method_refs": [first, second],
                "prerequisites": [link],
            }
            invalid = revise(
                "task",
                task1,
                {
                    **definition,
                    "prerequisites": [{**link, "task_ref": task1}],
                },
            )
            self.assertEqual(invalid.json()["error"]["code"], "dependency_cycle")
            invalid = revise(
                "task",
                task1,
                {
                    **definition,
                    "prerequisites": [{**link, "applies_to": "all"}],
                },
            )
            self.assertEqual(invalid.json()["error"]["code"], "invalid_reference")
            task2 = saved(revise("task", task1, definition))
            cycle = revise(
                "task",
                prior,
                {
                    "name": "识别参照整体",
                    "prerequisites": [
                        {"task_ref": task2, "reason": "形成回路", "applies_to": "all"}
                    ],
                },
            )
            self.assertEqual(cycle.status_code, 400)
            self.assertEqual(cycle.json()["error"]["code"], "dependency_cycle")

            route = f"{_LIST}/{domain_id}/dependencies"
            query = {"task_id": str(task2["object_id"]), "version": 2}
            full = client.get(route, headers=headers, params=query).raise_for_status().json()
            self.assertEqual(full["method_refs"], [first, second])
            self.assertCountEqual(full["kc_refs"], [kc1, kc2, another])
            versions = next(
                group for group in full["kc_sources"] if group["kc_id"] == kc1["object_id"]
            )
            self.assertCountEqual(
                versions["uses"],
                [
                    {"method_ref": first, "kc_ref": kc1},
                    {"method_ref": second, "kc_ref": kc2},
                ],
            )
            a_only = (
                client.get(
                    route,
                    headers=headers,
                    params={**query, "solution_ids": str(first["object_id"])},
                )
                .raise_for_status()
                .json()
            )
            self.assertCountEqual(a_only["kc_refs"], [kc1, another])
            self.assertEqual(a_only["prerequisites"], [link])
            b_only = (
                client.get(
                    route,
                    headers=headers,
                    params={**query, "solution_ids": str(second["object_id"])},
                )
                .raise_for_status()
                .json()
            )
            self.assertEqual(b_only["kc_refs"], [kc2])
            self.assertEqual(b_only["prerequisites"], [])
            wrong_method = client.get(
                route,
                headers=headers,
                params={**query, "solution_ids": str(prior_method["object_id"])},
            )
            self.assertEqual(wrong_method.json()["error"]["code"], "invalid_reference")
            original = (
                client.get(route, headers=headers, params={**query, "version": 1})
                .raise_for_status()
                .json()
            )
            self.assertEqual(original["method_refs"], [])

            removed = _save(
                client,
                admin,
                {
                    "request_id": str(uuid4()),
                    "object_kind": "kc",
                    "action": "soft_delete",
                    "object_ref": kc2,
                    "expected_version": 2,
                    "change_note": "保留旧引用",
                },
            )
            removed.raise_for_status()
            invalid = create("solution", {"name": "不能新用已移除的知识", "kc_refs": [kc1]})
            self.assertEqual(invalid.json()["error"]["code"], "invalid_reference")
            self.assertEqual(
                client.get(route, headers=headers, params=query).raise_for_status().json(), full
            )

        with self.engine.connect() as connection:
            self.assertEqual(
                connection.scalar(text("SELECT count(*) FROM domain.object_reference")), 9
            )
            self.assertFalse(
                connection.scalar(
                    text(
                        "SELECT has_table_privilege("
                        "'deermind_app','domain.object_reference','DELETE')"
                    )
                )
            )

    def test_kc_direct_path_records_basis_and_preserves_old_versions(self) -> None:
        """引用和只代入都无确认，确认固定三版本，原收据和依据可查。"""
        with self.api() as client:
            admin = _login(client, "operator")
            headers = session_headers(admin)
            root = _save(client, admin, _body(uuid4(), "匀速路程")).raise_for_status().json()
            root_id = root["result"]["object_ref"]["object_id"]
            paths_url = f"{_LIST}/{root_id}/kc-test-paths"
            dependencies_url = f"{_LIST}/{root_id}/dependencies"

            def create(kind: str, content: dict[str, JsonValue]) -> dict[str, JsonValue]:
                reply = _save(
                    client,
                    admin,
                    {
                        "request_id": str(uuid4()),
                        "object_kind": kind,
                        "action": "create",
                        "domain_id": root_id,
                        "definition": content,
                        "change_note": "登记",
                    },
                )
                self.assertEqual(reply.status_code, 200, reply.text)
                return reply.json()["result"]["object_ref"]

            def confirm(payload: dict[str, JsonValue]) -> Response:
                return client.post(paths_url, json=payload, headers={"Origin": _ORIGIN, **headers})

            def states(ref: dict[str, JsonValue], version: int = 1) -> list[JsonValue]:
                return (
                    client.get(
                        dependencies_url,
                        headers=headers,
                        params={"task_id": str(ref["object_id"]), "version": version},
                    )
                    .raise_for_status()
                    .json()["kc_test_paths"]
                )

            def original(request_id: str) -> dict[str, JsonValue]:
                return (
                    client.get(
                        _RECEIPT,
                        headers=headers,
                        params={
                            "action": "domain.confirm_kc_path",
                            "resource_kind": "domain",
                            "resource_id": root_id,
                            "request_id": request_id,
                        },
                    )
                    .raise_for_status()
                    .json()
                )

            kc = create(
                "kc",
                {
                    "name": "匀速路程公式为何成立",
                    "definition": _content("每单位时间经过相同路程"),
                    "applicability": _content("匀速，单位一致"),
                },
            )
            method = create(
                "solution",
                {
                    "name": "按单位时间累加",
                    "rationale": _content("同样的量重复相加"),
                    "applicability": _content("每单位时间经过相同路程"),
                    "key_process": _content("用重复累加说明乘法"),
                    "kc_refs": [kc],
                },
            )
            draft_task = create("task", {"name": "只有引用", "method_refs": [method]})
            complete: dict[str, JsonValue] = {
                "name": "解释 d=v×t",
                "method_refs": [method],
                "responsibility": _content("解释速度的含义及路程怎样累加"),
                "expected_output": _content("说明每个量的意义"),
                "completion_conditions": _content("说明匀速条件与单位"),
            }
            good = create("task", complete)
            unassociated = create("task", {**complete, "name": "未采用方法", "method_refs": []})
            reference: dict[str, JsonValue] = {
                "kc_ref": kc,
                "solution_ref": method,
                "task_ref": good,
                "observable_behavior": "解释每单位时间的路程怎样累加，并说出匀速条件。",
                "insufficient_examples": ["只把 3 和 4 代入得 12"],
            }
            self.assertEqual(states(good), [])
            detached = confirm({**reference, "request_id": str(uuid4()), "task_ref": unassociated})
            self.assertEqual(detached.status_code, 400)
            self.assertEqual(detached.json()["error"]["code"], "invalid_reference")
            missing = confirm({**reference, "request_id": str(uuid4()), "task_ref": draft_task})
            self.assertEqual(missing.status_code, 409)
            self.assertEqual(missing.json()["error"]["code"], "not_ready")
            self.assertEqual(states(draft_task), [])

            negative_id = str(uuid4())
            negative: dict[str, JsonValue] = {
                **reference,
                "request_id": negative_id,
                "not_direct_reason": "当前证据只要求代入，没有直接观察解释责任。",
            }
            rejected = confirm(negative)
            self.assertEqual(rejected.status_code, 409)
            recovered = original(negative_id)
            self.assertEqual(recovered["receipt_state"], "rejected")
            self.assertEqual(
                ErrorDetail.model_validate(recovered["error"]),
                ErrorDetail.model_validate(rejected.json()["error"]),
            )
            self.assertTrue(recovered["result_refs"])
            self.assertEqual(confirm(negative).json(), rejected.json())
            self.assertEqual(states(good), [])

            positive_id = str(uuid4())
            positive = {**reference, "request_id": positive_id}
            approved = confirm(positive).raise_for_status().json()
            self.assertEqual(original(positive_id)["result"], approved["result"])
            self.assertEqual(confirm(positive).raise_for_status().json(), approved)
            duplicate = confirm({**positive, "request_id": str(uuid4())}).raise_for_status().json()
            self.assertEqual(duplicate["result"], approved["result"])
            snapshot = states(good)
            self.assertEqual(len(snapshot), 1)

            revised = _save(
                client,
                admin,
                {
                    "request_id": str(uuid4()),
                    "object_kind": "task",
                    "action": "update",
                    "object_ref": good,
                    "expected_version": 1,
                    "definition": {**complete, "name": "解释 d=v×t（修订）"},
                    "change_note": "核对旧确认保留",
                },
            )
            revised.raise_for_status()
            self.assertEqual(states(good, 2), [])
            self.assertEqual(states(good), snapshot)

        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM domain.kc_test_path")), 1)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM domain.artifact")), 3)
            events = connection.execute(
                text(
                    "SELECT event_type,jsonb_array_length(payload->'records') FROM runtime.events "
                    "WHERE event_type IN ('DomainKCTestPathConfirmed','DomainKCTestPathNotReady')"
                )
            ).all()
            self.assertCountEqual(
                events,
                [
                    ("DomainKCTestPathConfirmed", 2),
                    ("DomainKCTestPathNotReady", 1),
                    ("DomainKCTestPathNotReady", 1),
                ],
            )

    def test_create_list_details_replay_and_trace(self) -> None:
        first_request, second_request = uuid4(), uuid4()
        first_body = _body(first_request, "小学数学")
        second_body = _body(second_request, "基础物理")
        with self.api() as client:
            admin = _login(client, "operator")
            headers = session_headers(admin)
            self.assertEqual(client.get(_LIST, headers=headers).json(), {"items": []})
            first_response = _save(client, admin, first_body)
            second_response = _save(client, admin, second_body)
            self.assertEqual((first_response.status_code, second_response.status_code), (200, 200))
            first, second = first_response.json(), second_response.json()
            first_id = UUID(first["result"]["object_ref"]["object_id"])
            second_id = UUID(second["result"]["object_ref"]["object_id"])
            self.assertNotEqual(first_id, second_id)

            listing = client.get(_LIST, headers=headers).raise_for_status().json()["items"]
            self.assertEqual(
                {item["object_ref"]["object_id"]: item["name"] for item in listing},
                {str(first_id): "小学数学", str(second_id): "基础物理"},
            )
            for row in listing:
                self.assertEqual(row["object_ref"]["version"], 1)
                self.assertFalse(row["is_deleted"])

            for reply, root, request_id, body in (
                (first, first_id, first_request, first_body),
                (second, second_id, second_request, second_body),
            ):
                ref = {"kind": "domain", "object_id": str(root), "version": 1}
                self.assertEqual(reply["result"]["object_ref"], ref)
                self.assertEqual(
                    reply["result"]["content_ref"],
                    {"owner": "domain", "object_ref": ref, "path": ""},
                )
                self.assertEqual(reply["result"]["gaps"], [])
                path = f"{_LIST}/{root}/objects/{root}"
                detail = client.get(path, headers=headers).raise_for_status().json()["object"]
                history = client.get(path, headers=headers, params={"version": 1})
                self.assertEqual(history.raise_for_status().json()["object"], detail)
                self.assertEqual(
                    client.get(path, headers=headers, params={"version": 2}).status_code, 404
                )
                self.assertEqual(detail["object_ref"], ref)
                self.assertEqual(detail["content"], body["definition"])
                self.assertEqual(detail["content_ref"], reply["result"]["content_ref"])
                self.assertFalse(detail["is_identity_deleted"])
                event_id = UUID(detail["source_event_id"])
                matching = next(item for item in listing if item["object_ref"] == ref)
                self.assertEqual(matching["source_event_id"], str(event_id))
                self.assert_trace(
                    root, event_id, UUID(reply["request_ref"]), request_id, body, admin
                )
                recovered = _receipt(client, admin, request_id, admin.account.account_id)
                receipt = recovered.raise_for_status().json()
                self.assertEqual(receipt["receipt_state"], "completed")
                self.assertEqual(receipt["receipt_ref"], reply["request_ref"])
                self.assertEqual(receipt["result"], reply["result"])
                self.assertIsNone(receipt["execution_ref"])

            for root, foreign in ((first_id, second_id), (second_id, first_id)):
                missing = client.get(f"{_LIST}/{root}/objects/{uuid4()}", headers=headers)
                crossed = client.get(f"{_LIST}/{root}/objects/{foreign}", headers=headers)
                self.assertEqual(crossed.status_code, 404)
                self.assertEqual(crossed.json(), missing.json())
            self.assertEqual(_save(client, admin, first_body).raise_for_status().json(), first)
            self.assertEqual(_receipt(client, admin, first_request, uuid4()).status_code, 404)
            conflict = _save(client, admin, _body(first_request, "同键异内容"))
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(conflict.json()["error"]["code"], "request_conflict")
            self.assertEqual(
                _receipt(client, admin, first_request, admin.account.account_id).json()["result"],
                first["result"],
            )
            self.assertEqual(self.persisted_counts(), (2,) * 6)

    def assert_trace(
        self,
        root: UUID,
        event_id: UUID,
        receipt_ref: UUID,
        request_id: UUID,
        body: dict[str, JsonValue],
        creator: SessionView,
    ) -> None:
        """用数据库中的事件、身份、版本、投影及收据核对接口返回。"""
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT i.object_id,i.kind,i.domain_id,i.head_version,i.catalog_revision,"
                        " v.version,v.content,v.content_schema_version,v.is_deleted,v.created_at,"
                        " v.created_by,v.change_note,v.source_event_id,"
                        " e.event_type,e.producer,e.scope_kind,e.scope_id,e.correlation_id,"
                        " e.source_request_id,e.scope_event_seq,e.payload,"
                        " p.projector_id,p.generation"
                        " FROM domain.object_identity i JOIN domain.object_version v"
                        " ON v.object_id=i.object_id"
                        " JOIN runtime.events e ON v.source_event_id=e.event_id"
                        " JOIN runtime.projection_receipts p ON p.event_id=e.event_id"
                        " WHERE i.object_id=:id"
                    ),
                    {"id": root},
                )
                .mappings()
                .one()
            )
            own_receipt = connection.execute(
                text(
                    "SELECT receipt_id,scope_id,action,request_id FROM domain.command_receipt"
                    " WHERE receipt_id=:ref"
                ),
                {"ref": receipt_ref},
            ).one()
        self.assertEqual(
            tuple(own_receipt),
            (receipt_ref, str(creator.account.account_id), _ACTION, str(request_id)),
        )
        values = (
            row["object_id"],
            row["kind"],
            row["domain_id"],
            row["head_version"],
            row["catalog_revision"],
            row["version"],
            row["content_schema_version"],
            row["is_deleted"],
        )
        self.assertEqual(values, (root, "domain", None, 1, 1, 1, 1, False))
        self.assertEqual(row["content"], body["definition"])
        self.assertEqual(row["source_event_id"], event_id)
        self.assertEqual(row["event_type"], "DomainDefinitionSaved")
        self.assertEqual(
            (row["producer"], row["scope_kind"], row["scope_id"]), ("domain", "domain", root)
        )
        self.assertEqual(
            (row["correlation_id"], row["source_request_id"]), (receipt_ref, str(request_id))
        )
        self.assertEqual(row["scope_event_seq"], 1)
        self.assertEqual(row["projector_id"], "domain.definitions.v1")
        self.assertEqual(row["generation"], 1)

        payload = row["payload"]
        self.assertEqual(
            payload["object_ref"], {"kind": "domain", "object_id": str(root), "version": 1}
        )
        self.assertIsNone(payload["previous_ref"])
        self.assertEqual(payload["request_ref"], str(receipt_ref))
        self.assertEqual(payload["action"], "create")
        self.assertEqual(len(payload["records"]), 1)
        record = payload["records"][0]
        self.assertEqual(record["record_type"], "domain.object_version")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["content"]["storage"], "inline")
        value = record["content"]["value"]
        self.assertEqual(value["object_id"], str(root))
        for field in (
            "version",
            "content_schema_version",
            "content",
            "is_deleted",
            "change_note",
        ):
            self.assertEqual(value[field], row[field])
        actor = Ref.model_validate(value["created_by"])
        self.assertEqual(actor, Ref.model_validate(row["created_by"]))
        self.assertEqual(actor.id, str(creator.account.account_id))
        self.assertEqual(value["change_note"], body["change_note"])
        self.assertEqual(datetime.fromisoformat(value["created_at"]), row["created_at"])

    def test_unauthorized_cannot_read_roots_or_find_receipt(self) -> None:
        request_id = uuid4()
        body = _body(request_id, "仅管理员读取")
        with self.api() as client:
            self.assertEqual(client.get(_LIST).status_code, 401)
            self.assertEqual(
                client.post(_SAVE, headers={"Origin": _ORIGIN}, json=body).status_code, 401
            )
            admin = _login(client, "operator")
            wrong_csrf = client.post(
                _SAVE,
                headers={"Origin": _ORIGIN, **session_headers(admin), "X-CSRF-Token": "wrong"},
                json=body,
            )
            self.assertEqual(wrong_csrf.status_code, 403)
            self.assertEqual(self.persisted_counts(), (0,) * 6)
            saved = _save(client, admin, body).raise_for_status().json()
            root = saved["result"]["object_ref"]["object_id"]
            admin_id = admin.account.account_id
            detail_path = f"{_LIST}/{root}/objects/{root}"
            self.assertEqual(client.get(_LIST).status_code, 403)
            self.assertEqual(client.get(detail_path).status_code, 403)
            client.cookies.clear()
            self.assertEqual(client.get(detail_path).status_code, 401)
            self.assertEqual(_receipt(client, admin, request_id, admin_id).status_code, 401)

            student = _login(client, "student")
            headers = session_headers(student)
            self.assertEqual(client.get(_LIST, headers=headers).status_code, 403)
            self.assertEqual(client.get(detail_path, headers=headers).status_code, 403)
            denied = _save(client, student, _body(uuid4(), "无权限提交"))
            self.assertEqual(denied.status_code, 403)
            protected = _receipt(client, student, request_id, admin_id)
            missing = _receipt(client, student, uuid4(), admin_id)
            self.assertEqual(protected.status_code, 404)
            self.assertEqual(protected.json(), missing.json())
            self.assertEqual(self.persisted_counts(), (1,) * 6)

    def test_large_domain_record_round_trips_through_event_attachment(self) -> None:
        request_id = uuid4()
        name = "甲" * 12_000
        body = _body(request_id, name)
        with self.api() as client:
            admin = _login(client, "operator")
            first = _save(client, admin, body).raise_for_status().json()
            root = first["result"]["object_ref"]["object_id"]
            path = f"{_LIST}/{root}/objects/{root}"
            detail = client.get(path, headers=session_headers(admin)).raise_for_status().json()
            event_id = UUID(detail["object"]["source_event_id"])
            self.assertEqual(detail["object"]["content"]["name"], name)
            self.assertEqual(_save(client, admin, body).raise_for_status().json(), first)
            receipt = _receipt(client, admin, request_id, admin.account.account_id)
            self.assertEqual(receipt.raise_for_status().json()["result"], first["result"])
            with self.engine.connect() as connection:
                attached = connection.scalar(
                    text(
                        "SELECT payload->'records'->0->'content' FROM runtime.events"
                        " WHERE event_id=:id"
                    ),
                    {"id": event_id},
                )
                self.assertEqual(attached["storage"], "file")
                sha = connection.scalar(
                    text(
                        "SELECT sha256 FROM runtime.file_objects"
                        " WHERE file_id=:id AND category='fact'"
                    ),
                    {"id": UUID(attached["file_id"])},
                )
                self.assertEqual(sha, attached["sha256"])
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM runtime.file_objects")), 1
                )
            self.assertEqual(self.persisted_counts(), (1,) * 6)

    def test_event_projection_and_receipt_roll_back_together(self) -> None:
        request_id = uuid4()
        submitted = _body(request_id, "事务失败后可重试")
        staged_events: list[UUID] = []

        async def fail_after_append(connection: AsyncConnection, event: StoredEvent) -> None:
            event_id = event.draft.event_id
            persisted_in_transaction = await connection.scalar(
                text("SELECT event_id FROM runtime.events WHERE event_id=:id"), {"id": event_id}
            )
            self.assertEqual(persisted_in_transaction, event_id)
            staged_events.append(event_id)
            raise RuntimeError("injected projection failure")

        with self.api() as client:
            admin = _login(client, "operator")
            with patch("deermind.spaces.domain.definitions.apply_domain_event", fail_after_append):
                failure = _save(client, admin, submitted)
            self.assertEqual(failure.status_code, 500)
            self.assertEqual(failure.json()["error"]["code"], "internal_error")
            self.assertNotIn("injected projection failure", failure.text)
            self.assertEqual(len(staged_events), 1)
            self.assertEqual(self.persisted_counts(), (0,) * 6)
            recovered = _receipt(client, admin, request_id, admin.account.account_id)
            self.assertEqual(recovered.raise_for_status().json()["receipt_state"], "not_found")
            saved = _save(client, admin, submitted).raise_for_status().json()
            root = saved["result"]["object_ref"]["object_id"]
            detail = client.get(f"{_LIST}/{root}/objects/{root}", headers=session_headers(admin))
            self.assertNotEqual(
                detail.raise_for_status().json()["object"]["source_event_id"], str(staged_events[0])
            )
            self.assertEqual(self.persisted_counts(), (1,) * 6)


class DomainMigrationTests(DatabaseTestCase):
    def test_upgrade_0011_preserves_existing_history_and_accounts(self) -> None:
        config = migration_config()
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0011_ai_calls")
        asyncio.run(seed(self))
        facts = text("SELECT event_id,event_type,payload FROM runtime.events ORDER BY event_id")
        accounts = text(
            "SELECT account_id,login_identifier,role FROM product.accounts ORDER BY account_id"
        )
        with self.engine.connect() as connection:
            self.assertIsNone(
                connection.scalar(text("SELECT to_regclass('domain.object_identity')"))
            )
            old_events = connection.execute(facts).all()
            old_accounts = connection.execute(accounts).all()
        self.assertTrue(old_events)
        self.assertEqual(len(old_accounts), 2)

        self.assertEqual(upgrade(self.migrator), "0011_ai_calls")
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.scalar(text("SELECT version_num FROM public.alembic_version")),
                "0015_kc_test_paths",
            )
            self.assertEqual(connection.execute(facts).all(), old_events)
            self.assertEqual(connection.execute(accounts).all(), old_accounts)
            count = connection.scalar(text("SELECT count(*) FROM domain.object_identity"))
            self.assertEqual(count, 0)
