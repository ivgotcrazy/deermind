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
from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import Ref, StoredEvent
from deermind.abstractions.material_intake import CandidateRef, IntakeSource
from deermind.bootstrap.courses import configure_goals
from deermind.entrypoints.api.app import create_app
from deermind.entrypoints.maintenance.database import migration_config, upgrade
from deermind.foundation.system.public.errors import ErrorDetail
from deermind.infrastructure.database.connection import EXPECTED_REVISION
from deermind.product.public.authentication import SessionView
from deermind.product.public.learning_targets import TargetView
from deermind.spaces.domain.intake_processing import IntakeProcessing
from deermind.spaces.evaluation.public import STANDARD_ASPECTS
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
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

    def test_material_adoption_checks_only_related_pages(self) -> None:
        """同一内容基线上的候选可并存，相关变化阻止整批采用。"""
        textbook, imported, source = uuid4(), uuid4(), uuid4()
        chapters = [uuid4(), uuid4()]
        pages = [uuid4(), uuid4()]
        batches = [uuid4() for _ in range(3)]
        candidates = [uuid4() for _ in batches]
        with self.api() as client:
            admin = _login(client, "operator")
            root = _save(client, admin, _body(uuid4(), "两章候选采用范围"))
            domain = root.raise_for_status().json()["result"]["object_ref"]["object_id"]
                }
                if check_goal
                else {}
            )
            # 预置同一基线的候选。采用请求仍经过真实 HTTP、收据和事件事务。
            with self.engine.begin() as db:
                keys = {"book": textbook, "import": imported, "domain": domain, "fact": source}
                db.execute(
                    text(
                        "INSERT INTO product.material_import "
                        "(import_id,textbook_id,status,revision,source_revision,content_revision,"
                        "created_at,updated_at,source_event_id) "
                        "VALUES (:import,:book,'active',1,1,0,now(),now(),:fact)"
                    ),
                    keys,
                )
                db.execute(
                    text(
                        "INSERT INTO product.textbook "
                        "(textbook_id,domain_id,import_id,metadata,metadata_revision,"
                        "created_at,source_event_id) "
                        "VALUES (:book,:domain,:import,'{}',1,now(),:fact)"
                    ),
                    keys,
                )
                for batch, candidate, section in zip(batches, candidates, (0, 1, 0), strict=True):
                    turn = uuid4()
                    chapter, page = chapters[section], pages[section]
                    db.execute(
                        text(
                            "INSERT INTO product.material_turn "
                            "(request_ref,import_id,input_digest,input,state,created_at,"
                            "updated_at,source_event_id) "
                            "VALUES (:turn,:import,repeat('0',64),'{}','completed',now(),now(),"
                            ":fact)"
                        ),
                        {**keys, "turn": turn},
                    )
                    db.execute(
                        text(
                            "INSERT INTO product.material_candidate_batch "
                            "VALUES (:batch,1,:turn,CAST(:scope AS jsonb),CAST(:pages AS jsonb),"
                            "CAST(:writes AS jsonb),jsonb_build_object('complete',true),"
                            "CAST(:diff AS jsonb),"
                            "'pending',1,now(),:fact)"
                        ),
                        {
                            **keys,
                            "batch": batch,
                            "turn": turn,
                            "scope": canonical_json(
                                {"import_id": str(imported), "basis_revision": 0}
                            ),
                            "pages": canonical_json([{"source_id": str(page)}]),
                            "writes": canonical_json(
                                [{"candidate_id": str(candidate), "action": "add"}]
                            ),
                            "diff": canonical_json(
                                {
                                    "chapters": [
                                        {
                                            "chapter_id": str(chapter),
                                            "name": f"第{section + 1}章",
                                            "order": section + 1,
                                            "source_ids": [str(page)],
                                        }
                                    ]
                                }
                            ),
                        },
                    )
                    db.execute(
                        text(
                            "INSERT INTO product.material_candidate "
                            "(candidate_id,candidate_revision,batch_id,import_id,local_key,kind,"
                            "chapter_ref,body,basis_revision,created_at,source_event_id) "
                            "VALUES (:candidate,1,:batch,:import,'t1','task_instance',"
                            "CAST(:chapter AS jsonb),'{}',0,now(),:fact)"
                        ),
                        {
                            **keys,
                            "batch": batch,
                            "candidate": candidate,
                            "chapter": canonical_json({"id": str(chapter)}),
                        },
                    )

            headers = {"Origin": _ORIGIN, **session_headers(admin)}
            for batch in batches[:2]:
                adopted = client.post(
                    f"/api/m1/material-imports/{imported}/candidate-batches/{batch}/decision",
                    headers=headers,
                    json={
                        "request_id": str(uuid4()),
                        "decision": "adopt",
                        "batch_ref": {"batch_id": str(batch), "batch_revision": 1},
                        "expected_revision": 1,
                    },
                )
                self.assertEqual(adopted.status_code, 200, adopted.text)
            batch = batches[2]
            endpoint = f"/api/m1/material-imports/{imported}/candidate-batches/{batch}/decision"
            decision = {
                "request_id": str(uuid4()),
                "decision": "adopt",
                "batch_ref": {"batch_id": str(batch), "batch_revision": 1},
                "expected_revision": 1,
            }
            stale = client.post(endpoint, headers=headers, json=decision)
            self.assertEqual(stale.status_code, 409, stale.text)
            self.assertEqual(stale.json()["error"]["code"], "candidate_basis_changed")
            declined = client.post(
                endpoint, headers=headers, json={**decision, "decision": "decline"}
            )
            self.assertEqual(declined.status_code, 200, declined.text)
            self.assertEqual(declined.json()["result"]["content_revision"], 2)
            with self.engine.connect() as db:
                current = db.scalars(
                    text("SELECT candidate_id FROM product.material_content_current")
                )
                self.assertEqual(set(current), set(candidates[:2]))

    def test_same_task_can_use_different_methods_in_two_chapters(self) -> None:
        """同一 Task 的采用按章节生效，取消一章不会改变另一章。"""
        self._two_chapter_flow(check_goal=False)

    def test_goal_reassessment_keeps_late_results_historical(self) -> None:
        self._two_chapter_flow(check_goal=True)

    def _two_chapter_flow(self, *, check_goal: bool) -> None:
        textbook, imported, source = uuid4(), uuid4(), uuid4()
        first, second = uuid4(), uuid4()
        with self.api() as client:
            admin = _login(client, "operator")
            root = _save(client, admin, _body(uuid4(), "两章的同一任务"))
            domain = root.raise_for_status().json()["result"]["object_ref"]["object_id"]
            method_fields = (
                {
                    key: _content("按已知原量与增加比例列式并核对结果。")
                    for key in ("approach", "rationale", "applicability", "key_process")
                }
                if check_goal
                else {}
            )
            task_fields = (
                {
                    key: _content("已知原量与增加比例，给出新量及列式。")
                    for key in (
                        "responsibility", "expected_output", "completion_conditions",
                        "applicability", "boundaries",
                    )
            methods = [
                _save(
                    client,
                    admin,
                    {
                        "request_id": str(uuid4()),
                        "action": "create",
                        "object_kind": "solution",
                        "domain_id": domain,
                        "definition": {"name": name, **method_fields},
                        "change_note": "两章可采用不同方法",
                    },
                )
                .raise_for_status()
                .json()["result"]["object_ref"]
                for name in ("逐步计算", "合并比例")
            ]
            task = (
                _save(
                    client,
                    admin,
                    {
                        "request_id": str(uuid4()),
                        "action": "create",
                        "object_kind": "task",
                        "domain_id": domain,
                        "definition": {"name": "求部分量", "method_refs": methods, **task_fields},
                        "change_note": "章节采用的固定任务",
                    },
                )
                .raise_for_status()
                .json()["result"]["object_ref"]
            )
            # 两章是隔离库的已采用材料夹具，关联写入通过真实 HTTP 和事实事务。
            with self.engine.begin() as db:
                values = {"book": textbook, "import": imported, "domain": domain, "fact": source}
                db.execute(
                    text(
                        "INSERT INTO product.material_import "
                        "(import_id,textbook_id,status,revision,source_revision,content_revision,"
                        "created_at,updated_at,source_event_id) "
                        "VALUES (:import,:book,'active',1,1,1,now(),now(),:fact)"
                    ),
                    values,
                )
                db.execute(
                    text(
                        "INSERT INTO product.textbook "
                        "(textbook_id,domain_id,import_id,metadata,metadata_revision,"
                        "created_at,source_event_id) "
                        "VALUES (:book,:domain,:import,"
                        "jsonb_build_object('title','M1 test'),1,now(),:fact)"
                    ),
                    values,
                )
                for order, chapter in enumerate((first, second), 1):
                    db.execute(
                        text(
                            "INSERT INTO product.material_chapter "
                            "(chapter_id,textbook_id,title,sort_order,revision,catalog_basis_ref,"
                            "updated_at,source_event_id) "
                            "VALUES (:chapter,:book,:title,:position,1,'{}',now(),:fact)"
                        ),
                        {**values, "chapter": chapter, "title": f"第{order}章", "position": order},
                    )

            headers = {"Origin": _ORIGIN, **session_headers(admin)}
            paths = [
                f"/api/m1/textbooks/{textbook}/chapters/{chapter}/associations"
                for chapter in (first, second)
            ]
            relations: list[Ref] = []
            for path, method in zip(paths, methods, strict=True):
                saved = (
                    client.post(
                        path,
                        headers=headers,
                        json={
                            "request_id": str(uuid4()),
                            "action": "add",
                            "task_ref": task,
                            "method_refs": [method],
                        },
                    )
                    .raise_for_status()
                    .json()["result"]
                )
                relations.append(Ref.model_validate(saved["association_ref"]))
                self.assertEqual(saved["method_refs"], [method])
            claim = (
                client.post(
                    "/api/m1/evaluation/claim-commands",
                    headers=headers,
                    json={
                        "request_id": str(uuid4()),
                        "action": "create_claim",
                        "domain_id": str(domain),
                        "task_ref": task,
                        "title": "两章各用一种方法",
                        "description": "分别核对每种方法。",
                        "aspects": [
                            {"code": code, "label": label, "description": label}
                            for code, label in STANDARD_ASPECTS.items()
                        ],
                    },
                )
                .raise_for_status()
                .json()["result"]["claim_ref"]
            )
            no_parameters: dict[str, object] = {}
            no_conditions: dict[str, object] = {}
            target = (
                client.post(
                    "/api/m1/learning-targets",
                    headers=headers,
                    json={
                        "request_id": str(uuid4()),
                        "action": "create",
                        "textbook_id": str(textbook),
                        "title": "两章目标",
                        "items": [
                            {
                                "title": "分别核对",
                                "claim_ref": claim,
                                "chapter_refs": [str(first), str(second)],
                                "task_conditions": {
                                    "description": "原量增加四分之一",
                                    "parameter_values": no_parameters,
                                },
                                "method_mode": "each",
                                "methods": [
                                    {
                                        "method_ref": method,
                                        "chapter_refs": [str(chapter)],
                                        "aspects": [
                                            {
                                                "aspect_ref": {
                                                    "claim_ref": claim,
                                                    "aspect_code": "independent",
                                                },
                                                "condition_values": no_conditions,
                                            }
                                        ],
                                    }
                                    for method, chapter in zip(
                                        methods, (first, second), strict=True
                                    )
                                ],
                            }
                        ],
                    },
                )
                .raise_for_status()
                .json()["result"]["target"]
            )
            self.assertEqual(
                [method["chapter_refs"] for method in target["items"][0]["methods"]],
                [[str(first)], [str(second)]],
            )
            self.assertEqual(
                target["chapter_basis_refs"],
                [ref.model_dump(mode="json") for ref in relations],
            )
            if check_goal:
                self._verify_delayed_goal(
                    client, TargetView.model_validate_json(canonical_json(target)), (first, second)
                )
                headers = {"Origin": _ORIGIN, **session_headers(_login(client, "operator"))}
                deletion = client.post(
                    f"/api/m1/material-imports/{imported}/delete",
                    headers=headers,
                    json={
                        "request_id": str(uuid4()),
                        "expected_revision": 1,
                        "confirmed_scope_ref": {
                            "owner": "product",
                            "type": "deletion_scope",
                            "id": str(imported),
                            "revision": 1,
                        },
                    },
                )
                self.assertEqual(deletion.status_code, 409)
                self.assertEqual(deletion.json()["error"]["code"], "already_applied")
                return
            removed = client.post(
                paths[0],
                headers=headers,
                json={
                    "request_id": str(uuid4()),
                    "action": "remove",
                    "task_ref": task,
                    "association_id": relations[0].id,
                    "expected_revision": relations[0].revision,
                },
            )
            self.assertEqual(removed.status_code, 200, removed.text)
            self.assertEqual(client.get(paths[0], headers=headers).json()["items"], [])
            remaining = client.get(paths[1], headers=headers).raise_for_status().json()["items"]
            self.assertEqual(remaining[0]["association_ref"], relations[1].model_dump(mode="json"))
            self.assertEqual(remaining[0]["method_refs"], [methods[1]])

            # 保存端已经持有教材行锁时，删除须等待这次短事务结束。
            endpoint = f"/api/m1/material-imports/{imported}/delete"
            confirmed = {
                "owner": "product",
                "type": "deletion_scope",
                "id": str(imported),
                "revision": 1,
            }
            with ThreadPoolExecutor(1) as worker:
                with self.engine.begin() as db:
                    lock = db.scalar(
                        text(
                            "SELECT import_id FROM product.material_import "
                            "WHERE import_id=:id FOR UPDATE"
                        ),
                        {"id": imported},
                    )
                    self.assertEqual(lock, imported)
                    deleting = worker.submit(
                        client.post,
                        endpoint,
                        headers=headers,
                        json={
                            "request_id": str(uuid4()),
                            "expected_revision": 1,
                            "confirmed_scope_ref": confirmed,
                        },
                    )
                    with self.assertRaises(TimeoutError):
                        deleting.result(timeout=0.2)
                self.assertEqual(deleting.result(timeout=5).status_code, 200)

            stale = client.post(
                paths[1],
                headers=headers,
                json={
                    "request_id": str(uuid4()),
                    "action": "update",
                    "task_ref": task,
                    "association_id": relations[1].id,
                    "expected_revision": 1,
                    "method_refs": [methods[0]],
                },
            )
            self.assertEqual(stale.status_code, 404, stale.text)
            domain_definition = client.get(
                f"{_LIST}/{domain}/objects/{task['object_id']}?version=1", headers=headers
            )
            self.assertEqual(domain_definition.status_code, 200, domain_definition.text)
            self.assert_material_source_invalidated(client, imported, domain)

    def assert_material_source_invalidated(
        self, client: TestClient, imported: UUID, domain_id: str
    ) -> None:
        """固定三个隔离待办，使用真实删除事件检验领域投影及重新接收。"""
        input_id = uuid4()
        pending, completed, other = uuid4(), uuid4(), uuid4()
        with self.engine.begin() as db:
            payload = db.scalar(
                text(
                    "SELECT payload FROM runtime.handoffs WHERE kind='publish' "
                    "AND payload->>'event_type'='MaterialImportDeleted' "
                    "AND payload->>'scope_id'=:id"
                ),
                {"id": str(imported)},
            )
            notice = EventNotice.model_validate_json(canonical_json(payload))
            db.execute(
                text(
                    "INSERT INTO domain.artifact "
                    "(artifact_id,domain_id,kind,payload,created_at,source_event_id) "
                    "VALUES (:input,:domain,'input','{}',now(),:event)"
                ),
                {"input": input_id, "domain": domain_id, "event": notice.event_id},
            )
            for item, origin, state in (
                (pending, imported, "pending"),
                (completed, imported, "completed"),
                (other, uuid4(), "pending"),
            ):
                candidate = uuid4()
                source = IntakeSource(
                    candidate_ref=CandidateRef(
                        candidate_id=candidate, candidate_revision=1, basis_revision=1
                    ),
                    candidate_fact=EventPartRef(
                        event_id=notice.event_id, record_id=str(candidate), path=""
                    ),
                    adoption_ref=Ref(owner="product", type="material_adoption", id=str(uuid4())),
                )
                db.execute(
                    text(
                        "INSERT INTO domain.intake_item(item_id,domain_id,candidate_key,source_ref,"
                        "input_artifact_id,kind,title,group_id,state,revision,created_at,"
                        "source_event_id) "
                        "VALUES (:id,:domain,:key,CAST(:source AS jsonb),:input,'kc','验证来源',"
                        ":id,:state,1,now(),:event)"
                    ),
                    {
                        "id": item,
                        "domain": domain_id,
                        "key": f"{origin}:{candidate}:1:1",
                        "source": source.model_dump_json(),
                        "input": input_id,
                        "state": state,
                        "event": notice.event_id,
                    },
                )

        app = client.app
        portal = client.portal
        assert isinstance(app, FastAPI) and portal is not None
        engine: AsyncEngine = app.state.database
        processing: IntakeProcessing = app.state.domain_intake_processing

        async def deliver() -> Acceptance:
            async with engine.begin() as connection:
                return await processing.invalidate_source(connection, notice)

        result = portal.call(deliver)
        self.assertEqual(result.disposition, "accepted")
        self.assertEqual([item.id for item in result.arrangement_refs], [str(pending)])
        self.assertEqual(portal.call(deliver).disposition, "ignored")

        with self.engine.connect() as db:
            rows = db.execute(
                text("SELECT item_id,state,revision FROM domain.intake_item WHERE domain_id=:id"),
                {"id": domain_id},
            )
            self.assertEqual(
                {row.item_id: (row.state, row.revision) for row in rows},
                {
                    pending: ("removed", 2),
                    completed: ("completed", 1),
                    other: ("pending", 1),
                },
            )

    def _verify_delayed_goal(
        self, client: TestClient, target: TargetView, chapters: tuple[UUID, UUID]
    ) -> None:
        def send(
            route: str, body: object, session: SessionView, method: str = "POST",
        ) -> dict[str, JsonValue]:
            value = client.request(
                method, "/api/m1" + route,
                headers={"Origin": _ORIGIN, **session_headers(session)},
                json=body,
            )
            return value.raise_for_status().json()

        operator = _login(client, "operator")
        config_route = "/interaction/activity-configs/detection"

        def configure(kind: str, definition: dict[str, JsonValue], revision: int | None,
                      reference: JsonValue = None) -> dict[str, JsonValue]:
            result = send(config_route, {
                "request_id": str(uuid4()), "config_kind": kind, "expected_revision": revision,
                "config_ref": reference, "definition": {"activity_type": "detection", **definition},
            }, operator, "PUT")["result"]
            assert isinstance(result, dict)
            return result

        blueprint = configure("blueprint", {
            "nodes": [
                {
                    "node_id": node, "name": node, "purpose": "固定检测",
                    "required_inputs": [], "outputs": [], "allowed_actions": [],
                    "execution_guidance": "按当前信息处理",
                    "fallback": {"action": "wait_input", "explanation": "等待确认"},
                }
                for node in ("start", "end")
            ],
            "transitions": [{
                "transition_id": "end-step", "source_node_id": "start", "target_node_id": "end",
                "order": 1, "when": "on_control", "condition_text": "已确认",
                "required_facts": [{"code": "plan_confirmed", "value": True}], "evidence_required": False,
            }],
        }, None)
        rule = configure("rule", {
            "name": "独立检测", "applies_when": "检测期间", "requirement": "关闭本轮后才能提供帮助。",
            "basis": "检测规则", "limitations": [], "enabled": True,
        }, 1)["definition_ref"]
        binding = blueprint["affected_refs"]
        assert isinstance(rule, dict) and isinstance(binding, list)
        detection = configure("binding", {
            "activity": {"rule_ids": [rule["id"]], "strategy_ids": []}, "nodes": {},
        }, 2, binding[0])["config_ref"]

        def adopt(target_ref: dict[str, JsonValue], previous: JsonValue) -> dict[str, JsonValue]:
            operator = _login(client, "operator")
            chapter_data: list[dict[str, JsonValue]] = [
                {"chapter_id": str(chapter), "revision": 1, "content_refs": []}
                for chapter in chapters
            ]
            check = send(
                "/course-applications/checks",
                {
                    "request_id": str(uuid4()),
                    "textbook_id": str(target.textbook_id),
                    "target_ref": target_ref,
                    "expected_application_ref": previous,
                    "chapters": chapter_data,
                    "activity_config_refs": [detection],
                },
                operator,
            )
            result = check["result"]
            assert isinstance(result, dict)
            readiness = result["readiness"]
            assert isinstance(readiness, list)
            detection_rows = [
                row for row in readiness if isinstance(row, dict) and row["purpose"] == "detection"
            ]
            self.assertEqual(len(detection_rows), len(chapters))
            self.assertTrue(all(row["status"] == "ready" for row in detection_rows))
            applied = send(
                "/course-applications/confirmations",
                {
                    "request_id": str(uuid4()),
                    "check_ref": result["check_ref"],
                    "expected_application_ref": previous,
                },
                operator,
            )["result"]
            assert isinstance(applied, dict)
            return applied

        current = adopt(target.target_ref.model_dump(mode="json"), None)
        student = _login(client, "student")
        usage = (
            client.get("/api/m1/usage-conditions", headers=session_headers(student))
            .raise_for_status()
            .json()
        )
        send(
            "/usage-confirmations",
            {
                "request_id": str(uuid4()),
                "expected_revision": usage["revision"],
                "confirmation": {
                    "student_id": str(student.account.account_id),
                    "kind": "student_assent",
                    "notice_ref": usage["notice_ref"],
                    "source_ref": usage["source_ref"],
                    "decision": "accepted",
                },
            },
            student,
        )
        opened = send(
            "/learning-spaces/open",
            {
                "request_id": str(uuid4()),
                "action": "create",
                "textbook_id": str(target.textbook_id),
                "target_id": str(target.target_ref.target_id),
                "expected_application_ref": current["application_ref"],
            },
            student,
        )["result"]
        assert isinstance(opened, dict) and isinstance(opened["space"], dict)
        scope_id = opened["space"]["space_id"]
        assert isinstance(scope_id, str)
        operator = _login(client, "operator")
        revised = send(
            "/learning-targets",
            {
                "request_id": str(uuid4()),
                "action": "update",
                "textbook_id": str(target.textbook_id),
                "target_id": str(target.target_ref.target_id),
                "expected_revision": target.target_ref.revision,
                "title": target.title,
                "items": [
                    item.model_copy(update={"method_mode": "any_one"}).model_dump(mode="json")
                    for item in target.items
                ],
            },
            operator,
        )["result"]
        assert isinstance(revised, dict) and isinstance(revised["target"], dict)
        ref = revised["target"]["target_ref"]
        assert isinstance(ref, dict)
        adopt(ref, current["application_ref"])
        with self.engine.connect() as db:
            triggers = db.scalars(
                text(
                    "SELECT event_id FROM runtime.events WHERE scope_id=:scope "
                    "AND event_type='LearningTargetApplied' ORDER BY scope_event_seq"
                ),
                {"scope": UUID(scope_id)},
            ).all()
        older, newer = triggers

        async def deliver(trigger: UUID) -> Acceptance:
            assert isinstance(client.app, FastAPI)
            state = client.app.state
            handler = configure_goals(state.learning_targets, state.activity_configs)
            async with state.database.begin() as db:
                return await handler.receive(
                    db,
                    EventNotice(
                        delivery_id=uuid4(),
                        event_id=trigger,
                        event_type="LearningTargetApplied",
                        producer="product",
                        scope_kind="learning_space",
                        scope_id=UUID(scope_id),
                        schema_version=1,
                        handoff_id=uuid4(),
                    ),
                )

        assert client.portal is not None
        newest = client.portal.call(deliver, newer).arrangement_refs[0]
        oldest = client.portal.call(deliver, older).arrangement_refs[0]
        self.assertEqual(client.portal.call(deliver, older).arrangement_refs, [oldest])
        with self.engine.connect() as db:
            rows = db.execute(
                text(
                    "SELECT goal_evaluation_id,current_state_applied "
                    "FROM evaluation.goal_evaluation "
                    "WHERE scope_id=:scope"
                ),
                {"scope": UUID(scope_id)},
            ).all()
        self.assertEqual(
            dict((str(row[0]), row[1]) for row in rows), {newest.id: True, oldest.id: False}
        )

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
                EXPECTED_REVISION,
            )
            self.assertEqual(connection.execute(facts).all(), old_events)
            self.assertEqual(connection.execute(accounts).all(), old_accounts)
            count = connection.scalar(text("SELECT count(*) FROM domain.object_identity"))
            self.assertEqual(count, 0)
