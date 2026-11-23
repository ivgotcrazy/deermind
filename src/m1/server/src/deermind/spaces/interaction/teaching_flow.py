"""按固定蓝图验证语义候选与程序事实，选择本轮活动动作。"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from deermind.abstractions.events import FactModel
from deermind.spaces.interaction.blueprints import effective_binding
from deermind.spaces.interaction.public import (
    BlueprintNode,
    NodeId,
    ResolvedActivityConfig,
    Transition,
    Wording,
)


class ConditionCheck(FactModel):
    transition_id: NodeId
    status: Literal["met", "not_met", "unknown"]
    input_quote: Wording | None


class RuleCheck(FactModel):
    rule_id: str
    status: Literal["satisfied", "not_applicable", "violated", "unknown"]
    input_quote: Wording | None


class TeachingProposal(FactModel):
    action: Literal["reply", "clarify"]
    conditions: list[ConditionCheck]
    rules: list[RuleCheck]
    placement: Literal["continue", "child", "new_topic"] = "continue"
    placement_quote: Wording | None = None


@dataclass(frozen=True)
class TeachingDecision:
    action: Literal["reply", "clarify", "wait_input", "blocked"]
    transition: Transition | None = None
    reason: str | None = None


def _fallback(node: BlueprintNode, reason: str) -> TeachingDecision:
    action = node.fallback.action
    if action == "clarify" and "clarify" not in node.allowed_actions:
        action = "blocked"
    return TeachingDecision(action, reason=reason)


def decide(
    config: ResolvedActivityConfig,
    node: BlueprintNode,
    proposal: TeachingProposal,
    source_text: str,
    facts: Mapping[str, bool],
) -> TeachingDecision:
    """模型没有动作授权。未知硬事实或语义不会绕过排在前面的转移。"""
    if proposal.action not in node.allowed_actions:
        return _fallback(node, "action_not_allowed")
    rules = effective_binding(config, node.node_id).rule_ids
    reported = {item.rule_id: item for item in proposal.rules}
    if len(reported) != len(proposal.rules) or reported.keys() != {str(value) for value in rules}:
        return _fallback(node, "rule_checks_incomplete")
    for item in reported.values():
        if item.status not in {"satisfied", "not_applicable"} or (
            item.input_quote is not None and item.input_quote not in source_text
        ):
            return _fallback(node, "rule_checks_failed")

    transitions = sorted(
        (
            edge
            for edge in config.blueprint.transitions
            if edge.source_node_id == node.node_id and edge.when in {"on_input", "after_reply"}
        ),
        key=lambda edge: edge.order,
    )
    checks = {item.transition_id: item for item in proposal.conditions}
    if len(checks) != len(proposal.conditions) or not checks.keys() <= {
        edge.transition_id for edge in transitions if edge.condition_text
    }:
        return _fallback(node, "invalid_condition_checks")
    if proposal.action == "clarify":
        return TeachingDecision("clarify")
    for edge in transitions:
        results = [facts.get(required.code) for required in edge.required_facts]
        if any(
            value is not None and value != required.value
            for value, required in zip(results, edge.required_facts, strict=True)
        ):
            continue
        if any(value is None for value in results):
            return _fallback(node, "unknown_program_fact")
        if edge.condition_text:
            check = checks.get(edge.transition_id)
            if check is None or check.status == "unknown":
                return _fallback(node, "unknown_semantic_condition")
            if (edge.evidence_required and check.input_quote is None) or (
                check.input_quote is not None and check.input_quote not in source_text
            ):
                return _fallback(node, "condition_source_missing")
            if check.status == "not_met":
                continue
        return TeachingDecision("reply", edge)
    if transitions:
        return _fallback(node, "no_transition")
    return TeachingDecision("reply")
