"""蓝图不接受缺失保留节点或断开的路径。"""

import unittest

from deermind.foundation.system.public.errors import RequestError
from deermind.spaces.interaction.blueprints import validate_blueprint
from deermind.spaces.interaction.public import BlueprintDefinition


class ActivityBlueprintTests(unittest.TestCase):
    def test_standard_node_ids_and_conditions_are_checked_as_a_graph(self) -> None:
        blueprint = BlueprintDefinition.model_validate(
            {
                "activity_type": "explanation",
                "nodes": [
                    {
                        "node_id": identity,
                        "name": name,
                        "purpose": name,
                        "required_inputs": [],
                        "execution_guidance": "确认当前环节后再继续。",
                        "outputs": [],
                        "allowed_actions": ["reply"] if identity == "explain" else [],
                        "fallback": {"action": "clarify", "explanation": "下一步不明时先澄清。"},
                    }
                    for identity, name in (("start", "开始"), ("explain", "讲解"), ("end", "结束"))
                ],
                "transitions": [
                    {
                        "transition_id": f"step-{n}",
                        "source_node_id": start,
                        "target_node_id": end,
                        "order": 1,
                        "when": "on_enter" if n == 1 else "after_reply",
                        "required_facts": [],
                        "evidence_required": False,
                    }
                    for n, (start, end) in enumerate((("start", "explain"), ("explain", "end")), 1)
                ],
            }
        )
        validate_blueprint(blueprint)
        for edited in (
            blueprint.model_copy(update={"nodes": blueprint.nodes[1:]}),
            blueprint.model_copy(update={"nodes": blueprint.nodes[:-1]}),
            blueprint.model_copy(update={"transitions": blueprint.transitions[:1]}),
        ):
            with self.subTest(edited=edited), self.assertRaises(RequestError) as caught:
                validate_blueprint(edited)
            self.assertEqual(caught.exception.code, "invalid_blueprint")
