<script setup lang="ts">
import { computed, ref } from 'vue';
import content from '../../../mvp_foundation/content/fractions-application/package.json';
import evaluation from '../../../mvp_foundation/evaluation/fractions-content-cases.json';
import SourceReferenceReview from './SourceReferenceReview.vue';

const sections = [
  { id: 'coverage', label: '章节覆盖' }, { id: 'targets', label: '学习要求' },
  { id: 'problems', label: '问题与解法' }, { id: 'knowledge', label: '知识定义' },
  { id: 'examples', label: '原创题与参考' }, { id: 'source', label: '教材题与图示' }, { id: 'evaluation', label: '评价案例' },
];
const section = ref('coverage');
const selectedProblem = ref(content.problem_templates[0].id);
const problem = computed(() => content.problem_templates.find(p => p.id === selectedProblem.value)!);
const solutions = computed(() => content.solution_templates.filter(s => problem.value.solution_refs.includes(`${s.id}@${s.version}`)));
const knowledgeName = (reference: string) => content.knowledge_components.find(k => `${k.id}@${k.version}` === reference)?.name || reference;
const templateName = (reference: string) => content.problem_templates.find(p => `${p.id}@${p.version}` === reference)?.name || reference;
const sourceRows = computed(() => content.material.inventory.filter(row => row.template_refs.includes(`${problem.value.id}@1`)));
</script>

