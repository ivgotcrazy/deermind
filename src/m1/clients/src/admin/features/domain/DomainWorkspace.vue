<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError } from '../../../shared/api/http';
import RichContent from '../../../shared/content/RichContent.vue';
import { listDomains, readDomain } from './api';
import type { DomainRow, DomainSession, DomainView, MemberKind } from './api';
import DomainCreateDialog from './DomainCreateDialog.vue';
import DomainMembers from './DomainMembers.vue';
import DomainIntakeItems from './DomainIntakeItems.vue';
import DomainInstances from './DomainInstances.vue';

const { session } = defineProps<{ session: DomainSession }>();
const lifecycle = new AbortController();
const createDialog = ref<InstanceType<typeof DomainCreateDialog>>();
const heading = ref<HTMLElement>();
const rows = ref<DomainRow[] | null>(null);
const filter = ref('');
const listError = ref('');
const selected = ref('');
const memberKind = ref<MemberKind | 'intake' | 'instances'>('kc');
const detail = ref<DomainView | null>(null);
const detailError = ref('');
let detailRead: AbortController | undefined;
let listRevision = 0;

const visible = computed(() => {
  const term = filter.value.trim().toLocaleLowerCase();
  return (rows.value ?? []).filter((row) => row.name.toLocaleLowerCase().includes(term));
});

async function loadList() {
  const revision = ++listRevision;
  listError.value = '';
  try {
    const result = await listDomains(session, lifecycle.signal);
    if (!lifecycle.signal.aborted && revision === listRevision) rows.value = result.items;
  } catch (error) {
    if (!lifecycle.signal.aborted && revision === listRevision) {
      listError.value = error instanceof ApiError ? error.message : '暂时无法读取领域列表。';
    }
  }
}

async function selectDomain(id: string) {
  detailRead?.abort();
  const read = new AbortController();
  detailRead = read;
  selected.value = id;
  detail.value = null;
  detailError.value = '';
  try {
    const result = await readDomain(id, session, read.signal);
    if (read.signal.aborted) return;
    detail.value = result;
    await nextTick();
    heading.value?.focus();
  } catch (error) {
    if (!read.signal.aborted) {
      detailError.value = error instanceof ApiError ? error.message : '暂时无法读取该领域。';
    }
  }
}

function backToList() {
  detailRead?.abort();
  selected.value = '';
}

function domainCreated(id: string) {
  void loadList();
  void selectDomain(id);
}

onMounted(loadList);

onBeforeUnmount(() => {
  lifecycle.abort();
  detailRead?.abort();
});
</script>

<template>
  <section class="admin-editor domain-workspace" aria-label="领域管理">
    <template v-if="!selected">
      <h1 class="admin-page-title">领域管理</h1>
      <div class="admin-list-toolbar">
        <label for="domain-search">领域名称</label>
        <input
          id="domain-search"
          v-model="filter"
          type="search"
          placeholder="按领域名称搜索"
          aria-label="搜索领域"
        />
        <button type="button" class="primary" @click="createDialog?.open()">
          {{ createDialog?.pending ? '核对待保存领域' : '新建领域' }}
        </button>
      </div>

      <div v-if="listError" class="feedback">
        <p role="alert">{{ listError }}</p>
        <button type="button" class="secondary" @click="loadList">重新读取</button>
      </div>
      <p v-else-if="!rows" class="feedback" role="status">正在读取领域…</p>
      <p v-else-if="!visible.length" class="feedback">
        {{ rows.length ? '没有找到匹配的领域。' : '还没有领域。' }}
      </p>
      <table v-else class="admin-data-table" aria-label="领域列表">
        <thead>
          <tr>
            <th>领域名称</th>
            <th>版本</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in visible" :key="row.object_ref.object_id">
            <td>
              <button type="button" @click="selectDomain(row.object_ref.object_id)">
                {{ row.name }}
              </button>
            </td>
            <td>v{{ row.object_ref.version }}</td>
          </tr>
        </tbody>
      </table>
    </template>
    <template v-else>
      <p class="admin-crumb">
        <button type="button" aria-label="返回领域列表" @click="backToList">领域管理</button
        ><template v-if="detail"> / {{ detail.content.name }}</template>
      </p>
      <div v-if="detail" class="domain-detail">
        <h1 ref="heading" class="admin-page-title" tabindex="-1">{{ detail.content.name }}</h1>
        <dl class="domain-meta">
          <dt>版本</dt>
          <dd>v{{ detail.object_ref.version }}</dd>
          <dt>领域编号</dt>
          <dd>{{ detail.object_ref.object_id }}</dd>
        </dl>
        <section v-if="detail.content.coverage" class="domain-reading" data-rich-field="coverage">
          <h3>范围</h3>
          <RichContent :content="detail.content.coverage" />
        </section>
        <section
          v-if="detail.content.description"
          class="domain-reading"
          data-rich-field="description"
        >
          <h3>说明</h3>
          <RichContent :content="detail.content.description" />
        </section>
        <nav class="editor-tabs" aria-label="领域对象">
          <button
            type="button"
            class="secondary"
            :aria-pressed="memberKind === 'kc'"
            @click="memberKind = 'kc'"
          >
            知识成分
          </button>
          <button
            type="button"
            class="secondary"
            :aria-pressed="memberKind === 'task'"
            @click="memberKind = 'task'"
          >
            任务
          </button>
          <button
            type="button"
            class="secondary"
            :aria-pressed="memberKind === 'solution'"
            @click="memberKind = 'solution'"
          >
            方法
          </button>
          <button
            type="button"
            class="secondary"
            :aria-pressed="memberKind === 'intake'"
            @click="memberKind = 'intake'"
          >
            待入库内容
          </button>
          <button
            type="button"
            class="secondary"
            :aria-pressed="memberKind === 'instances'"
            @click="memberKind = 'instances'"
          >
            题目实例
          </button>
        </nav>
        <DomainIntakeItems
          v-if="memberKind === 'intake'"
          :key="selected"
          :domain-id="selected"
          :session="session"
        />
        <DomainInstances
          v-else-if="memberKind === 'instances'"
          :key="selected"
          :domain-id="selected"
          :session="session"
        />
        <DomainMembers
          v-else
          :key="`${selected}:${memberKind}`"
          :kind="memberKind"
          :domain-id="selected"
          :session="session"
        />
      </div>
      <div v-else-if="detailError" class="feedback">
        <p role="alert">{{ detailError }}</p>
        <button type="button" class="secondary" @click="selectDomain(selected)">重新读取</button>
      </div>
      <p v-else class="feedback" role="status">正在读取领域…</p>
    </template>

    <DomainCreateDialog ref="createDialog" :session="session" @saved="domainCreated" />
  </section>
</template>

<style scoped>
.domain-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  margin: 8px 0 20px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.domain-meta dd {
  margin: 0 16px 0 0;
  overflow-wrap: anywhere;
}
.domain-reading {
  background: white;
  padding: 14px 20px;
  border: 1px solid var(--el-border-color);
}
.domain-reading + .domain-reading {
  border-top: 0;
}
.domain-detail > nav {
  margin: 16px 0;
}
</style>
