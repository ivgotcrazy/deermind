<script setup lang="ts">
import { computed } from 'vue';
import ContentTable from './ContentTable.vue';
import type { Chart, DataTable } from './types';

const { chart, table } = defineProps<{ chart: Chart; table: DataTable }>();

const plot = { left: 63, right: 610, top: 39, bottom: 236 };
const pieCenter = { x: 166, y: 147, radius: 105 };
const piePalette = ['#32644d', '#a44b38', '#517391', '#8b6330', '#5c5277', '#69793e'];

function values(column: string): string[] | undefined {
  const result: string[] = [];
  for (const row of table.rows) {
    const cell = row.cells[column];
    if (cell?.state !== 'provided') return undefined;
    result.push(cell.value);
  }
  return result;
}

const categories = computed(() => values(chart.category_column));
const cartesian = computed(() => {
  const { axis, series } = chart;
  const names = categories.value;
  if (chart.kind === 'pie' || !axis || !names?.length) return null;
  const minimum = Number(axis.min);
  const maximum = Number(axis.max);
  const step = Number(axis.step);
  const intervalCount = Math.floor((maximum - minimum) / step + 1e-9);
  const decimalPlaces = Math.max(
    axis.min.split('.')[1]?.length ?? 0,
    axis.step.split('.')[1]?.length ?? 0,
  );
  // 无法保留刻度时转为同数据表，避免近似绘制或大量 SVG 节点。
  if (
    !Number.isFinite(maximum - minimum) ||
    !Number.isFinite(intervalCount) ||
    maximum <= minimum ||
    step <= 0 ||
    intervalCount > 100 ||
    decimalPlaces > 100
  ) {
    return null;
  }
  const group = (plot.right - plot.left) / names.length;
  const barWidth = Math.min(23, (group * 0.66) / series.length);
  const xAt = (index: number) => plot.left + group * (index + 0.5);
  const yAt = (number: number) =>
    plot.bottom - ((number - minimum) / (maximum - minimum)) * (plot.bottom - plot.top);
  const baseline = yAt(Math.max(minimum, Math.min(0, maximum)));
  const ticks = Array.from({ length: intervalCount + 1 }, (_, index) => {
    const value = minimum + step * index;
    return { label: value.toFixed(decimalPlaces), y: yAt(value) };
  });
  const traces = [];
  for (const [index, item] of series.entries()) {
    const labels = values(item.column);
    if (!labels || labels.some((label) => !Number.isFinite(Number(label)))) return null;
    const offset = (index - (series.length - 1) / 2) * barWidth;
    const points = labels.map((label, categoryIndex) => ({
      x: xAt(categoryIndex) + (chart.kind === 'bar' ? offset : 0),
      y: yAt(Number(label)),
      label,
    }));
    traces.push({ ...item, points, path: points.map(({ x, y }) => `${x},${y}`).join(' ') });
  }
  return {
    categories: names.map((label, index) => ({ label, x: xAt(index) })),
    ticks,
    traces,
    barWidth,
    baseline,
  };
});

function pieSlice(start: number, end: number, large: boolean) {
  const { x, y, radius } = pieCenter;
  const position = (angle: number) =>
    `${x + radius * Math.cos(angle)} ${y + radius * Math.sin(angle)}`;
  return `M ${x} ${y} L ${position(start)} A ${radius} ${radius} 0 ${large ? 1 : 0} 1 ${position(end)} Z`;
}

const pie = computed(() => {
  const series = chart.series[0];
  const labels = series && values(series.column);
  const names = categories.value;
  if (
    chart.kind !== 'pie' ||
    !series ||
    !names?.length ||
    !labels ||
    labels.some((label) => !Number.isFinite(Number(label)))
  ) {
    return null;
  }
  let start = -Math.PI / 2;
  return labels.map((label, index) => {
    const value = Number(label);
    const end = start + (2 * Math.PI * value) / 100;
    const slice = {
      name: names[index],
      label,
      value,
      color: chart.slice_colors?.[index] ?? piePalette[index % piePalette.length] ?? series.color,
      path: pieSlice(start, end, value > 50),
    };
    start = end;
    return slice;
  });
});
</script>

