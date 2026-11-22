/** 从表达树重建原演算，包括括号、结合顺序和约分标记。 */
import { defineComponent, h } from 'vue';
import type { PropType, VNode } from 'vue';
import type { MathExpression } from './types';

const operators = {
  add: '+',
  subtract: '−',
  multiply: '×',
  divide: '÷',
  equal: '=',
};

const precedence = {
  equal: 1,
  add: 2,
  subtract: 2,
  multiply: 3,
  divide: 3,
  number: 4,
  symbol: 4,
  fraction: 4,
  group: 4,
};

function inParentheses(body: VNode): VNode {
  return h('mrow', [h('mo', '('), body, h('mo', ')')]);
}

function number(expression: Extract<MathExpression, { op: 'number' }>): VNode {
  const replacements = expression.cancel_to ?? [];
  let value = h('mn', { class: { cancelled: replacements.length > 0 } }, expression.value);
  for (const [index, replacement] of replacements.entries()) {
    value = h('mover', { 'data-cancellation': '' }, [
      h('mrow', [value]),
      h('mn', { class: { cancelled: index < replacements.length - 1 } }, replacement),
    ]);
  }
  return value;
}

function render(expression: MathExpression, parentOrder = 0, isRight = false): VNode {
  switch (expression.op) {
    case 'number':
      return number(expression);
    case 'symbol':
      return h('mi', expression.name);
    case 'group': {
      const [inner] = expression.args;
      return inner ? inParentheses(render(inner)) : h('mtext', '公式结构不完整');
    }
    case 'fraction':
      return h(
        'mfrac',
        expression.args.map((operand) => render(operand)),
      );
    default: {
      const [left, right] = expression.args;
      if (!left || !right) return h('mtext', '公式结构不完整');
      const order = precedence[expression.op];
      const value = h('mrow', [
        render(left, order),
        h('mo', operators[expression.op]),
        render(right, order, true),
      ]);
      return order < parentOrder || (isRight && order === parentOrder)
        ? inParentheses(value)
        : value;
    }
  }
}

export default defineComponent({
  props: {
    expression: { type: Object as PropType<MathExpression>, required: true },
  },
  setup(props) {
    return () => h('math', [render(props.expression)]);
  },
});
