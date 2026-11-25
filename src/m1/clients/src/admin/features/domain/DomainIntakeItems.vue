<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { get } from '../../../shared/api/http';
import type { DomainSession } from './api';
import DomainDefinitionExtraction from './DomainDefinitionExtraction.vue';
import DomainIntakeActions from './DomainIntakeActions.vue';

type IntakeView = components['schemas']['IntakeView'];
const { domainId, session } = defineProps<{ domainId: string; session: DomainSession }>();
const lifecycle = new AbortController();
const items = ref<IntakeView[]>();
const cursor = ref<string | null>(null);
const error = ref('');
const loading = ref(false);
const labels = { kc: '知识成分', task_instance: '题目', reference: '题内参考' };

async function load(next?: string) {
  if (loading.value) return;
  loading.value = true;
  error.value = '';
  try {
    const page = await get('/api/m1/domains/{domain_id}/intake-items', {
      session,
      signal: lifecycle.signal,
      params: { domain_id: domainId },
      query: { cursor: next },
    });
    items.value = next ? [...(items.value ?? []), ...page.items] : page.items;
    cursor.value = page.next_cursor;
  } catch (cause) {
    if (!lifecycle.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '暂时无法读取待入库内容。';
  } finally {
    loading.value = false;
  }
}

onMounted(() => void load());
onBeforeUnmount(() => lifecycle.abort());
</script>

<template>
  <section class="editor-panel" aria-label="待入库内容">
    <header class="editor-row intake-heading">
      <h3>待入库内容</h3>
      <button type="button" class="secondary" :disabled="loading" @click="load()">刷新</button>
    </header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">正在读取待入库内容…</p>
    <p v-else-if="items && !items.length">暂无待入库内容。</p>
    <table v-if="items?.length" class="admin-data-table intake-table">
      <thead>
        <tr>
          <th scope="col">内容</th>
          <th scope="col">类型</th>
          <th scope="col">状态</th>
          <th scope="col">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.item_ref.id">
          <th scope="row">{{ item.title }}</th>
          <td>{{ labels[item.kind] }}</td>
          <td><span class="intake-status">待入库</span></td>
          <td>
            <div class="admin-row-actions">
              <DomainIntakeActions
                :item="item"
                :domain-id="domainId"
                :session="session"
                @saved="load()"
              >
                <DomainDefinitionExtraction
                  v-if="item.kind !== 'kc'"
                  :item="item"
                  :domain-id="domainId"
                  :session="session"
                />
              </DomainIntakeActions>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <button v-if="cursor" type="button" class="secondary" :disabled="loading" @click="load(cursor)">
      加载更多
    </button>
  </section>
</template>

<style scoped>
.intake-heading {
  margin-bottom: 16px;
}
.intake-table thead th:first-child {
  width: 46%;
}
.intake-table thead th:nth-child(2),
.intake-table thead th:nth-child(3) {
  width: 12%;
}
.intake-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  background: #fff4df;
  color: #815019;
  font-size: 13px;
  white-space: nowrap;
}
@media (max-width: 1024px) {
  .intake-table :is(th, td) {
    padding: 10px;
  }
  .intake-table thead th:first-child {
    width: 38%;
  }
}
</style>
