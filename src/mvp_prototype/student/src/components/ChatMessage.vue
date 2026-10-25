<script setup lang="ts">
import type { ChatMessage } from '../types';

defineProps<{ message: ChatMessage; live?: boolean; busy?: boolean; activeCheck?: string | null;
  answerDrafts?: Record<string,string> }>();
const emit = defineEmits<{
  answerDraft: [id: string, value: string];
  questionAction: [kind: 'start_check' | 'answer' | 'help', id: string];
}>();

function phaseLabel(phase?: string): string {
  const map: Record<string, string> = { concept: '概念讲解', example: '例题演示', practice: '练习', summary: '总结' };
  return phase ? map[phase] || phase : '';
}
function maxVal(rows: { value: number }[]): number { return Math.max(...rows.map(r => r.value), 1); }
function renderText(text: string): string {
  const escaped = text.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
  return escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}
</script>

<template>
  <div class="message-row" :class="{ user: message.role === 'user' }">
    <div class="avatar"><span v-if="message.role === 'user'">你</span><span v-else>🦌</span></div>
    <div class="message-body">
      <div class="message-meta">
        <span class="sender">{{ message.role === 'user' ? '你' : 'DeerMind' }}</span>
        <span v-if="message.phase" class="phase-tag">{{ phaseLabel(message.phase) }}</span>
      </div>
      <div class="message-content">
        <template v-for="(block, i) in message.blocks" :key="i">
          <div v-if="block.type === 'phase-marker'" class="block phase-marker">
            <span>📖</span><span>{{ block.label }}</span>
          </div>
          <div v-else-if="block.type === 'text'" class="block text" v-html="renderText(block.text)"></div>
          <div v-else-if="block.type === 'formula'" class="block formula"><pre>{{ block.text }}</pre></div>
          <figure v-else-if="block.type === 'bars'" class="block bars">
            <figcaption>{{ block.caption }}</figcaption>
            <div v-for="row in block.rows" :key="row.label" class="bar-row">
              <span class="bar-label">{{ row.label }}</span>
              <div class="bar-track"><div class="bar-fill" :style="{ width: (row.value / maxVal(block.rows) * 100) + '%' }"></div></div>
              <span class="bar-value">{{ row.value }}</span>
            </div>
          </figure>
          <div v-else-if="block.type === 'question'" class="block question">
            <span class="question-tag">{{ block.mode === 'check' ? '即时检测' : '随堂练习' }}</span>
            <p class="question-prompt">{{ block.prompt }}</p>
            <template v-if="live">
              <div v-if="block.mode === 'check' && block.state === 'offered'" class="question-actions">
                <button class="btn-primary" :disabled="busy || !!activeCheck"
                  @click="emit('questionAction', 'start_check', block.id)">开始检测</button>
              </div>
              <div v-else-if="block.state === 'active' || (block.mode === 'practice' && block.state === 'offered')" class="question-actions">
                <textarea :value="answerDrafts?.[block.id] || ''" placeholder="写下你的答案和思路..." rows="2"
                  :disabled="busy" @input="emit('answerDraft', block.id, ($event.target as HTMLTextAreaElement).value)"></textarea>
                <button class="btn-primary" :disabled="busy || !(answerDrafts?.[block.id]?.trim())"
                  @click="emit('questionAction', 'answer', block.id)">提交答案</button>
                <button v-if="block.state === 'active' && activeCheck === block.id" class="btn-secondary" :disabled="busy"
                  @click="emit('questionAction', 'help', block.id)">求助</button>
              </div>
              <div v-else-if="block.state === 'answered'" class="question-result">
                <span>已提交</span><p>{{ block.answer }}</p>
              </div>
              <p v-else-if="block.state === 'helped'" class="question-result">已结束检测，转入讲解。</p>
              <p v-else-if="block.state === 'skipped'" class="question-result">本题已结束，未提交答案。</p>
            </template>
            <div v-else-if="block.state === 'offered'" class="question-actions">
              <textarea placeholder="写下你的答案和思路..." rows="2"></textarea>
              <button class="btn-primary">提交答案</button>
            </div>
          </div>
          <div v-else-if="block.type === 'progress'" class="block progress">
            <span class="progress-label">{{ block.label }}</span>
            <div class="progress-track"><div class="progress-fill" :style="{ width: (block.current / block.total * 100) + '%' }"></div></div>
            <span class="progress-value">{{ block.current }}/{{ block.total }}</span>
          </div>
          <div v-else-if="block.type === 'summary'" class="block summary">
            <h4>{{ block.title }}</h4>
            <ul><li v-for="(p, i) in block.points" :key="i">{{ p }}</li></ul>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.btn-secondary { background: white; color: #2d6a4f; border: 1px solid #c8d6e0; border-radius: 6px; padding: 7px 18px; margin-left: 8px; font: inherit; font-size: 13px; cursor: pointer; }
.question-actions button:disabled { opacity: .5; cursor: default; }
.question-result { color: #5a6b7a; font-size: 12px; line-height: 1.7; }
.question-result p { margin: 4px 0 0; white-space: pre-wrap; color: #2c3e50; }
.message-row { display: flex; gap: 12px; margin-bottom: 24px; animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.message-row.user { flex-direction: row-reverse; }
.avatar { width: 36px; height: 36px; border-radius: 50%; background: #2d5a4a; color: #e8f0ec; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; flex-shrink: 0; }
.message-row.user .avatar { background: #4a6fa5; }
.message-body { max-width: 78%; min-width: 0; }
.message-row.user .message-body { text-align: right; }
.message-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 11px; color: #8a99a8; }
.message-row.user .message-meta { justify-content: flex-end; }
.sender { font-weight: 600; color: #5a6b7a; }
.phase-tag { background: #e0f0e8; color: #2d6a4f; padding: 1px 8px; border-radius: 10px; font-size: 10px; font-weight: 500; }
.message-content { text-align: left; }
.block { margin-bottom: 10px; }
.block:last-child { margin-bottom: 0; }
.phase-marker { display: flex; align-items: center; gap: 8px; background: linear-gradient(90deg, #e8f5ee 0%, transparent 100%); padding: 8px 14px; border-radius: 8px; font-size: 13px; font-weight: 600; color: #2d6a4f; border-left: 3px solid #40916c; }
.text { font-size: 14px; line-height: 1.8; color: #2c3e50; }
.text :deep(strong) { color: #1a3a2e; background: #fff3cd; padding: 1px 4px; border-radius: 3px; }
.formula { background: #f5f7fa; border-left: 3px solid #7b9acc; padding: 12px 16px; border-radius: 0 8px 8px 0; overflow-x: auto; }
.formula pre { margin: 0; font-family: Consolas, Monaco, monospace; font-size: 14px; line-height: 1.7; color: #2c3e50; white-space: pre-wrap; }
.bars { background: #fafbfc; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px 16px; margin: 0; }
.bars figcaption { font-size: 12px; color: #6b7c8d; margin-bottom: 12px; font-weight: 500; }
.bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.bar-row:last-child { margin-bottom: 0; }
.bar-label { width: 40px; font-size: 12px; color: #5a6b7a; flex-shrink: 0; }
.bar-track { flex: 1; height: 18px; background: #eef2f5; border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, #52b788, #40916c); border-radius: 4px; transition: width 0.5s; }
.bar-value { width: 30px; font-size: 12px; font-weight: 600; color: #2c3e50; text-align: right; }
.question { background: #fff; border: 1px solid #d4e4dc; border-radius: 10px; padding: 14px 16px; }
.question-tag { display: inline-block; background: #d4edda; color: #155724; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-bottom: 8px; }
.question-prompt { font-size: 14px; line-height: 1.7; color: #2c3e50; margin: 0 0 12px 0; }
.question-actions textarea { width: 100%; border: 1px solid #d0d7de; border-radius: 6px; padding: 8px 10px; font-size: 13px; resize: vertical; margin-bottom: 8px; box-sizing: border-box; font-family: inherit; }
.question-actions textarea:focus { outline: none; border-color: #40916c; box-shadow: 0 0 0 2px rgba(64,145,108,0.15); }
.btn-primary { background: #2d6a4f; color: white; border: none; padding: 7px 18px; border-radius: 6px; font-size: 13px; cursor: pointer; font-weight: 500; font-family: inherit; }
.btn-primary:hover { background: #245440; }
.progress { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
.progress-label { font-size: 12px; color: #5a6b7a; width: 80px; }
.progress-track { flex: 1; height: 8px; background: #eef2f5; border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: #40916c; border-radius: 4px; }
.progress-value { font-size: 12px; font-weight: 600; color: #2c3e50; }
.summary { background: #f0f7f3; border-radius: 10px; padding: 12px 16px; }
.summary h4 { margin: 0 0 8px 0; font-size: 14px; color: #1b4332; }
.summary ul { margin: 0; padding-left: 18px; }
.summary li { font-size: 13px; line-height: 1.7; color: #2c3e50; margin-bottom: 4px; }
@media (max-width: 700px) {
  .message-body { max-width: 85%; }
  .text { font-size: 13px; }
  .avatar { width: 30px; height: 30px; font-size: 11px; }
}
</style>
