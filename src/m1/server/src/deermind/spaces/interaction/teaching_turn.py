"""Advance a teaching activity from a fixed context and candidate."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution
from deermind.foundation.system.executions import store
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import history
from deermind.spaces.interaction.blueprints import entry_node
from deermind.spaces.interaction.conversation import (
    Conversation,
    activity_change,
    draft,
    next_position,
    notice_events,
    ref,
    revise,
    store_position,
)
from deermind.spaces.interaction.public import BlueprintNode, ConfigView, StudentInput
from deermind.spaces.interaction.reply_candidate import ReplyCandidate
from deermind.spaces.interaction.teaching_flow import TeachingDecision, decide
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def apply_teaching_turn(
    conversation: Conversation,
    db: AsyncConnection,
    work: Execution,
    candidate: ReplyCandidate,
    config: ConfigView | None,
    parent_config: ConfigView | None,
    bundle: facts.ContextFact | None,
    candidate_id: UUID,
) -> tuple[Literal["completed", "needs_input", "blocked"], str]:
    """Apply the accepted lesson action inside the current turn transaction."""
    # 配置、上下文包缺失，或上下文目的与候选意图不符，转为追问。
    if config is None or bundle is None or bundle.purpose != candidate.intent:
        return "needs_input", "你想继续当前内容，还是插入一个新问题？"
    scope, identity = work.scope_id, UUID(work.input_ref.id)
    current = await history.current(db, scope)
    leaf = current.current_activity
    # 已有活动修订则定位当前节点，否则取蓝图入口节点。
    node = (
        next(item for item in config.definition.blueprint.nodes if item.node_id == leaf.node_id)
        if bundle.activity_revision_ref and leaf
        else entry_node(config.definition.blueprint)
    )
    if node is None:
        # 蓝图无可自动通过的开始节点，阻断本轮。
        return "blocked", "当前讲解缺少可用的开始节点。"
    item = (
        await db.execute(
            text(
                "SELECT input,source_event_id,request_id FROM interaction.inputs "
                "WHERE scope_id=:scope AND input_id=:id"
            ),
            {"scope": scope, "id": identity},
        )
    ).one()
    source = StudentInput.model_validate_json(canonical_json(item.input))
    original_text = source.text or ""
    placement = candidate.teaching.placement if candidate.teaching else "continue"
    quote = candidate.teaching.placement_quote if candidate.teaching else None
    node_actions = None
    if parent_config and leaf:
        # 读取父蓝图当前节点的允许动作，用于判定子活动/换题是否被授权。
        parent_node = next(
            part
            for part in parent_config.definition.blueprint.nodes
            if part.node_id == leaf.node_id
        )
        node_actions = parent_node.allowed_actions
    placed = (
        placement == "continue"
        if bundle.activity_revision_ref is not None or node_actions is None
        else (
            # 子活动/新话题落点须带引文、引文出自原文，且父节点授权对应动作。
            placement in {"child", "new_topic"}
            and quote is not None
            and quote in original_text
            and ("start_child" if placement == "child" else "switch") in node_actions
        )
    )

    choice = (
        decide(config.definition, node, candidate.teaching, original_text, {})
        if candidate.teaching and placed
        else TeachingDecision("clarify", reason="activity_placement_unavailable")
    )
    authority = await store.authorization(db, work.execution_id)
    principal, request = UUID(authority.initiator_ref.id), UUID(work.acceptance_key)
    applied: Ref | None = bundle.activity_revision_ref
    if choice.action == "reply":
        # 获准回复时在事务内推进活动并落修订。
        applied = await _apply_lesson(
            conversation,
            db,
            work,
            scope,
            principal,
            candidate,
            config,
            bundle,
            node,
            choice,
            item.source_event_id,
            item.request_id,
            placement,
        )
    decision_id = uuid4()
    owner = ref("decision", decision_id)
    saved = facts.DecisionFact(
        decision_id=decision_id,
        scope_id=scope,
        input_ref=identity,
        source_trigger_ref=None,
        activity_revision_ref=bundle.activity_revision_ref,
        context_bundle_id=bundle.bundle_id,
        ai_candidate_ref=Ref(owner="ai", type="candidate", id=str(candidate_id)),
        proposal=candidate.model_dump(mode="json"),
        validation={"passed": choice.reason is None, "reason": choice.reason},
        accepted_action={
            "action": choice.action,
            "placement": placement,
            "transition_id": choice.transition.transition_id if choice.transition else None,
            "activity_revision_ref": applied.model_dump(mode="json") if applied else None,
        },
        created_at=datetime.now(UTC),
    )
    await conversation.append(
        db,
        scope,
        principal,
        request,
        [
            draft(
                scope,
                facts.DECISION_RECORDED,
                owner,
                facts.DecisionRecorded(
                    subject_ref=owner,
                    # 决策结果：回复为 allowed，澄清为 clarify，其余为 denied。
                    outcome="allowed"
                    if choice.action == "reply"
                    else "clarify"
                    if choice.action == "clarify"
                    else "denied",
                    reason_code=choice.reason,
                    records=[facts.record(facts.DECISION, decision_id, saved)],
                ),
                item.request_id,
            )
        ],
    )
    if choice.action == "reply":
        # 活动已推进，本轮完成。
        return "completed", candidate.wording
    if choice.action == "clarify":
        # 需追问：有回退原因时用兜底话术，否则用候选原话。
        return "needs_input", node.fallback.explanation if choice.reason else candidate.wording
    return "blocked", node.fallback.explanation


async def _apply_lesson(
    conversation: Conversation,
    db: AsyncConnection,
    work: Execution,
    scope: UUID,
    principal: UUID,
    candidate: ReplyCandidate,
    config: ConfigView,
    bundle: facts.ContextFact,
    node: BlueprintNode,
    choice: TeachingDecision,
    trigger: UUID,
    request_id: str,
    placement: Literal["continue", "child", "new_topic"],
) -> Ref:
    request = UUID(work.acceptance_key)
    identity = UUID(work.input_ref.id)
    current = await history.current(db, scope)
    leaf = current.current_activity
    if bundle.activity_revision_ref is None:
        # 未挂既有活动：子活动挂靠当前叶，新话题不设父活动。
        parent_id = leaf.activity_ref.activity_id if leaf and placement == "child" else None
        if leaf is not None and parent_id is None:
            path = await history.lineage(db, scope, leaf.activity_ref.activity_id)
            completed = leaf.type == "free_chat" and leaf.parent_id is None
            if not completed and placement != "new_topic":
                # 既有课程只能由经核验的换题挂起，其余情况拒绝。
                raise ValueError("Only a verified topic change can suspend an active lesson")
            now = datetime.now(UTC)
            changes = [
                activity_change(
                    state.identity,
                    revise(
                        state.position,
                        "completed" if completed else "paused",
                        "end" if completed else state.position.node_id,
                        "change_topic",
                        now,
                        input_id=identity,
                    ),
                    request_id,
                )
                for state in path
            ]
            seq, epoch = await next_position(db, scope)
            await conversation.append(
                db,
                scope,
                principal,
                request,
                [
                    *changes,
                    *notice_events(
                        scope,
                        leaf.activity_ref.activity_id,
                        uuid4(),
                        seq,
                        "自由交谈已结束。" if completed else "已暂停「" + leaf.name + "」。",
                        now,
                        input_id=identity,
                        request=request_id,
                    ),
                ],
            )
            await store_position(db, scope, None, seq, epoch)
        adoption_ref = Ref(owner="product", type="space_adoption", id=str(bundle.adoption_ref))
        started = await conversation.begin(
            db,
            scope,
            principal,
            adoption_ref,
            config.config_ref,
            config.definition,
            bundle.purpose,
            candidate.topic,
            trigger,
            parent_id=parent_id,
            input_id=identity,
            initial_node=node.node_id,
            request_ref=request,
        )
        leaf_id = started.activity_id
    else:
        # 挂既有活动：以上下文包中的活动修订为准。
        leaf_id = UUID(bundle.activity_revision_ref.id)
        if (
            leaf is None
            or ref("activity", leaf.activity_ref.activity_id, leaf.activity_ref.revision)
            != bundle.activity_revision_ref
        ):
            # 候选接受前活动已切换，拒绝落盘。
            raise ValueError("The lesson changed before its candidate was accepted")
    state = await history.activity_at(db, scope, leaf_id)
    if choice.transition is None:
        # 未选中具体转移，返回当前修订引用。
        return ref("activity", leaf_id, state.position.revision)
    target = choice.transition.target_node_id
    revised = revise(
        state.position,
        # 转移到 end 记完成，否则保持 active。
        "completed" if target == "end" else "active",
        target,
        choice.transition.transition_id,
        datetime.now(UTC),
        input_id=identity,
    )
    await conversation.append(
        db, scope, principal, request, [activity_change(state.identity, revised, request_id)]
    )
    return ref("activity", leaf_id, revised.revision)
