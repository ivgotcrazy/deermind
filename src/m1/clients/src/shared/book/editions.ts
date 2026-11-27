import type { components } from '../../../../contracts/generated/http/schema';
import { get } from '../api/http';

export type BookTypes = components['schemas'];
export type BookSession = Pick<BookTypes['SessionView'], 'session_id' | 'csrf_token'>;
export type Edition = BookTypes['Edition'];
export type Node = BookTypes['ContentNode'];
export type MapTask = BookTypes['MapTask'];
export const bookPath = '/api/m1/textbooks/{book}/editions';
export const editionPath = '/api/m1/textbooks/{book}/editions/{edition}';

export function nodeText(node: Node) {
  const text = node.content?.text;
  return typeof text === 'string' ? text : node.content ? JSON.stringify(node.content) : '';
}

const names: Record<Node['node_kind'], string> = {
  book: '全书',
  unit: '单元',
  chapter: '章',
  section: '节',
  group: '栏目',
  example: '例题',
  exercise: '练习',
  subquestion: '小问',
  solution: '解法',
  heading: '标题',
  paragraph: '段落',
  caption: '图注',
  formula: '公式',
  table: '表格',
  chart: '统计图',
  diagram: '示意图',
  image: '插图',
};

export function outline(nodes: Node[]) {
  const children = new Map<string | null, Node[]>();
  for (const node of nodes) {
    const siblings = children.get(node.parent_id) ?? [];
    siblings.push(node);
    children.set(node.parent_id, siblings);
  }
  const result: { node: Node; depth: number; title: string }[] = [];
  function visit(parent: string | null, depth: number) {
    for (const node of (children.get(parent) ?? []).sort(
      (a, b) => a.sibling_order - b.sibling_order,
    )) {
      const heading = children.get(node.node_id)?.find((n) => n.node_kind === 'heading');
      result.push({
        node,
        depth,
        title: nodeText(node) || (heading && nodeText(heading)) || names[node.node_kind],
      });
      visit(node.node_id, depth + 1);
    }
  }
  visit(null, 0);
  return result;
}

export function sectionOf(nodes: Node[], id: string): string {
  const byId = new Map(nodes.map((n) => [n.node_id, n]));
  let current = byId.get(id);
  while (current) {
    if (['chapter', 'unit', 'section'].includes(current.node_kind)) return current.node_id;
    current = current.parent_id ? byId.get(current.parent_id) : undefined;
  }
  return '';
}

export async function fixedChapters(session: BookSession, book: string, id: string) {
  const extraction = await get(editionPath, { session, params: { book, edition: id } });
  const tree = await get(editionPath, { session, params: { book, edition: extraction.tree_id! } });
  return outline(tree.nodes)
    .filter(({ node }) => ['unit', 'chapter', 'section'].includes(node.node_kind))
    .map(({ node, title }) => ({
      id: node.node_id,
      title,
      revision: tree.number,
      tasks: extraction.entries
        .filter((t) => t.chapter_id === node.node_id)
        .map((t) => ({
          active: true,
          task_ref: t.task_ref,
          method_refs: t.method_refs,
          association_ref: {
            owner: 'product',
            type: 'material_edition',
            id,
            revision: extraction.revision,
          },
        })),
    }));
}