<template>
  <figure :data-chart="chart.kind" :data-relationship="chart.relationship">
    <figcaption>
      {{ chart.caption }}<span v-if="chart.unit" class="unit">（{{ chart.unit }}）</span>
    </figcaption>
    <div
      v-if="cartesian || pie"
      class="plot-scroll"
      role="region"
      :aria-label="chart.caption"
      tabindex="0"
    >
      <svg role="img" :aria-label="chart.caption" :viewBox="pie ? '0 0 480 294' : '0 0 640 282'">
        <title>{{ chart.caption }}</title>
        <g v-if="cartesian">
          <text x="12" y="21" class="axis-label">{{ chart.axis?.label }}</text>
          <g v-for="tick in cartesian.ticks" :key="tick.label">
            <line :x1="plot.left" :x2="plot.right" :y1="tick.y" :y2="tick.y" class="gridline" />
            <text :x="plot.left - 10" :y="tick.y + 4" text-anchor="end" class="axis-label">
              {{ tick.label }}
            </text>
          </g>
          <text
            v-for="(category, index) in cartesian.categories"
            :key="index"
            :x="category.x"
            :y="plot.bottom + 27"
            text-anchor="middle"
            class="axis-label"
          >
            {{ category.label }}
          </text>
          <g
            v-for="(trace, traceIndex) in cartesian.traces"
            :key="trace.column"
            :fill="trace.color"
          >
            <polyline
              v-if="chart.kind === 'line'"
              :points="trace.path"
              :stroke="trace.color"
              stroke-width="2.5"
              fill="none"
            />
            <g v-for="(point, index) in trace.points" :key="index">
              <rect
                v-if="chart.kind === 'bar'"
                :x="point.x - cartesian.barWidth * 0.42"
                :y="Math.min(point.y, cartesian.baseline)"
                :width="cartesian.barWidth * 0.84"
                :height="Math.abs(cartesian.baseline - point.y)"
              />
              <circle v-else :cx="point.x" :cy="point.y" r="4" />
              <text
                :x="point.x"
                :y="point.y + (chart.kind === 'line' && traceIndex > 0 ? 18 : -8)"
                text-anchor="middle"
                class="value-label"
              >
                {{ point.label }}
              </text>
            </g>
          </g>
        </g>
        <g v-else-if="pie">
          <g v-for="(slice, index) in pie" :key="index" :fill="slice.color">
            <circle
              v-if="slice.value === 100"
              :cx="pieCenter.x"
              :cy="pieCenter.y"
              :r="pieCenter.radius"
            />
            <path v-else-if="slice.value > 0" :d="slice.path" stroke="white" stroke-width="2" />
          </g>
          <g v-if="chart.legend">
            <g v-for="(slice, index) in pie" :key="index">
              <rect x="298" :y="53 + index * 38" width="12" height="12" :fill="slice.color" />
              <text x="319" :y="63 + index * 38" class="axis-label">
                {{ slice.name }} {{ slice.label }}{{ chart.unit }}
              </text>
            </g>
          </g>
        </g>
      </svg>
    </div>
    <p v-else class="gap">当前无法按原数据绘制图表，请查阅数据表。</p>
    <ul v-if="cartesian && chart.legend" class="legend">
      <li v-for="trace in cartesian.traces" :key="trace.column">
        <span :style="{ backgroundColor: trace.color }" aria-hidden="true"></span>
        {{ trace.label }}
      </li>
    </ul>
    <details v-if="cartesian || pie">
      <summary>查看图表数据</summary>
      <ContentTable :table="table" :caption="chart.caption" />
    </details>
    <ContentTable v-else :table="table" :caption="chart.caption" />
  </figure>
</template>

<style scoped>
figure {
  margin: 0;
}

figcaption {
  margin-bottom: 0.375rem;
  font-weight: 600;
}

.unit {
  color: var(--color-muted);
  font-size: 0.9em;
  font-weight: 400;
}

.plot-scroll {
  overflow-x: auto;
  background: #f6f8f5;
}

svg {
  display: block;
  width: 100%;
  min-width: 30rem;
  font-variant-numeric: tabular-nums;
}

.gridline {
  stroke: var(--color-line);
}

.axis-label,
.value-label {
  fill: currentColor;
  font-size: 13px;
}

.value-label {
  font-size: 12px;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  margin: 0.5rem 0;
  padding: 0;
  list-style: none;
}

.legend li {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
}

.legend span {
  width: 0.625rem;
  height: 0.625rem;
}

.gap,
summary {
  color: var(--color-muted);
  font-size: 0.875rem;
}

summary {
  cursor: pointer;
}

.plot-scroll:focus-visible,
summary:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
</style>
