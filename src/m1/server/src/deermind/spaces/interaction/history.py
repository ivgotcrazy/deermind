"""按空间查询活动和正式消息，分页期间固定消息上界。"""

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.foundation.system.public.errors import RequestError
from deermind.spaces.interaction.conversation_facts import ActivityFact, RevisionFact
from deermind.spaces.interaction.public import (
    ActivityPage,
    ActivityRef,
    ActivityView,
    CurrentConversation,
    DetectionPlanRef,
    DetectionRoundView,
    MessagePage,
    MessageView,
)
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

_ACTIVITY = """
    SELECT to_jsonb(a)-'source_event_id' AS identity,
           to_jsonb(r)-'source_event_id' AS position,
           EXISTS (SELECT 1 FROM interaction.activities c
                   WHERE c.scope_id=a.scope_id AND c.parent_id=a.activity_id) AS has_children
    FROM interaction.activities a
    JOIN interaction.activity_heads h USING(activity_id)
    JOIN interaction.activity_revisions r USING(activity_id,revision)
"""


@dataclass(frozen=True)
class ActivityState:
    """当前活动身份和修订，均来自同一查询。"""

    identity: ActivityFact
    position: RevisionFact
    has_children: bool

    def view(self) -> ActivityView:
        """返回目录与标题栏需要显示的字段。"""
        activity, revision = self.identity, self.position
        return ActivityView(
            activity_ref=ActivityRef(activity_id=activity.activity_id, revision=revision.revision),
            type=activity.type,
            name=activity.name,
            started_at=activity.started_at,
            parent_id=activity.parent_id,
            root_id=activity.root_id,
            node_id=revision.node_id,
            run_state=revision.run_state,
            first_message_ref=activity.first_message_ref,
            has_children=self.has_children,
        )


def _state(row: RowMapping) -> ActivityState:
    return ActivityState(
        ActivityFact.model_validate_json(canonical_json(row["identity"])),
        RevisionFact.model_validate_json(canonical_json(row["position"])),
        bool(row["has_children"]),
    )


