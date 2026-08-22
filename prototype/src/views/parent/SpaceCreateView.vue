<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '@/components/Icon.vue'

const router = useRouter()

const name = ref('')
const type = ref<'school' | 'tutoring'>('school')
const semester = ref('2026 秋季学期')
const selectedBooks = ref<string[]>(['人教版 数学 六年级上册'])
const uploaded = ref<string[]>([])
const progress = ref('第一单元 分数乘法')
const created = ref(false)

const systemBooks = [
  '人教版 数学 六年级上册',
  '北师大版 数学 六年级上册',
  '学而思 思维训练 六年级',
]

function toggleBook(b: string) {
  const i = selectedBooks.value.indexOf(b)
  if (i >= 0) selectedBooks.value.splice(i, 1)
  else selectedBooks.value.push(b)
}
function mockUpload() {
  uploaded.value.push('校内同步提升讲义.pdf')
}
function create() {
  created.value = true
}
</script>

<template>
  <div class="create">
    <h2 class="title">新建学习空间</h2>
    <p class="sub">一次性配置，之后孩子端就能在空间内学习</p>

    <section class="card form">
      <label class="field">
        <span>空间名称</span>
        <input v-model="name" class="input" placeholder="如：学校 · 六年级上册数学" />
      </label>

      <label class="field">
        <span>类型</span>
        <div class="seg">
          <button :class="{ on: type === 'school' }" @click="type = 'school'">学校</button>
          <button :class="{ on: type === 'tutoring' }" @click="type = 'tutoring'">辅导班</button>
        </div>
      </label>

      <label class="field">
        <span>学期</span>
        <select v-model="semester" class="input">
          <option>2026 秋季学期</option>
          <option>2026 春季学期</option>
          <option>2027 秋季学期</option>
        </select>
      </label>

      <div class="field">
        <span>绑定教材（可多个）</span>
        <div class="books">
          <button
            v-for="b in systemBooks"
            :key="b"
            class="book"
            :class="{ on: selectedBooks.includes(b) }"
            @click="toggleBook(b)"
          >
            <Icon v-if="selectedBooks.includes(b)" name="check" :size="14" /> {{ b }}
          </button>
        </div>
        <button class="upload" @click="mockUpload"><Icon name="upload" :size="16" /> 上传教材（PDF/图片）</button>
        <div v-for="u in uploaded" :key="u" class="uploaded"><Icon name="doc" :size="14" /> {{ u }}</div>
      </div>

      <label class="field">
        <span>当前进度（不确定可留空，小鹿会摸底）</span>
        <select v-model="progress" class="input">
          <option>第一单元 分数乘法</option>
          <option>第二单元 位置与方向（二）</option>
          <option>第三单元 分数除法</option>
        </select>
      </label>

      <button class="btn btn-primary btn-block" @click="create">创建学习空间</button>
    </section>

    <!-- 创建成功 -->
    <section v-if="created" class="card success">
      <Icon name="check" :size="24" />
      <div>
        <div class="ok">创建成功</div>
        <p>「{{ name || '新空间' }}」已建立。孩子端将出现该空间入口，小鹿会在其内进行辅导。</p>
      </div>
      <button class="btn btn-indigo btn-block" @click="router.push('/parent/spaces')">返回空间列表</button>
    </section>
  </div>
</template>

<style scoped>
.create {
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
  opacity: 0.75;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field > span {
  font-size: 13px;
  font-weight: 700;
  opacity: 0.85;
}
.seg {
  display: flex;
  gap: 8px;
}
.seg button {
  flex: 1;
  padding: 10px;
  border: 2px solid var(--color-line);
  border-radius: 12px;
  background: #fff;
  font-weight: 700;
}
.seg button.on {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.books {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.book {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border: 2px solid var(--color-line);
  border-radius: 12px;
  background: #fff;
  font-size: 14px;
  text-align: left;
  transition: all var(--ease-soft);
}
.book.on {
  border-color: var(--color-cta);
  background: var(--color-cta-soft);
  color: #15803d;
}
.upload {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  border: 2px dashed var(--color-primary);
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
}
.uploaded {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text);
}
.success {
  border: 3px solid var(--color-cta);
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  color: #15803d;
}
.ok {
  font-weight: 800;
  font-size: 16px;
}
.success p {
  margin: 0;
  font-size: 13px;
  color: var(--color-text);
  line-height: 1.6;
}
</style>
