<script setup lang="ts">
import { ref, computed } from 'vue';
import { textbooks, domains } from '../data';
import { domainDetails } from '../admin-data';
import type { Textbook, TextbookChapter } from '../types';

type ViewMode = 'list' | 'detail';
type ChapterTab = 'structure' | 'domain-mapping';

const viewMode = ref<ViewMode>('list');
const selectedTextbook = ref<Textbook | null>(null);
const chapterTab = ref<ChapterTab>('structure');
const expandedUnits = ref<Set<string>>(new Set());
const selectedChapterId = ref<string>('');

function openTextbook(tb: Textbook) {
  selectedTextbook.value = tb;
  viewMode.value = 'detail';
  expandedUnits.value = new Set(tb.units.map(u => u.id));
  chapterTab.value = 'structure';
  selectedChapterId.value = '';
}

function backToList() {
  viewMode.value = 'list';
  selectedTextbook.value = null;
  selectedChapterId.value = '';
}

function toggleUnit(unitId: string) {
  if (expandedUnits.value.has(unitId)) {
    expandedUnits.value.delete(unitId);
  } else {
    expandedUnits.value.add(unitId);
  }
}

function selectChapter(chapter: TextbookChapter) {
  selectedChapterId.value = selectedChapterId.value === chapter.id ? '' : chapter.id;
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: '已启用', color: '#2d8a5e', bg: '#e8f5ee' },
  draft: { label: '草稿', color: '#8a99a8', bg: '#f0f4f7' },
  archived: { label: '已归档', color: '#b85c3c', bg: '#fdf0ed' },
};

const totalChapters = computed(() => textbooks.reduce((s, t) => s + t.totalChapters, 0));
const totalMappedKc = computed(() => textbooks.reduce((s, t) => s + t.mappedKcCount, 0));

// 获取章节关联的 Domain 内容
function getChapterDomainContent(chapter: TextbookChapter) {
  const domain = domainDetails['DOM-001'];
  if (!domain) return { tasks: [], solutions: [], kcs: [] };
  const kcs = domain.kcs.filter(k => chapter.kcRefs.includes(k.id));
  const tasks = domain.tasks.filter(t => t.kcRefs.some(kc => chapter.kcRefs.includes(kc)));
  const solutions = domain.solutions.filter(s => tasks.some(t => t.solutionRefs.includes(s.id)));
  return { tasks, solutions, kcs };
}

const selectedChapter = computed(() => {
  if (!selectedTextbook.value || !selectedChapterId.value) return null;
  for (const unit of selectedTextbook.value.units) {
    const ch = unit.chapters.find(c => c.id === selectedChapterId.value);
    if (ch) return ch;
  }
  return null;
});

const mappingProgress = computed(() => {
  if (!selectedTextbook.value) return 0;
  const total = selectedTextbook.value.totalChapters;
  const mapped = total - selectedTextbook.value.unmappedChapters;
  return total > 0 ? Math.round((mapped / total) * 100) : 0;
});
</script>

