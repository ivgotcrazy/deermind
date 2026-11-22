"""教材候选只能引用本轮发送的页，文件身份由程序绑定。"""

import unittest
from uuid import uuid4

from deermind.product.materials.proposals import MaterialProposal
from deermind.spaces.domain.public import SourceRef


class MaterialProposalTests(unittest.TestCase):
    def test_bind_uses_registered_file_and_keeps_observed_printed_page(self) -> None:
        shown = SourceRef.model_validate(
            {
                "source_id": "given-page",
                "owner": "product",
                "ref": {"type": "file", "file_id": uuid4(), "sha256": "f" * 64},
                "file_page": 1,
            }
        )
        raw_source = shown.model_dump(mode="json")
        raw_source.update(
            {
                "file_page": 93,
                "printed_page": "93",
                "ref": {"type": "file", "file_id": str(uuid4()), "sha256": "0" * 64},
            }
        )
        proposal = MaterialProposal.model_validate(
            {
                "outcome": "proposal",
                "reply": "待核对",
                "catalog_changes": [
                    {
                        "action": "add",
                        "local_key": "c",
                        "name": "统计",
                        "order": 1,
                        "source_ids": ["given-page"],
                        "reason": "可见",
                    }
                ],
                "coverage": [{"source_id": "given-page", "status": "processed", "reason": "可见"}],
                "issues": [],
                "questions": [],
                "changes": [
                    {
                        "action": "add",
                        "local_key": "t",
                        "chapter_key": "c",
                        "kind": "task_instance",
                        "title": "看图",
                        "reason": "原题",
                        "parent_key": None,
                        "content": {
                            "schema_version": "1",
                            "role": "statement",
                            "data_tables": [],
                            "source_refs": [raw_source],
                            "blocks": [
                                {
                                    "block_id": "p",
                                    "type": "paragraph",
                                    "payload": {"spans": [{"type": "text", "text": "看图"}]},
                                    "provenance": {
                                        "source_refs": ["given-page"],
                                        "transformation": "extracted",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        )
        source = proposal.bind_sources([shown]).changes[0].content.source_refs[0]
        self.assertEqual(source.ref, shown.ref)
        self.assertEqual(source.file_page, 1)
        self.assertEqual(source.printed_page, "93")

        with self.assertRaisesRegex(ValueError, "覆盖清单"):
            proposal.bind_sources([shown.model_copy(update={"source_id": "other"})])
