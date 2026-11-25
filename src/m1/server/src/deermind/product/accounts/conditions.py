"""首次使用条件的确定性计算；仅接受已由业务核实的关系和确认，不调用AI。"""

from datetime import datetime
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.product.accounts.usage_facts import (
    ConditionsFact,
    ConfirmationFact,
    UsageIssue,
)


def derive_conditions(
    *,
    student_id: UUID,
    revision: int,
    now: datetime,
    notice_ref: Ref,
    guardian_verified: bool,
    confirmations: list[ConfirmationFact],
) -> ConditionsFact:
    """调用方在锁内选定每类最新确认；旧告知、其他学生和重复类别不能混入。

    结果只由实际决定和已核实关系产生。保存事件后，重建使用该结果正文，
    不能再次调用本函数以当前规则重算历史。
    """
    current: dict[str, ConfirmationFact] = {}
    for fact in confirmations:
        if fact.student_id != student_id or fact.notice_ref != notice_ref:
            # 确认须属于本学生和本告知版本，防止混入他人或旧告知。
            raise ValueError("Confirmation does not belong to this student and notice")
        if fact.kind in current:
            # 每类只允许一条当前确认。
            raise ValueError("Select one current confirmation per kind before calculation")
        current[fact.kind] = fact

    reasons: list[UsageIssue] = []
    if not guardian_verified:
        reasons.append(
            UsageIssue(
                code="guardian_verification_required",
                path="guardian",
                message="监护关系尚未核实，请联系管理员。",
            )
        )
    for kind, label in (("guardian_consent", "监护人同意"), ("student_assent", "本人使用意愿")):
        fact = current.get(kind)
        if fact is None or fact.decision != "accepted":
            # 区分"已拒绝"与"尚未确认"，给出不同缺口码。
            declined = fact is not None and fact.decision == "declined"
            reasons.append(
                UsageIssue(
                    code=kind + ("_declined" if declined else "_required"),
                    path=kind,
                    message=f"{label}{'尚未同意' if declined else '尚未确认'}。",
                )
            )
    rejected = any(fact.decision == "declined" for fact in current.values())
    # 任一拒绝即阻断；无拒绝但仍有缺口为待定；缺口清空才放行。
    eligibility = "blocked" if rejected else ("pending" if reasons else "allowed")
    return ConditionsFact(
        student_id=student_id,
        revision=revision,
        confirmation_refs=[
            Ref(owner="product", type="usage_confirmation", id=str(fact.confirmation_id))
            for _, fact in sorted(current.items())
        ],
        eligibility=eligibility,
        reasons=reasons,
        updated_at=now,
    )
