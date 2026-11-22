"""用发布包验证四例正文在随机测试库及独立目录中的保存与回读。"""

import asyncio
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

from deermind.abstractions.events import Ref
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from deermind.spaces.domain.public import RichContent
from pydantic import ValidationError
from rich_content_cases import Draft, case_documents, read_cases
from test_database import DatabaseTestCase

_MAX_BYTES = 1024 * 1024


class RichContentStorageTests(DatabaseTestCase):
    """验证原用途与关键数据和文件身份经真实持久化后仍完整。"""

    def test_four_cases_save_and_reload(self) -> None:
        """在本轮挂载下使用隔离子目录，导出经过实际回读的正文供浏览器消费。"""
        upgrade(self.migrator)
        mount = os.environ.get("M1_TEST_FILES_ROOT")
        if mount:
            self.assertTrue(Path(mount).is_mount())
        with tempfile.TemporaryDirectory(prefix="rich-content-test-", dir=mount) as directory:
            restored = asyncio.run(self.save_and_reload(Path(directory)))
        self.assert_case_semantics(restored)
        if output := os.environ.get("M1_TEST_CONTENT_OUTPUT"):
            Path(output).write_text(json.dumps(restored, ensure_ascii=False), encoding="utf-8")

    async def save_and_reload(self, root: Path) -> dict[str, Draft]:
        """用真实附件入口和数据库，不在正式领域下保存任何教材。"""
        engine = application_engine(self.app)
        actor = Ref(owner="runtime", type="service", id="rich-content-fixture")
        # 各测试只管理自己的子目录，PVC类型和完整性另由部署后的写读验证。
        attachments = FactAttachments(engine, LocalFiles(root, backend="local"))
        restored: dict[str, Draft] = {}
        try:
            for case in read_cases():
                case_id = case["case_id"]
                documents: list[Draft] = []
                for document in case_documents(case):
                    draft = RichContent.model_validate(document["content"])
                    value = draft.model_dump(mode="json")
                    source = Ref(owner="domain", type="fixture", id=str(uuid4()))
                    reference = await attachments.save_json(
                        value,
                        actor=actor,
                        source=source,
                        artifact_key=f"rich-test:{case_id}:{document['id']}",
                        max_bytes=_MAX_BYTES,
                    )
                    # 重新建读取器，并从数据库登记及实际文件取回完整正文。
                    reader = FactAttachments(engine, LocalFiles(root, backend="local"))
                    readback = await reader.read_json(
                        reference, source=source, max_bytes=_MAX_BYTES
                    )
                    self.assertEqual(readback, value)
                    self.assertEqual(RichContent.model_validate(readback), draft)
                    documents.append({**document, "content": readback})
                    if case_id == "C06":
                        await self.assert_failed_attachments(reader, reference, source, root)
                restored[case_id] = {"documents": documents, "notes": case["notes"]}
        finally:
            await engine.dispose()
        return restored

    async def assert_failed_attachments(
        self, reader: FactAttachments, reference: Ref, source: Ref, root: Path
    ) -> None:
        """同一文件在错属主、破坏哈希和缺失字节时均不可读取。"""
        wrong_source = source.model_copy(update={"id": str(uuid4())})
        with self.assertRaises(PermissionError):
            await reader.read_json(reference, source=wrong_source, max_bytes=_MAX_BYTES)
        file = await reader.registry.by_id(UUID(reference.id))
        assert file is not None
        self.assertEqual(file.source_refs, [source])
        self.assertEqual(file.storage_key, f"{file.file_id.hex}.blob")
        owned_path = root / file.storage_key
        owned_path.chmod(0o600)
        content = owned_path.read_bytes()
        owned_path.write_bytes(b"!" + content[1:])
        with self.assertRaisesRegex(OSError, "integrity"):
            await reader.read_json(reference, source=source, max_bytes=_MAX_BYTES)
        owned_path.unlink()
        with self.assertRaises(FileNotFoundError):
            await reader.read_json(reference, source=source, max_bytes=_MAX_BYTES)

    def assert_case_semantics(self, restored: dict[str, Draft]) -> None:
        """用用户确认的四例要点核对回读，而非只校验往返相同。"""
        double_solution = restored["C02"]["documents"]
        self.assertEqual(
            [document["content"]["role"] for document in double_solution],
            ["statement", "reference", "reference", "teaching_aid"],
        )
        original_pages = double_solution[0]["content"]["source_refs"]
        self.assertEqual([source["printed_page"] for source in original_pages], ["49", "50"])
        self.assertTrue(all(source["region"] for source in original_pages))

        error_work = restored["C03"]["documents"][0]["content"]["blocks"][1]["payload"]
        self.assertEqual(error_work["purpose"], "given_work")
        self.assertEqual(error_work["lines"][0]["expression"]["op"], "divide")
        self.assertEqual(error_work["lines"][1]["expression"]["op"], "multiply")

        census = restored["C05"]["documents"]
        statement, _, derived = (document["content"] for document in census)
        self.assertEqual(derived["role"], "derived_view")
        self.assertEqual(statement["data_tables"], derived["data_tables"])
        census_table = statement["data_tables"][0]
        self.assertEqual(census_table["rows"][0]["cells"]["age60"]["value"], "1.30")
        self.assertEqual(
            [block["payload"]["kind"] for block in statement["blocks"] if block["type"] == "chart"],
            ["bar", "line", "pie"],
        )
        cropped = deepcopy(statement)
        cropped["blocks"][1]["payload"]["axis"]["max"] = "1"
        with self.assertRaises(ValidationError) as error:
            RichContent.model_validate(cropped)
        self.assertEqual(error.exception.errors()[0]["loc"][0], "blocks")

        diagram = restored["C06"]["documents"][0]["content"]["blocks"][1]["payload"]
        self.assertEqual(len(diagram["layout"]["boxes"]), 6)
        self.assertEqual(len(diagram["layout"]["points"]), 6)
        self.assertEqual(
            {(relation["predicate"], relation["basis"]) for relation in diagram["relations"]},
            {("inside", "visual_observation")},
        )
