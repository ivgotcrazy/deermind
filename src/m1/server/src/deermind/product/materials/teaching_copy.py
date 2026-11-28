"""Start an editable draft from an older published snapshot without changing its facts."""

from uuid import NAMESPACE_URL, uuid5

from deermind.product.public.material_editions import (
    ModelKnowledge,
    ModelMethod,
    ModelTask,
    TeachingDependency,
    TeachingModel,
    TeachingTask,
)


def local_key(kind: str, name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"deermind:{kind}:{name}"))


def copy_legacy(tasks: list[TeachingTask]) -> TeachingModel:
    knowledge: dict[str, ModelKnowledge] = {}
    paired: list[ModelTask] = []
    composites: list[ModelTask] = []
    for task in tasks:
        common = task.model_dump(
            include={
                "chapter_id",
                "source_nodes",
                "description",
                "expected_output",
                "completion_conditions",
            }
        )
        for concept in task.direct_knowledge:
            if concept.name in knowledge:
                continue
            key = local_key("knowledge", concept.name)
            knowledge[concept.name] = ModelKnowledge(
                key=key,
                name=concept.name,
                meaning=concept.meaning,
                applicability=concept.applicability,
            )
            method = next((m for m in task.methods if m.name == concept.test_method), None)
            paired.append(
                ModelTask(
                    chapter_id=task.chapter_id,
                    source_nodes=task.source_nodes,
                    description=task.description,
                    expected_output=concept.observable_behavior,
                    completion_conditions=task.completion_conditions,
                    key=local_key("master", concept.name),
                    name="掌握" + concept.name,
                    task_type="knowledge",
                    knowledge_key=key,
                    insufficient_example=concept.insufficient_example,
                    methods=[
                        ModelMethod(
                            **method.model_dump(exclude={"knowledge"}),
                            key=local_key("method", method.name),
                            dependencies=[],
                        )
                    ]
                    if method
                    else [],
                )
            )
        methods: list[ModelMethod] = []
        for method in task.methods:
            deps = [
                TeachingDependency(task_key=local_key("task", n), reason="原版任务先导")
                for n in dict.fromkeys(task.prerequisites)
            ]
            deps.extend(
                TeachingDependency(task_key=local_key("master", n), reason="原版方法所需知识")
                for n in dict.fromkeys(method.knowledge)
            )
            methods.append(
                ModelMethod(
                    **method.model_dump(exclude={"knowledge"}),
                    key=local_key("method", method.name),
                    dependencies=deps,
                )
            )
        composites.append(
            ModelTask(
                **common,
                key=local_key("task", task.name),
                name=task.name,
                task_type="composite",
                knowledge_key=None,
                methods=methods,
            )
        )
    return TeachingModel(knowledge=list(knowledge.values()), tasks=paired + composites)
