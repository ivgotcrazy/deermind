import type { BookTypes } from '../../../shared/book/editions';

export type Model = BookTypes['TeachingModel'];
export type Task = BookTypes['ModelTask'];
export type Knowledge = BookTypes['ModelKnowledge'];
export type Method = BookTypes['ModelMethod'];
export type Selection = { kind: 'knowledge' | 'tasks'; key: string };

export function newMethod(): Method {
  return {
    key: crypto.randomUUID(),
    name: '',
    steps: '',
    rationale: '',
    applicability: '',
    dependencies: [],
  };
}

export function newTask(chapter: string, knowledge?: Knowledge): Task {
  return {
    key: crypto.randomUUID(),
    name: knowledge ? '掌握' + knowledge.name : '',
    chapter_id: chapter,
    source_nodes: [],
    task_type: knowledge ? 'knowledge' : 'composite',
    knowledge_key: knowledge?.key ?? null,
    description: '',
    expected_output: '',
    completion_conditions: '',
    insufficient_example: '',
    methods: [],
  };
}

export function dependents(model: Model, task: Task) {
  return model.tasks.flatMap((owner) =>
    owner.methods
      .filter((m) => m.dependencies.some((d) => d.task_key === task.key))
      .map((method) => ({ owner, method })),
  );
}

export function prerequisites(task: Task) {
  return [...new Set(task.methods.flatMap((m) => m.dependencies.map((d) => d.task_key)))];
}