<template>
  <details class="f-card content-review" data-testid="actual-content-review">
    <summary>查看“分数的应用”实际内容草案</summary>
    <div class="f-content-heading f-spaced">
      <div><span class="f-eyebrow">北师大版 · 六年级上册 · 第四单元</span><h2>分数的应用</h2></div>
      <span class="f-tag">v{{ content.version }} · 待审核</span>
    </div>
    <p>书内 49–56 页已逐页阅读。这里查看本章的内容候选；尚未发布、采用，也没有生成学生的掌握判断。</p>
    <p class="f-muted">{{ content.problem_templates.length }} 类问题 · {{ content.solution_templates.length }} 种方法 · {{ content.knowledge_components.length }} 个 KC · {{ content.target.requirements.length }} 项候选学习要求。数量只描述这份草案。</p>
    <p><a :href="content.source.url" target="_blank" rel="noopener noreferrer">打开教材来源</a> · 修订日期 {{ content.updated_on }}</p>
    <nav class="content-review-nav" aria-label="内容草案分类">
      <button v-for="item in sections" :key="item.id" class="f-secondary" :aria-pressed="section===item.id" @click="section=item.id">{{ item.label }}</button>
    </nav>

    <section v-if="section==='coverage'" aria-label="章节覆盖与缺口">
      <h3>先看这章覆盖什么</h3>
      <article v-for="item in content.material.sections" :key="item.key" class="f-diff">
        <b>{{ item.title }} · {{ item.pages[0] }}–{{ item.pages[1] }} 页</b>
        <ul><li v-for="row in content.material.inventory.filter(r=>r.section===item.key)" :key="row.key">
          <b>{{ row.location }}</b>：{{ row.summary }}
          <p v-if="row.template_refs.length" class="f-muted">候选关联：{{ row.template_refs.map(templateName).join('；') }}</p>
        </li></ul>
      </article>
      <h3>尚待处理</h3>
      <ul><li v-for="item in content.open_items" :key="item.id">{{ item.item }}<p class="f-muted">影响：{{ item.blocks }}</p></li></ul>
    </section>

    <section v-else-if="section==='targets'" aria-label="候选学习要求">
      <h3>什么表现才支持相应要求</h3><p>{{ content.target.assessment_boundary }}</p>
      <article v-for="item in content.target.requirements" :key="item.id" class="f-diff">
        <h4>{{ item.label }}</h4><p>{{ item.quality }}</p>
        <p class="f-muted">{{ item.id }} · {{ item.claim_ref }}</p>
        <details><summary>查看判断依据与限制</summary>
          <template v-for="claim in content.claims.filter(c=>`${c.id}@1`===item.claim_ref)" :key="claim.id">
            <p><b>可支持：</b>{{ claim.supporting }}</p><p><b>反向表现：</b>{{ claim.counterevidence }}</p><p><b>不足以判断：</b>{{ claim.insufficient }}</p>
          </template>
          <p>内容位置：{{ item.source_keys.join('、') }}</p>
        </details>
      </article>
    </section>

    <section v-else-if="section==='problems'" aria-label="问题模板与方法">
      <label class="f-field">选择问题模板<select v-model="selectedProblem"><option v-for="item in content.problem_templates" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <h3>{{ problem.name }}</h3><p>{{ problem.responsibility }}</p>
      <p class="f-muted">{{ problem.id }}@{{ problem.version }}</p>
      <h4>参数与适用条件</h4>
      <dl class="content-parameters"><template v-for="(value,key) in problem.parameters" :key="key"><dt>{{ key }}</dt><dd>{{ Array.isArray(value)?value.join('、'):value }}</dd></template></dl>
      <ul><li v-for="condition in problem.constraints" :key="condition">{{ condition }}</li></ul>
      <p><b>允许观察的变化：</b>{{ problem.variation_axes.join('；') }}</p><p><b>边界：</b>{{ problem.limits }}</p>
      <h4>可用方法候选</h4>
      <article v-for="solution in solutions" :key="solution.id" class="f-diff">
        <b>{{ solution.name }}</b><p>{{ solution.condition }}</p><ol><li v-for="step in solution.steps" :key="step">{{ step }}</li></ol>
        <p class="f-muted">知识依据：{{ solution.knowledge_refs.map(knowledgeName).join('；') }}</p>
        <details v-if="solution.subproblem_refs.length"><summary>子问题及参数绑定</summary><p v-for="(sub,i) in solution.subproblem_refs" :key="i">{{ sub.ref }}：{{ sub.binding }}</p></details>
      </article>
      <p>本章候选映射：{{ sourceRows.map(r=>`${r.pages.join('、')} 页 · ${r.location}`).join('；') }}</p>
    </section>

    <section v-else-if="section==='knowledge'" aria-label="知识成分候选">
      <article v-for="item in content.knowledge_components" :key="item.id" class="f-diff">
        <h3>{{ item.name }}</h3><p>{{ item.definition }}</p><p><b>适用边界：</b>{{ item.boundary }}</p>
        <p><b>可观察表现：</b>{{ item.observable }}</p><p><b>反例：</b>{{ item.counterexample }}</p><p class="f-muted">{{ item.id }}@{{ item.version }}</p>
      </article>
    </section>

    <section v-else-if="section==='examples'" aria-label="原创内容参考">
      <p>这些题目是依据本章结构编制的原创候选，已经用于开发，不能冒充未见过的正式测量题。</p>
      <article v-for="item in content.original_problems" :key="item.id" class="f-diff">
        <h3>{{ item.id }} · {{ templateName(item.template_ref) }}</h3><p>{{ item.prompt }}</p>
        <details><summary>查看参考解法与用途</summary><ol><li v-for="method in item.reference.methods" :key="method">{{ method }}</li></ol><p>{{ item.reference.meaning }}</p><p class="f-muted">{{ item.use }}</p></details>
      </article>
    </section>

    <SourceReferenceReview v-else-if="section==='source'" />

    <section v-else aria-label="评价案例参考">
      <p>共 {{ evaluation.cases.length }} 个开发案例，尚待独立复核，也尚未运行真实模型。</p>
      <article v-for="item in evaluation.cases" :key="item.id" class="f-diff">
        <h3>{{ item.id }} · {{ item.title }}</h3><p><b>条件：</b>{{ item.precondition }}</p>
        <ul><li v-for="input in item.input" :key="input">{{ input }}</li></ul>
        <details><summary>查看允许结论与错误结论</summary><h4>应如何处理</h4><ul><li v-for="value in item.expected" :key="value">{{ value }}</li></ul><h4>不能这样判断</h4><ul><li v-for="value in item.forbidden" :key="value">{{ value }}</li></ul><p class="f-muted">{{ item.reference_basis }}</p></details>
      </article>
    </section>
  </details>
</template>

<style scoped>
.content-review{overflow-wrap:anywhere}.content-review>summary{font-weight:700;cursor:pointer;padding:6px 0}
.content-review-nav{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.content-review-nav button[aria-pressed="true"]{background:#285c49;color:white;border-color:#285c49}
.content-review h3{margin:22px 0 10px}.content-review h4{margin:16px 0 8px}.content-review li{margin:8px 0}.content-review a{color:#205f4c;text-decoration:underline}
.content-parameters{display:grid;grid-template-columns:minmax(90px,140px) 1fr;gap:8px 16px}.content-parameters dt{font-weight:600}.content-parameters dd{margin:0}
@media(max-width:560px){.content-parameters{grid-template-columns:1fr;gap:5px}.content-parameters dd{margin-bottom:8px}.content-review-nav button{flex:1 1 42%}}
</style>