async def activity_at(db: AsyncConnection, scope: UUID, activity: UUID) -> ActivityState:
    """只读取指定空间中的活动。"""
    row = (
        (
            await db.execute(
                text(_ACTIVITY + " WHERE a.scope_id=:scope AND a.activity_id=:id"),
                {"scope": scope, "id": activity},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RequestError(404, "not_found", "找不到这个活动。")
    return _state(row)


async def lineage(db: AsyncConnection, scope: UUID, leaf: UUID) -> list[ActivityState]:
    """读取从根到叶的路径，一次查询取得所有当前修订。"""
    found = await db.execute(
        text(
            """
            WITH RECURSIVE paths AS (
                SELECT activity_id,parent_id,0 AS depth FROM interaction.activities
                WHERE scope_id=:scope AND activity_id=:leaf
                UNION ALL
                SELECT a.activity_id,a.parent_id,p.depth+1 FROM interaction.activities a
                JOIN paths p ON p.parent_id=a.activity_id WHERE a.scope_id=:scope
            )
            """
            + _ACTIVITY
            + " JOIN paths p ON p.activity_id=a.activity_id ORDER BY p.depth DESC"
        ),
        {"scope": scope, "leaf": leaf},
    )
    return [_state(row) for row in found.mappings()]


async def current(db: AsyncConnection, scope: UUID) -> CurrentConversation:
    """读取当前叶和消息顺序。没有活动时返回空路径。"""
    row = (
        await db.execute(
            text(
                "SELECT current_leaf_ref,active_input_id,last_message_seq "
                "FROM interaction.space_runtime WHERE scope_id=:scope"
            ),
            {"scope": scope},
        )
    ).one_or_none()
    leaf = row.current_leaf_ref if row else None
    path = [state.view() for state in await lineage(db, scope, leaf)] if leaf else []
    active = row.active_input_id if row else None
    round_view = await current_round(db, leaf) if leaf and path[-1].type == "detection" else None
    return CurrentConversation(
        current_activity=path[-1] if path else None,
        path=path,
        active_input_id=active,
        allowed_actions=["pause", "finish"] if path and not active else [],
        latest_message_seq=row.last_message_seq if row else 0,
        current_round=round_view,
    )


async def current_round(db: AsyncConnection, activity_id: UUID) -> DetectionRoundView | None:
    row = (
        await db.execute(
            text(
                "SELECT r.round_id,r.task_use_ref,r.plan_id,r.plan_revision,rr.revision,rr.state, "
                "(p.status='confirmed' AND jsonb_array_length(v.items)>(SELECT count(*) "
                "FROM interaction.detection_rounds used WHERE (used.plan_id,used.plan_revision)="
                "(r.plan_id,r.plan_revision))) AS remaining "
                "FROM interaction.detection_rounds r "
                "JOIN interaction.round_revisions rr USING(round_id) "
                "JOIN interaction.plan_revisions v "
                "ON (v.plan_id,v.revision)=(r.plan_id,r.plan_revision) "
                "JOIN interaction.plan_progress p "
                "ON (p.plan_id,p.plan_revision)=(r.plan_id,r.plan_revision) "
                "WHERE r.activity_id=:activity ORDER BY r.opened_at DESC, rr.revision DESC LIMIT 1"
            ),
            {"activity": activity_id},
        )
    ).one_or_none()
    if row is None:
        return None
    return DetectionRoundView(
        round_ref=Ref(
            owner="interaction", type="round", id=str(row.round_id), revision=row.revision
        ),
        task_use_ref=Ref(owner="interaction", type="task_use", id=str(row.task_use_ref)),
        plan_ref=DetectionPlanRef(plan_id=row.plan_id, revision=row.plan_revision),
        state=row.state,
        can_continue=row.state == "closed" and row.remaining,
    )


def _cursor(token: str, cursor: str | None) -> str | None:
    if cursor is None:
        return None
    prefix, separator, value = cursor.partition(".")
    if prefix != token or not separator or not value:
        raise RequestError(400, "invalid_cursor", "这个游标不属于当前查询。")
    return value


def _token(*values: str) -> str:
    return sha256(canonical_json(list(values)).encode()).hexdigest()


async def directory(
    db: AsyncConnection,
    account: UUID,
    scope: UUID,
    parent: UUID | None,
    cursor: str | None,
    limit: int,
) -> ActivityPage:
    """顶层从新到旧，展开直接子活动时从早到晚。"""
    if parent is not None:
        await activity_at(db, scope, parent)
    token = _token(str(account), str(scope), "activity_tree", str(parent))
    position = _cursor(token, cursor)
    operator, direction = (">", "ASC") if parent else ("<", "DESC")
    values: dict[str, object] = {"scope": scope, "parent": parent, "limit": limit + 1}
    clause = " WHERE a.scope_id=:scope AND a.parent_id IS NOT DISTINCT FROM CAST(:parent AS uuid)"
    if position is not None:
        try:
            anchor = await activity_at(db, scope, UUID(position))
            if anchor.identity.parent_id != parent:
                raise ValueError("Cursor outside parent")
        except (RequestError, ValueError) as error:
            raise RequestError(400, "invalid_cursor", "找不到游标对应的活动。") from error
        values.update(time=anchor.identity.started_at, id=anchor.identity.activity_id)
        clause += f" AND (a.started_at,a.activity_id) {operator} (:time,:id)"
    rows = (
        (
            await db.execute(
                text(
                    _ACTIVITY + clause + f" ORDER BY a.started_at {direction},a.activity_id "
                    f"{direction} LIMIT :limit"
                ),
                values,
            )
        )
        .mappings()
        .all()
    )
    items = [_state(row).view() for row in rows[:limit]]
    next_cursor = f"{token}.{items[-1].activity_ref.activity_id}" if len(rows) > limit else None
    return ActivityPage(items=items, next_cursor=next_cursor)


async def messages(
    db: AsyncConnection,
    account: UUID,
    scope: UUID,
    activity: UUID | None,
    anchor: UUID | None,
    after: int,
    cursor: str | None,
    limit: int,
) -> MessagePage:
    """顺序补读或者从活动首条消息附近查询。"""
    if activity is not None:
        await activity_at(db, scope, activity)
    token = _token(str(account), str(scope), "messages", str(activity), str(anchor))
    position = _cursor(token, cursor)
    upper = (await current(db, scope)).latest_message_seq
    if position is not None:
        pair = position.split(",")
        if len(pair) != 2 or any(not entry.isascii() or not entry.isdigit() for entry in pair):
            raise RequestError(400, "invalid_cursor", "消息续页位置不正确。")
        after, fixed_upper = map(int, pair)
        if not 0 <= after <= fixed_upper <= upper:
            raise RequestError(400, "invalid_cursor", "消息续页范围不正确。")
        upper = fixed_upper
    elif anchor is not None:
        anchor_seq = await db.scalar(
            text(
                "SELECT message_seq FROM interaction.messages "
                "WHERE scope_id=:scope AND message_id=:id"
            ),
            {"scope": scope, "id": anchor},
        )
        if not isinstance(anchor_seq, int):
            raise RequestError(404, "not_found", "找不到这条聊天记录。")
        after = max(0, anchor_seq - max(1, limit // 3))
    if after > upper:
        raise RequestError(400, "invalid_request", "消息起点超过当前记录范围。")
    rows = (
        await db.scalars(
            text(
                "SELECT (to_jsonb(m)-'source_event_id'-'scope_id'-'source_input_ref'"
                "-'source_trigger_ref') || jsonb_build_object('activity_ref',"
                "CASE WHEN a.activity_id IS NULL THEN NULL ELSE "
                "jsonb_build_object('activity_id',a.activity_id,'revision',h.revision) END) "
                "FROM interaction.messages m "
                "LEFT JOIN interaction.message_assignments a USING(message_id) "
                "LEFT JOIN interaction.activity_heads h USING(activity_id) "
                "WHERE m.scope_id=:scope AND m.message_seq>:after AND m.message_seq<=:upper "
                "AND (CAST(:activity AS uuid) IS NULL OR a.activity_id=:activity) "
                "ORDER BY m.message_seq LIMIT :limit"
            ),
            {
                "scope": scope,
                "after": after,
                "upper": upper,
                "activity": activity,
                "limit": limit + 1,
            },
        )
    ).all()
    items = [MessageView.model_validate_json(canonical_json(row)) for row in rows[:limit]]
    last = items[-1].message_seq if items else after
    return MessagePage(
        items=items,
        next_cursor=f"{token}.{last},{upper}" if len(rows) > limit else None,
        last_seq=last,
        upper_seq=upper,
    )
