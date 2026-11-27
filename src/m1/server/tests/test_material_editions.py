"""Whole-book tree validation, stable corrections and page navigation."""

import unittest
from uuid import uuid4

from deermind.product.materials.edition_proposals import OutlineBatch, OutlineItem, assemble
from deermind.product.public.material_editions import BookPage


class BookTreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.edition = uuid4()
        source = uuid4()
        self.pages = [
            BookPage(
                page_id=uuid4(),
                source_id=source,
                file_id=source,
                name="book.pdf",
                index=i,
                printed=None,
            )
            for i in (1, 2)
        ]
        self.items = [
            OutlineItem(key="section", parent="book", kind="section", text="", pages=[1], order=1),
            OutlineItem(
                key="q", parent="section", kind="exercise", text="行驶多远？", pages=[1], order=1
            ),
            OutlineItem(
                key="method", parent="q", kind="solution", text="速度乘时间", pages=[2], order=1
            ),
        ]

    def test_cross_page_parent_and_single_page_solution(self) -> None:
        nodes, pages = assemble(
            self.edition, self.pages, [OutlineBatch(nodes=self.items, printed_pages={"2": "50"})]
        )
        question = next(n for n in nodes if n.node_kind == "exercise")
        solution = next(n for n in nodes if n.node_kind == "solution")
        self.assertEqual(question.covered_page_ids, [p.page_id for p in pages])
        self.assertEqual(solution.parent_id, question.node_id)
        self.assertEqual(solution.covered_page_ids, [pages[1].page_id])
        self.assertEqual(pages[1].printed, "50")
        self.assertIsNone(pages[0].printed)

    def test_correction_preserves_identity_and_other_content(self) -> None:
        nodes, pages = assemble(self.edition, self.pages, [OutlineBatch(nodes=self.items)])
        old = next(n for n in nodes if n.node_kind == "solution")
        changed = self.items[-1].model_copy(
            update={
                "key": str(old.node_id),
                "parent": str(old.parent_id),
                "text": "路程等于速度乘时间",
            }
        )
        new, _ = assemble(self.edition, pages, [OutlineBatch(nodes=[changed])], nodes)
        self.assertEqual({n.node_id for n in new}, {n.node_id for n in nodes})
        self.assertEqual(
            next(n for n in new if n.node_id == old.node_id).content, {"text": changed.text}
        )
        self.assertNotEqual(old.content, {"text": changed.text})

    def test_invalid_page_parent_cycle_and_incomplete_coverage_fail(self) -> None:
        for replacement in (
            {"pages": [3]},
            {"parent": "missing"},
            {"parent": "method"},
            {"pages": [1]},
        ):
            with self.subTest(change=replacement), self.assertRaises(ValueError):
                assemble(
                    self.edition,
                    self.pages,
                    [
                        OutlineBatch(
                            nodes=[*self.items[:-1], self.items[-1].model_copy(update=replacement)]
                        )
                    ],
                )
