"""学习目标的章节适用范围与评价方面条件校验。"""

from collections.abc import Callable, Mapping
from uuid import UUID, uuid4

from deermind.abstractions.events import Ref
from deermind.foundation.system.public.errors import Issue, RequestError
from deermind.product.public.chapter_associations import ChapterAssociationView
from deermind.product.public.learning_targets import (
    GoalItem,
    GoalItemDraft,
    MethodRequirement,
    TargetAspect,
)
from deermind.spaces.evaluation.public import STANDARD_ASPECTS, AspectRule, ClaimView
from pydantic import JsonValue

type ConditionResolver = Callable[[AspectRule, dict[str, JsonValue]], dict[str, JsonValue]]
type MethodIdentity = tuple[UUID, int]


def allowed_methods(
    item: GoalItemDraft,
    claim: ClaimView,
    chapters: Mapping[UUID, ChapterAssociationView],
) -> dict[MethodIdentity, list[UUID]]:
    """保留方法与具体章节的对应关系，章节间采用不同方法可同时进入目标。"""
    allowed: dict[MethodIdentity, list[UUID]] = {}
    if len(set(item.chapter_refs)) != len(item.chapter_refs):
        raise RequestError(400, "invalid_reference", "目标章节不能重复。")
    for chapter in item.chapter_refs:
        found = chapters.get(chapter)
        if found is None or not found.active or found.task_ref != claim.definition.task_ref:
            raise RequestError(
                409, "invalid_reference", "目标章节没有采用 Claim 对应的 Task 版本。"
            )
        for method in found.method_refs:
            allowed.setdefault((method.object_id, method.version), []).append(chapter)
    return allowed


def _method(
    method: MethodRequirement,
    claim: ClaimView,
    position: str,
    resolve: ConditionResolver,
) -> tuple[MethodRequirement, list[Issue]]:
    definition = next(
        (entry for entry in claim.definition.methods if entry.method_ref == method.method_ref), None
    )
    if definition is None:
        raise RequestError(409, "invalid_reference", "所选方法不属于该 Claim。")
    gaps: list[Issue] = []
    if not definition.criterion_ids:
        gaps.append(Issue(code="missing_criteria", path=position, message="尚无执行判据。"))
    aspects = {item.code for item in claim.definition.aspects}
    selected = set[str]()
    revised: list[TargetAspect] = []
    for index, aspect in enumerate(method.aspects):
        identity = aspect.aspect_ref
        code = identity.aspect_code
        if identity.claim_ref != claim.claim_ref or code not in aspects or code in selected:
            raise RequestError(409, "invalid_reference", "评价方面重复或不属于该 Claim 修订。")
        selected.add(code)
        rule = next((item for item in definition.aspect_rules if item.aspect_code == code), None)
        conditions = aspect.condition_values
        if rule is None:
            if conditions:
                raise RequestError(400, "invalid_condition", "没有方面规则时不能指定条件值。")
            gaps.append(
                Issue(
                    code="missing_aspect_rule",
                    path=f"{position}/aspects/{index}",
                    message="尚无本方面规则。",
                )
            )
        else:
            if code not in STANDARD_ASPECTS:
                gaps.append(
                    Issue(
                        code="unsupported_aspect",
                        path=f"{position}/aspects/{index}",
                        message="评价方面缺少确定性处理依据。",
                    )
                )
            try:
                conditions = resolve(rule, conditions)
            except ValueError as error:
                raise RequestError(400, "invalid_condition", str(error)) from error
        revised.append(aspect.model_copy(update={"condition_values": conditions}))
    return method.model_copy(update={"aspects": revised}), gaps


def prepare_item(
    item: GoalItemDraft,
    claim: ClaimView,
    chapters: Mapping[UUID, ChapterAssociationView],
    prior_item_ids: set[UUID],
    path: str,
    resolve: ConditionResolver,
) -> tuple[GoalItem, list[Issue], list[Ref]]:
    if item.claim_ref != claim.claim_ref or (
        item.item_id is not None and item.item_id not in prior_item_ids
    ):
        raise RequestError(409, "invalid_reference", "目标项或 Claim 修订不属于本次保存范围。")
    identities = {
        (method.method_ref.object_id, method.method_ref.version) for method in item.methods
    }
    if len(identities) != len(item.methods) or (
        item.method_mode == "specified" and len(identities) != 1
    ):
        raise RequestError(400, "invalid_reference", "指定方式需恰好一种方法，方法不能重复。")
    allowed = allowed_methods(item, claim, chapters)
    methods: list[MethodRequirement] = []
    gaps: list[Issue] = []
    for index, method in enumerate(item.methods):
        chapter_ids = set(method.chapter_refs)
        identity = (method.method_ref.object_id, method.method_ref.version)
        if len(chapter_ids) != len(method.chapter_refs) or not chapter_ids <= set(
            allowed.get(identity, [])
        ):
            raise RequestError(409, "invalid_reference", "方法只可关联实际采用该方法的章节。")
        revised, missing = _method(method, claim, f"{path}/methods/{index}", resolve)
        methods.append(revised)
        gaps.extend(missing)
    saved = GoalItem(
        item_id=item.item_id or uuid4(),
        title=item.title,
        claim_ref=claim.claim_ref,
        chapter_refs=item.chapter_refs,
        task_conditions=item.task_conditions,
        method_mode=item.method_mode,
        methods=methods,
    )
    return saved, gaps, [chapters[chapter].association_ref for chapter in item.chapter_refs]
