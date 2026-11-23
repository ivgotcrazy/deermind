"""一次讲解只采用当前节点中首个得到依据的合法转移。"""

from unittest import TestCase

from deermind.abstractions.events import Ref
from deermind.spaces.interaction.public import (
    BindingDefinition,
    BlueprintDefinition,
    BlueprintNode,
    Fallback,
    LocalBinding,
    RequiredFact,
    ResolvedActivityConfig,
    Transition,
)
from deermind.spaces.interaction.teaching_flow import ConditionCheck, TeachingProposal, decide


def teaching_config() -> tuple[ResolvedActivityConfig, BlueprintNode]:
    node = BlueprintNode(
        node_id="explain",
        name="讲解",
        purpose="理解原量和增加量",
        required_inputs=[],
        execution_guidance="检查学生的解释。",
        outputs=[],
        allowed_actions=["reply", "clarify"],
        fallback=Fallback(action="clarify", explanation="你能再说一下理由吗？"),
    )
    edges = [
        Transition(
            transition_id="understands",
            source_node_id="explain",
            target_node_id="end",
            order=1,
            when="on_input",
            condition_text="学生说明为何要加回原量。",
            required_facts=[],
            evidence_required=True,
        ),
        Transition(
            transition_id="revisit",
            source_node_id="explain",
            target_node_id="explain",
            order=2,
            when="after_reply",
            required_facts=[],
            evidence_required=False,
        ),
    ]
    ref = Ref(owner="interaction", type="test_config", id="1")
    return (
        ResolvedActivityConfig(
            activity_type="explanation",
            blueprint_ref=ref,
            binding_ref=ref,
            blueprint=BlueprintDefinition(
                activity_type="explanation",
                nodes=[
                    node.model_copy(update={"node_id": "start"}),
                    node,
                    node.model_copy(update={"node_id": "end"}),
                ],
                transitions=edges,
            ),
            binding=BindingDefinition(
                activity_type="explanation",
                activity=LocalBinding(rule_ids=[], strategy_ids=[]),
                nodes={},
            ),
            rules=[],
            strategies=[],
        ),
        node,
    )


class TeachingFlowTests(TestCase):
    def test_unknown_or_invented_basis_never_skips_to_later_transition(self) -> None:
        config, node = teaching_config()
        for status, quote, code in (
            ("unknown", None, "unknown_semantic_condition"),
            ("met", "我已经懂了", "condition_source_missing"),
        ):
            check = ConditionCheck.model_validate(
                {"transition_id": "understands", "status": status, "input_quote": quote}
            )
            proposal = TeachingProposal(action="reply", conditions=[check], rules=[])
            with self.subTest(status=status):
                result = decide(config, node, proposal, "我不知道", {})
                self.assertEqual(result.action, "clarify")
                self.assertEqual(result.reason, code)
                self.assertIsNone(result.transition)

    def test_revisit_can_continue_with_no_recommended_strategy(self) -> None:
        config, node = teaching_config()
        proposal = TeachingProposal(
            action="reply",
            conditions=[
                ConditionCheck(transition_id="understands", status="not_met", input_quote="我没懂")
            ],
            rules=[],
        )
        result = decide(config, node, proposal, "我没懂，为什么加回原量？", {})
        self.assertEqual(result.action, "reply")
        assert result.transition is not None
        self.assertEqual(result.transition.transition_id, "revisit")

    def test_unknown_hard_fact_cannot_be_satisfied_by_model(self) -> None:
        config, node = teaching_config()
        config.blueprint.transitions[0] = config.blueprint.transitions[0].model_copy(
            update={"required_facts": [RequiredFact(code="plan_confirmed", value=True)]}
        )
        proposal = TeachingProposal(
            action="reply",
            conditions=[
                ConditionCheck(transition_id="understands", status="met", input_quote="确认")
            ],
            rules=[],
        )
        self.assertEqual(decide(config, node, proposal, "确认", {}).reason, "unknown_program_fact")
