/** 正文类型由领域接口生成。 */
import type { components } from '../../../../contracts/generated/http/schema';

export type RichContent = components['schemas']['RichContent-Output'];
type Block = RichContent['blocks'][number];

export type DataTable = RichContent['data_tables'][number];
export type Chart = Extract<Block, { type: 'chart' }>['payload'];
export type Diagram = Extract<Block, { type: 'diagram' }>['payload'];
export type MathExpression = Extract<
  Block,
  { type: 'math_sequence' }
>['payload']['lines'][number]['expression'];
