<script setup lang="ts">
import { ref } from 'vue'
import { parentNotes } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const active = ref<'teacher' | 'observation' | 'material' | null>(null)
const teacherText = ref(parentNotes.teacher)
const obsText = ref(parentNotes.observation)
const saved = ref<Record<string, boolean>>({ teacher: true, observation: true })
const uploaded = ref<string[]>([...parentNotes.materials])

const cards = [
  { id: 'teacher' as const, icon: 'doc', title: '老师评语', desc: '孩子不可见，小鹿会参考', placeholder: '例如：老师说女儿应用题常漏条件…' },
  { id: 'observation' as const, icon: 'sparkles', title: '家长观察', desc: '你对孩子学习状态的感受', placeholder: '例如：她口算不错，但一到大题就慌…' },
  { id: 'material' as const, icon: 'upload', title: '补充教材', desc: '辅导班讲义 / 试卷 PDF', placeholder: '' },
]

function save(id: string) {
  saved.value[id] = true
  active.value = null
}
function mockUpload() {
  uploaded.value.push('新增讲义.pdf')
  active.value = null
}
</script>

<template>
  <div class="input">
    <h2 class="title">家长录入</h2>
    <p class="sub">补充系统不知道的信息，让小鹿更懂孩子（不录入也不影响使用）</p>

    <div class="list">
      <section v-for="c in cards" :key="c.id" class="card entry">
        <button class="entry-head" @click="active = active === c.id ? null : c.id">
          <span class="ico"><Icon :name="c.icon" :size="20" /></span>
          <span class="txt">
            <span class="t">{{ c.title }}</span>
            <span class="d">{{ c.desc }}</span>
          </span>
          <span v-if="saved[c.id] || (c.id === 'material' && uploaded.length)" class="chip">已录入</span>
        </button>

        <div v-if="active === c.id" class="form">
          <template v-if="c.id === 'teacher'">
            <textarea v-model="teacherText" class="input" rows="3" :placeholder="c.placeholder"></textarea>
            <button class="btn btn-primary btn-block" @click="save('teacher')">保存评语</button>
          </template>
          <template v-else-if="c.id === 'observation'">
            <textarea v-model="obsText" class="input" rows="3" :placeholder="c.placeholder"></textarea>
            <button class="btn btn-primary btn-block" @click="save('observation')">保存观察</button>
          </template>
          <template v-else>
            <button class="upload" @click="mockUpload"><Icon name="upload" :size="16" /> 选择 PDF / 图片上传</button>
            <div v-for="u in uploaded" :key="u" class="up"><Icon name="doc" :size="14" /> {{ u }}</div>
          </template>
        </div>
      </section>
    </div>

    <p class="tip"><Icon name="sparkles" :size="14" /> 录入内容仅家长可见，孩子端无法查看</p>
  </div>
</template>

<style scoped>
.input {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 20px;
}
.sub {
  margin: -6px 0 0;
  font-size: 13px;
  opacity: 0.7;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.entry-head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  border: none;
  background: transparent;
  padding: 0;
  font-family: inherit;
  text-align: left;
}
.ico {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.txt {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.txt .t {
  font-weight: 800;
  font-size: 15px;
}
.txt .d {
  font-size: 12px;
  opacity: 0.65;
}
.form {
  margin-top: 12px;
  border-top: 1px dashed var(--color-line);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.upload {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border: 2px dashed var(--color-primary);
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
}
.up {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 12px;
  color: var(--color-primary);
}
</style>
