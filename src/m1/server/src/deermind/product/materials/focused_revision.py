"""按上一批的章节和父题身份拼回单项修订；未选中的待审内容照原文保留。"""

from deermind.product.materials.assistant_facts import CandidateFact
from deermind.product.materials.proposals import (
    MaterialProposal,
    OriginalCoverage,
    ProposedChapter,
    ProposedContent,
)
from deermind.spaces.domain.public import SourceRef
from sqlalchemy.engine import RowMapping


def revise_item(
    proposal: MaterialProposal,
    shown: list[SourceRef],
    snapshot: RowMapping,
    previous_rows: dict[str, CandidateFact],
    focus: str,
    amendment: ProposedContent,
) -> tuple[MaterialProposal, list[SourceRef]]:
    old = previous_rows[focus]
    pending = snapshot["decision_state"] == "pending"
    selected_rows = previous_rows.values() if pending else [old]
    sections = snapshot["diff_summary"]["chapters"]
    names = {s["chapter_id"]: s["local_key"] for s in sections}
    amendments: list[ProposedContent] = []
    for row in selected_rows:
        identity = str(row.candidate_id)
        body = amendment.model_dump() if identity == focus else row.body
        amendments.append(
            ProposedContent.model_validate(
                {
                    **body,
                    "action": "add",
                    "kind": row.kind,
                    "local_key": identity,
                    "chapter_key": names[row.chapter_ref.id],
                    "replaces": identity,
                    "parent_key": row.parent_ref.id if row.parent_ref else None,
                    "reason": amendment.reason if identity == focus else "沿用上一批原文",
                }
            )
        )
    needed = {item.chapter_key for item in amendments}
    proposal = proposal.model_copy(
        update={
            "changes": amendments,
            "catalog_changes": [
                ProposedChapter.model_validate(
                    {key: value for key, value in section.items() if key != "chapter_id"}
                )
                for section in sections
                if pending or section["local_key"] in needed
            ],
            "retire": [],
        }
    )
    if pending:
        prior_sources = [SourceRef.model_validate(s) for s in snapshot["read_set"]]
        known = {s.source_id for s in shown}
        shown = [*shown, *(s for s in prior_sources if s.source_id not in known)]
        proposal.coverage.extend(
            OriginalCoverage.model_validate(c)
            for c in snapshot["coverage"]["pages"]
            if c["source_id"] not in known
        )
    return proposal, shown