<template>
  <div class="textbook-management">
    <!-- 列表视图 -->
    <template v-if="viewMode === 'list'">
      <div class="page-header">
        <div>
          <h2>教材管理</h2>
          <p class="page-desc">管理教材资源，建立教材章节与 Domain Space 中 Task/Solution/KC 的关联</p>
        </div>
        <button class="primary-btn">+ 导入教材</button>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">教材总数</span>
          <span class="stat-value">{{ textbooks.length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">总章节数</span>
          <span class="stat-value">{{ totalChapters }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">已映射 KC</span>
          <span class="stat-value">{{ totalMappedKc }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">启用中</span>
          <span class="stat-value">{{ textbooks.filter(t => t.status === 'active').length }}</span>
        </div>
      </div>

      <div class="table-card">
        <table class="data-table">
          <thead>
            <tr>
              <th>教材ID</th>
              <th>教材名称</th>
              <th>版本</th>
              <th>年级</th>
              <th>关联 Domain</th>
              <th>章节数</th>
              <th>KC 映射</th>
              <th>未映射章节</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tb in textbooks" :key="tb.id" class="clickable-row" @click="openTextbook(tb)">
              <td class="mono">{{ tb.id }}</td>
              <td class="font-medium">{{ tb.name }}</td>
              <td>{{ tb.version }}</td>
              <td>{{ tb.grade }}</td>
              <td>{{ tb.domain }}</td>
              <td>{{ tb.totalChapters }}</td>
              <td>{{ tb.mappedKcCount }}</td>
              <td :class="{ warning: tb.unmappedChapters > 0 }">{{ tb.unmappedChapters > 0 ? tb.unmappedChapters : '—' }}</td>
              <td>
                <span class="status-tag" :style="{ color: statusConfig[tb.status].color, background: statusConfig[tb.status].bg }">
                  {{ statusConfig[tb.status].label }}
                </span>
              </td>
              <td><button class="link-btn">管理</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 详情视图 -->
    <template v-else-if="selectedTextbook">
      <div class="detail-header">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <div class="detail-title">
          <h2>{{ selectedTextbook.name }}</h2>
          <span class="status-tag" :style="{ color: statusConfig[selectedTextbook.status].color, background: statusConfig[selectedTextbook.status].bg }">
            {{ statusConfig[selectedTextbook.status].label }}
          </span>
        </div>
        <div class="detail-meta">
          <span>{{ selectedTextbook.publisher }}</span>
          <span>{{ selectedTextbook.grade }}</span>
          <span>关联 Domain: {{ selectedTextbook.domain }}</span>
          <span>导入时间: {{ selectedTextbook.importedAt }}</span>
        </div>
      </div>

      <!-- 映射进度 -->
      <div class="mapping-progress">
        <div class="progress-info">
          <span class="progress-label">章节 Domain 映射进度</span>
          <span class="progress-value">{{ mappingProgress }}% ({{ selectedTextbook.totalChapters - selectedTextbook.unmappedChapters }}/{{ selectedTextbook.totalChapters }} 章节已映射)</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: mappingProgress + '%' }"></div>
        </div>
      </div>

      <!-- Tab 切换 -->
      <div class="tab-bar">
        <button class="tab" :class="{ active: chapterTab === 'structure' }" @click="chapterTab = 'structure'">
          章节结构
        </button>
        <button class="tab" :class="{ active: chapterTab === 'domain-mapping' }" @click="chapterTab = 'domain-mapping'">
          Domain 内容关联
        </button>
      </div>

      <!-- 章节结构 -->
      <div v-if="chapterTab === 'structure'" class="chapter-tree">
        <div v-for="unit in selectedTextbook.units" :key="unit.id" class="unit-block">
          <div class="unit-header" @click="toggleUnit(unit.id)">
            <span class="unit-toggle">{{ expandedUnits.has(unit.id) ? '▼' : '▶' }}</span>
            <span class="unit-name">{{ unit.name }}</span>
            <span class="unit-count">{{ unit.chapters.length }} 章</span>
          </div>
          <div v-if="expandedUnits.has(unit.id)" class="chapter-list">
            <div
              v-for="chapter in unit.chapters"
              :key="chapter.id"
              class="chapter-item"
              :class="{ selected: selectedChapterId === chapter.id }"
              @click="selectChapter(chapter)"
            >
              <span class="chapter-name">{{ chapter.name }}</span>
              <span class="chapter-kcs">{{ chapter.kcRefs.length }} 个 KC</span>
              <span class="chapter-status" :class="{ mapped: chapter.kcRefs.length > 0, unmapped: chapter.kcRefs.length === 0 }">
                {{ chapter.kcRefs.length > 0 ? '已映射' : '未映射' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Domain 内容关联 -->
      <div v-if="chapterTab === 'domain-mapping'" class="domain-mapping">
        <div v-if="!selectedChapter" class="empty-hint">
          <p>请在左侧章节结构中选择一个章节，查看其关联的 Domain 内容</p>
        </div>
        <div v-else class="mapping-detail">
          <h3 class="mapping-title">{{ selectedChapter.name }} - 关联 Domain 内容</h3>

          <!-- 关联 KC -->
          <div class="mapping-section">
            <h4>关联 KC ({{ getChapterDomainContent(selectedChapter).kcs.length }})</h4>
            <div class="tag-list">
              <span v-for="kc in getChapterDomainContent(selectedChapter).kcs" :key="kc.id" class="content-tag kc-tag">
                <span class="mono">{{ kc.id }}</span> {{ kc.name }}
              </span>
              <span v-if="getChapterDomainContent(selectedChapter).kcs.length === 0" class="empty-text">暂无关联 KC</span>
            </div>
          </div>

          <!-- 关联 Task -->
          <div class="mapping-section">
            <h4>关联 Task ({{ getChapterDomainContent(selectedChapter).tasks.length }})</h4>
            <div class="task-list">
              <div v-for="task in getChapterDomainContent(selectedChapter).tasks" :key="task.id" class="task-item">
                <span class="mono task-id">{{ task.id }}</span>
                <span class="task-name">{{ task.name }}</span>
                <span class="task-desc">{{ task.description }}</span>
              </div>
              <span v-if="getChapterDomainContent(selectedChapter).tasks.length === 0" class="empty-text">暂无关联 Task</span>
            </div>
          </div>

          <!-- 关联 Solution -->
          <div class="mapping-section">
            <h4>关联 Solution ({{ getChapterDomainContent(selectedChapter).solutions.length }})</h4>
            <div class="tag-list">
              <span v-for="sol in getChapterDomainContent(selectedChapter).solutions" :key="sol.id" class="content-tag solution-tag">
                <span class="mono">{{ sol.id }}</span> {{ sol.name }}
              </span>
              <span v-if="getChapterDomainContent(selectedChapter).solutions.length === 0" class="empty-text">暂无关联 Solution</span>
            </div>
          </div>

          <div class="mapping-actions">
            <button class="secondary-btn">编辑关联</button>
            <button class="secondary-btn">从 Domain 池遴选</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.textbook-management { height: 100%; overflow-y: auto; padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px 0; font-size: 20px; color: #1a2a3a; }
.page-desc { margin: 0; font-size: 13px; color: #8a99a8; }
.primary-btn { background: #2d6a4f; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; }
.primary-btn:hover { background: #1b4332; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-card { background: #fff; border-radius: 8px; padding: 16px; border: 1px solid #e8ecf0; }
.stat-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #1a2a3a; }
.table-card { background: #fff; border-radius: 8px; border: 1px solid #e8ecf0; overflow: hidden; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { text-align: left; padding: 12px 16px; font-size: 12px; color: #8a99a8; font-weight: 600; background: #f8fafc; border-bottom: 1px solid #e8ecf0; }
.data-table td { padding: 12px 16px; font-size: 13px; color: #3a4a5a; border-bottom: 1px solid #f0f4f7; }
.clickable-row { cursor: pointer; transition: background 0.15s; }
.clickable-row:hover { background: #f8fafc; }
.mono { font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; color: #5a6b7a; }
.font-medium { font-weight: 500; }
.warning { color: #b85c3c; font-weight: 500; }
.status-tag { font-size: 11px; padding: 3px 8px; border-radius: 4px; font-weight: 500; }
.link-btn { background: none; border: none; color: #2d6a4f; cursor: pointer; font-size: 13px; font-family: inherit; padding: 0; }
.link-btn:hover { text-decoration: underline; }
.detail-header { margin-bottom: 16px; }
.back-btn { background: none; border: none; color: #5a6b7a; cursor: pointer; font-size: 13px; font-family: inherit; padding: 0; margin-bottom: 12px; }
.back-btn:hover { color: #2d6a4f; }
.detail-title { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.detail-title h2 { margin: 0; font-size: 20px; color: #1a2a3a; }
.detail-meta { display: flex; gap: 20px; font-size: 13px; color: #8a99a8; flex-wrap: wrap; }
.mapping-progress { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }
.progress-info { display: flex; justify-content: space-between; margin-bottom: 8px; }
.progress-label { font-size: 13px; color: #5a6b7a; font-weight: 500; }
.progress-value { font-size: 13px; color: #2d6a4f; font-weight: 500; }
.progress-bar { height: 8px; background: #f0f4f7; border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #40916c, #2d6a4f); border-radius: 4px; transition: width 0.3s; }
.tab-bar { display: flex; gap: 0; border-bottom: 2px solid #e8ecf0; margin-bottom: 16px; }
.tab { background: none; border: none; padding: 10px 16px; font-size: 13px; color: #8a99a8; cursor: pointer; font-family: inherit; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab:hover { color: #3a4a5a; }
.tab.active { color: #2d6a4f; border-bottom-color: #2d6a4f; font-weight: 500; }
.chapter-tree { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 8px 0; }
.unit-block { border-bottom: 1px solid #f0f4f7; }
.unit-block:last-child { border-bottom: none; }
.unit-header { display: flex; align-items: center; gap: 8px; padding: 12px 16px; cursor: pointer; }
.unit-header:hover { background: #f8fafc; }
.unit-toggle { font-size: 10px; color: #8a99a8; width: 16px; }
.unit-name { font-size: 14px; font-weight: 500; color: #1a2a3a; flex: 1; }
.unit-count { font-size: 12px; color: #8a99a8; }
.chapter-list { padding: 0 0 8px 40px; }
.chapter-item { display: flex; align-items: center; gap: 12px; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin-right: 8px; }
.chapter-item:hover { background: #f8fafc; }
.chapter-item.selected { background: #e8f5ee; }
.chapter-name { font-size: 13px; color: #3a4a5a; flex: 1; }
.chapter-kcs { font-size: 12px; color: #8a99a8; }
.chapter-status { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.chapter-status.mapped { background: #e8f5ee; color: #2d8a5e; }
.chapter-status.unmapped { background: #fdf0ed; color: #b85c3c; }
.domain-mapping { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 20px; min-height: 300px; }
.empty-hint { display: flex; align-items: center; justify-content: center; height: 200px; color: #8a99a8; font-size: 14px; }
.mapping-title { font-size: 16px; font-weight: 600; color: #1a2a3a; margin: 0 0 16px 0; }
.mapping-section { margin-bottom: 20px; }
.mapping-section h4 { font-size: 13px; font-weight: 600; color: #5a6b7a; margin: 0 0 10px 0; }
.tag-list { display: flex; flex-wrap: wrap; gap: 8px; }
.content-tag { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; padding: 6px 10px; border-radius: 6px; }
.kc-tag { background: #eef4ff; color: #4a6fa5; }
.solution-tag { background: #fff4e6; color: #c9942a; }
.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; background: #f8fafc; border-radius: 6px; }
.task-id { font-size: 11px; min-width: 50px; }
.task-name { font-size: 13px; font-weight: 500; color: #1a2a3a; min-width: 140px; }
.task-desc { font-size: 12px; color: #8a99a8; flex: 1; }
.empty-text { font-size: 13px; color: #b0b8c0; font-style: italic; }
.mapping-actions { display: flex; gap: 8px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #f0f4f7; }
.secondary-btn { background: #fff; border: 1px solid #d0d8e0; padding: 6px 14px; border-radius: 6px; font-size: 13px; color: #5a6b7a; cursor: pointer; font-family: inherit; }
.secondary-btn:hover { border-color: #2d6a4f; color: #2d6a4f; }
</style>
