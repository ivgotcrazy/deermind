<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import references from '../../../mvp_foundation/content/fractions-application/source-references.json';

const pages = [...new Set(references.rows.map(r => r.page))];
const pageNumber = ref(51);
const pageRows = computed(() => references.rows.filter(r => r.page === pageNumber.value));
const selected = ref(pageRows.value[0]!.id);
watch(pageNumber, () => { selected.value = pageRows.value[0]!.id; });
const row = computed(() => pageRows.value.find(r => r.id === selected.value) || pageRows.value[0]!);
const figure = computed(() => references.diagrams.find(d => d.id === row.value.diagram_ref));
const maximum = computed(() => Math.max(...(figure.value?.rows.map(r => Number(r.value)) || [1])));
const width = (value: string) => 360 * Number(value) / maximum.value;
const originLabel = (origin: string) => ({ given: '已知', derived: '推导', result: '所求' }[origin] || origin);
const basis = computed(() => row.value.reference_basis.startsWith('worked_in_source')
  ? '原书提供了相关推导；本参考由作者另行核算。'
  : row.value.reference_basis.startsWith('author_rubric') ? '开放性整理参考，不设唯一答案。'
  : row.value.reference_basis.startsWith('author_exploration') ? '探索性解释参考，尚未映射本包正式目标。'
  : '作者根据原题条件推导；不是出版社答案册。');
</script>

<template>
  <section class="source-reference" aria-label="教材原题与图示参考" data-testid="source-reference-review">
    <h3>从教材位置核对题目与依据</h3>
    <p>51 条定位参考覆盖书内 49–56 页。按页与小题查找；同题的画图、计算和说理要求分别说明，不把定位条数当成独立检测题数。</p>
    <p class="f-muted">这些是作者参考，尚待独立复核；没有运行识别或评价模型。原题历史数据只作为题内条件。</p>
    <div class="source-selectors">
      <label class="f-field">教材页码<select v-model.number="pageNumber"><option v-for="page in pages" :key="page" :value="page">第 {{ page }} 页</option></select></label>
      <label class="f-field">题目位置<select v-model="selected"><option v-for="item in pageRows" :key="item.id" :value="item.id">{{ item.location }}</option></select></label>
    </div>
    <article :key="row.id" class="f-diff">
      <h4>第 {{ row.page }} 页 · {{ row.location }}</h4>
      <p class="f-muted">{{ row.id }} · {{ row.source_key }}</p>
      <p><b>题意与条件摘要：</b>{{ row.givens }}</p>
      <h4>需要分别核对的表现</h4>
      <ul><li v-for="requirement in row.required" :key="requirement">{{ requirement }}</li></ul>
      <p><b>候选映射：</b>{{ row.template_refs.length ? row.template_refs.join('、') : '本包未设正式评价映射；不等于超纲或禁止回答。' }}</p>
      <details>
        <summary>展开解答与关系图</summary>
        <p><b>参考结果：</b>{{ row.reference_answer }}</p>
        <ol><li v-for="step in row.reasoning" :key="step">{{ step }}</li></ol>
        <p class="f-muted">{{ basis }}</p>
        <figure v-if="figure" class="source-figure">
          <figcaption><b>{{ figure.title }}</b><p>作者重绘的解答参考，含推导值；不能直接用作无提示检测题。</p></figcaption>
          <p class="source-pan-hint f-muted">关系图可横向查看；文字说明在图下方。</p>
          <div class="source-svg-scroll" tabindex="0" role="region" aria-label="数量关系参考图，可横向查看">
            <svg :viewBox="`0 0 640 ${figure.rows.length * 84 + 25}`" role="img" :aria-labelledby="`${figure.id}-title ${figure.id}-desc`">
              <title :id="`${figure.id}-title`">{{ figure.title }}</title>
              <desc :id="`${figure.id}-desc`">同一数量尺度的等分线段图。{{ figure.rows.map(r => `${r.label} ${r.value} ${figure!.unit}（${originLabel(r.origin)}）`).join('；') }}</desc>
              <g v-for="(bar,i) in figure.rows" :key="bar.label" :transform="`translate(0,${i * 84 + 18})`">
                <text x="10" y="22">{{ bar.label }}</text>
                <rect x="150" y="0" :width="width(bar.value)" height="32" :class="bar.origin === 'given' ? 'source-bar-given' : 'source-bar-derived'" />
                <line v-for="part in bar.parts - 1" :key="part" :x1="150 + width(bar.value) * part / bar.parts" :x2="150 + width(bar.value) * part / bar.parts" y1="0" y2="32" class="source-part" />
                <text :x="162 + width(bar.value)" y="14">{{ bar.value }} {{ figure.unit }}</text>
                <text :x="162 + width(bar.value)" y="37" class="source-origin">{{ originLabel(bar.origin) }}</text>
                <line v-if="i > 0" :x1="150 + width(bar.value)" :x2="150 + width(bar.value)" y1="-52" y2="0" class="source-alignment" />
              </g>
            </svg>
          </div>
          <ul><li v-for="relation in figure.relations" :key="`${relation.from}-${relation.to}`">{{ figure.rows[relation.to]!.label }}是{{ figure.rows[relation.from]!.label }}的 {{ relation.ratio }}。<span class="f-muted">依据：{{ relation.origin }}。</span></li></ul>
          <ul><li v-for="note in figure.notes" :key="note">{{ note }}</li></ul>
        </figure>
      </details>
    </article>
  </section>
</template>

<style scoped>
.source-selectors{display:grid;grid-template-columns:150px minmax(0,1fr);gap:14px;margin:20px 0}.source-selectors select{width:100%;min-width:0}
.source-reference summary{cursor:pointer;font-weight:600;padding:10px 0}.source-figure{margin:20px 0 0;padding:18px;background:#fff;border:1px solid #dce5df;border-radius:12px}
.source-figure figcaption p{font-size:14px;color:#6a5132}.source-svg-scroll{overflow-x:auto;max-width:100%;margin-top:16px}.source-svg-scroll svg{display:block;width:100%;min-width:600px;max-width:740px;font:16px 'Microsoft YaHei',sans-serif;color:#193b32}
.source-bar-given{fill:#dbe9e1;stroke:#315d4e;stroke-width:1.5}.source-bar-derived{fill:#f6f4e6;stroke:#315d4e;stroke-width:1.5;stroke-dasharray:5 3}.source-part{stroke:#315d4e;stroke-width:1}.source-alignment{stroke:#667e72;stroke-dasharray:3 3}.source-origin{font-size:13px;fill:#5c6e64}.source-pan-hint{display:none}
@media(max-width:680px){.source-selectors{grid-template-columns:1fr}.source-figure{padding:12px}.source-pan-hint{display:block}}
</style>
