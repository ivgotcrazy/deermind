"""蓝图节点、条件转移和配置绑定的确定性校验。"""

from collections import defaultdict, deque
from uuid import UUID

from deermind.foundation.system.public.errors import Issue, RequestError
from deermind.spaces.interaction.public import (
    BlueprintDefinition,
    BlueprintNode,
    LocalBinding,
    ResolvedActivityConfig,
)


def entry_node(blueprint: BlueprintDefinition) -> BlueprintNode | None:
    """只自动通过不需要运行事实或语义判断的开始转移。"""
    edges = sorted(
        (
            edge
            for edge in blueprint.transitions
            if edge.source_node_id == "start" and edge.when == "on_enter"
        ),
        key=lambda edge: edge.order,
    )
    if not edges:
        # start 没有进入转移，无入口节点。
        return None
    first = edges[0]
    # 直达结束、需事实或条件判定的转移不能自动通过，返回空。
    if first.target_node_id == "end" or first.required_facts or first.condition_text:
        return None
    return next(node for node in blueprint.nodes if node.node_id == first.target_node_id)


def _reach(start: str, edges: dict[str, set[str]]) -> set[str]:
    visited = {start}
    queue = deque([start])
    while queue:
        # 逐层取出尚未访问的后继并入队，完成可达集合遍历。
        successors = edges.get(queue.popleft(), set()) - visited
        visited.update(successors)
        queue.extend(successors)
    return visited


def validate_blueprint(blueprint: BlueprintDefinition) -> None:
    ids = {node.node_id for node in blueprint.nodes}
    # 节点集合必须包含 start/end，且节点编号不重复。
    if not {"start", "end"} <= ids or len(ids) != len(blueprint.nodes):
        raise RequestError(400, "invalid_blueprint", "须保留唯一的开始与结束节点。")
    forward: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    slots: set[tuple[str, int]] = set()
    transitions: set[str] = set()
    for edge in blueprint.transitions:
        source, target = edge.source_node_id, edge.target_node_id
        # 端点须存在，不得从 end 出发或指向 start，转移编号与同节点顺序不得重复。
        if (
            source not in ids
            or target not in ids
            or source == "end"
            or target == "start"
            or edge.transition_id in transitions
            or (source, edge.order) in slots
        ):
            raise RequestError(400, "invalid_blueprint", "连接目标、编号或顺序无效。")
        facts = {fact.code for fact in edge.required_facts}
        # 事实编码不得重复；要求证据时必须有条件文本。
        if len(facts) != len(edge.required_facts) or (
            edge.evidence_required and not edge.condition_text
        ):
            raise RequestError(400, "invalid_blueprint", "条件的依据或程序事实不完整。")
        transitions.add(edge.transition_id)
        slots.add((source, edge.order))
        forward[source].add(target)
        reverse[target].add(source)
    # 正向从 start 可达全部节点，反向从 end 也可达全部节点，保证无孤岛。
    if _reach("start", forward) != ids or _reach("end", reverse) != ids:
        raise RequestError(400, "invalid_blueprint", "所有节点须从开始可达，也须有路径通往结束。")
    for node in blueprint.nodes:
        # 普通节点必须挂至少一个允许动作。
        if node.node_id not in {"start", "end"} and not node.allowed_actions:
            raise RequestError(400, "invalid_blueprint", "普通节点至少需要一个允许动作。")


def validate_bindings(config: ResolvedActivityConfig) -> list[Issue]:
    # 绑定覆盖的节点须都在蓝图节点集合内。
    if not config.binding.nodes.keys() <= {node.node_id for node in config.blueprint.nodes}:
        raise RequestError(409, "invalid_reference", "节点规则或策略引用了不存在的节点。")
    rules = {UUID(item.ref.id): item for item in config.rules}
    strategies = {UUID(item.ref.id): item for item in config.strategies}
    for binding in [config.binding.activity, *config.binding.nodes.values()]:
        # 引用的规则、策略必须在同活动已登记集合内。
        if (
            not set(binding.rule_ids) <= rules.keys()
            or not set(binding.strategy_ids) <= strategies.keys()
        ):
            raise RequestError(409, "invalid_reference", "请选择同类活动已有的规则或策略。")
    # 活动级规则中没有任何启用定义时，返回提示问题。
    if not any(rules[rule].definition.enabled for rule in config.binding.activity.rule_ids):
        return [
            Issue(
                code="missing_activity_rules",
                path="/binding/activity/rule_ids",
                message="尚未选择活动级规则。",
            )
        ]
    return []


def effective_binding(config: ResolvedActivityConfig, node_id: str) -> LocalBinding:
    """节点只声明本层；有效内容始终叠加活动规则，停用定义退出现行配置。"""
    activity = config.binding.activity
    node = config.binding.nodes.get(node_id, LocalBinding(rule_ids=[], strategy_ids=[]))
    rules = {UUID(item.ref.id) for item in config.rules if item.definition.enabled}
    strategies = {UUID(item.ref.id) for item in config.strategies if item.definition.enabled}
    # 活动层与节点层规则、策略合并去重，只保留当前启用的定义。
    return LocalBinding(
        rule_ids=[
            key for key in dict.fromkeys([*activity.rule_ids, *node.rule_ids]) if key in rules
        ],
        strategy_ids=[
            key
            for key in dict.fromkeys([*activity.strategy_ids, *node.strategy_ids])
            if key in strategies
        ],
    )
