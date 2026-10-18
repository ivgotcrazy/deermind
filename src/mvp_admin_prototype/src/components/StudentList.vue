<script setup lang="ts">
import { ref, computed } from 'vue';
import { students } from '../data';
import type { Student, StudentLS } from '../types';

const emit = defineEmits<{ goTrace: [traceId: string] }>();

// 三级视图：list=系统维度, detail=学生维度, ls=学习空间维度
const viewMode = ref<'list' | 'detail' | 'ls'>('list');
const selectedStudent = ref<Student | null>(null);
const selectedLS = ref<StudentLS | null>(null);
const activeTab = ref<'status' | 'interaction' | 'timeline'>('status');

// 筛选
const gradeFilter = ref('all');
const lsFilter = ref('all');
const masteryFilter = ref('all');
const statusFilter = ref('all');
const searchQuery = ref('');
const sortField = ref<'avgMastery' | 'totalInteractions' | 'errorRate' | 'lastActive'>('lastActive');
const sortDesc = ref(true);

const grades = [...new Set(students.map(s => s.grade))];
const allLSNames = [...new Set(students.flatMap(s => s.learningSpaces.map(l => l.name)))];

const filteredStudents = computed(() => {
  let list = students.filter(s => {
    if (gradeFilter.value !== 'all' && s.grade !== gradeFilter.value) return false;
    if (lsFilter.value !== 'all' && !s.learningSpaces.some(l => l.name === lsFilter.value)) return false;
    if (masteryFilter.value === 'low' && s.avgMastery >= 50) return false;
    if (masteryFilter.value === 'mid' && (s.avgMastery < 50 || s.avgMastery >= 70)) return false;
    if (masteryFilter.value === 'high' && s.avgMastery < 70) return false;
    if (statusFilter.value === 'attention' && s.errorRate < 5 && s.avgMastery >= 60) return false;
    if (statusFilter.value === 'inactive' && s.streak > 3) return false;
    if (searchQuery.value && !s.name.includes(searchQuery.value)) return false;
    return true;
  });
  list = [...list].sort((a, b) => {
    let va: any = a[sortField.value], vb: any = b[sortField.value];
    if (typeof va === 'string') { va = va; vb = vb; return sortDesc.value ? vb.localeCompare(va) : va.localeCompare(vb); }
    return sortDesc.value ? vb - va : va - vb;
  });
  return list;
});

// 系统级统计
const systemStats = computed(() => ({
  total: students.length,
  avgMastery: Math.round(students.reduce((s, st) => s + st.avgMastery, 0) / students.length),
  avgErrorRate: (students.reduce((s, st) => s + st.errorRate, 0) / students.length).toFixed(1),
  attention: students.filter(s => s.errorRate >= 5 || s.avgMastery < 50).length,
  activeToday: students.filter(s => s.lastActive.startsWith('10-18')).length,
}));

function openStudent(s: Student) {
  selectedStudent.value = s;
  viewMode.value = 'detail';
}
function backToList() {
  viewMode.value = 'list';
  selectedStudent.value = null;
  selectedLS.value = null;
}
function openLS(ls: StudentLS) {
  selectedLS.value = ls;
  viewMode.value = 'ls';
  activeTab.value = 'status';
}
function backToStudent() {
  viewMode.value = 'detail';
  selectedLS.value = null;
}

function masteryColor(v: number): string {
  if (v >= 70) return '#2d8a5e';
  if (v >= 50) return '#c9942a';
  return '#b85c3c';
}
const actionTypeColor: Record<string, string> = {
  '讲解': '#2d6a4f', '练习': '#4a6fa5', '答疑': '#c9942a', '复习': '#8a99a8',
};
function toggleSort(field: typeof sortField.value) {
  if (sortField.value === field) sortDesc.value = !sortDesc.value;
  else { sortField.value = field; sortDesc.value = true; }
}
</script>

<template>
  <div class="student-profile">
    <!-- ========== 系统维度：学生表格 ========== -->
    <template v-if="viewMode === 'list'">
      <div class="page-header">
        <h2>学生画像</h2>
        <span class="header-sub">系统维度 · 共 {{ students.length }} 名学生</span>
      </div>

      <!-- 系统级统计 -->
      <div class="sys-stats">
        <div class="sys-stat"><span class="ss-label">总学生数</span><span class="ss-value">{{ systemStats.total }}</span></div>
        <div class="sys-stat"><span class="ss-label">平均掌握度</span><span class="ss-value" :style="{color: masteryColor(systemStats.avgMastery)}">{{ systemStats.avgMastery }}%</span></div>
        <div class="sys-stat"><span class="ss-label">平均异常率</span><span class="ss-value" :class="{warn: Number(systemStats.avgErrorRate) > 5}">{{ systemStats.avgErrorRate }}%</span></div>
        <div class="sys-stat"><span class="ss-label">需关注</span><span class="ss-value warn">{{ systemStats.attention }}</span></div>
        <div class="sys-stat"><span class="ss-label">今日活跃</span><span class="ss-value">{{ systemStats.activeToday }}</span></div>
      </div>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <select v-model="gradeFilter" class="filter-select">
          <option value="all">全部年级</option>
          <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
        </select>
        <select v-model="lsFilter" class="filter-select">
          <option value="all">全部学习空间</option>
          <option v-for="ls in allLSNames" :key="ls" :value="ls">{{ ls }}</option>
        </select>
        <select v-model="masteryFilter" class="filter-select">
          <option value="all">全部掌握度</option>
          <option value="high">优秀 (≥70%)</option>
          <option value="mid">发展中 (50-70%)</option>
          <option value="low">需加强 (<50%)</option>
        </select>
        <select v-model="statusFilter" class="filter-select">
          <option value="all">全部状态</option>
          <option value="attention">需关注</option>
          <option value="inactive">不活跃</option>
        </select>
        <input v-model="searchQuery" type="text" placeholder="搜索学生姓名..." class="filter-search" />
      </div>

      <!-- 学生表格 -->
      <div class="student-table">
        <div class="table-header">
          <span class="col-name">学生</span>
          <span class="col-grade">年级</span>
          <span class="col-ls">学习空间</span>
          <span class="col-num sortable" @click="toggleSort('totalInteractions')">总交互 ↕</span>
          <span class="col-num sortable" @click="toggleSort('avgMastery')">平均掌握度 ↕</span>
          <span class="col-num sortable" @click="toggleSort('errorRate')">异常率 ↕</span>
          <span class="col-time sortable" @click="toggleSort('lastActive')">最后活跃 ↕</span>
          <span class="col-action">操作</span>
        </div>
        <div v-for="s in filteredStudents" :key="s.id" class="table-row" @click="openStudent(s)">
          <span class="col-name">
            <span class="row-avatar">{{ s.name.charAt(0) }}</span>
            {{ s.name }}
          </span>
          <span class="col-grade">{{ s.grade }}</span>
          <span class="col-ls">
            <span class="ls-count">{{ s.learningSpaces.length }}个</span>
            <span class="ls-primary">{{ s.learningSpaces[0]?.name }}</span>
          </span>
          <span class="col-num mono">{{ s.totalInteractions }}</span>
          <span class="col-num">
            <span class="mastery-inline" :style="{color: masteryColor(s.avgMastery)}">{{ s.avgMastery }}%</span>
          </span>
          <span class="col-num">
            <span :class="{warn: s.errorRate >= 5}">{{ s.errorRate }}%</span>
          </span>
          <span class="col-time mono">{{ s.lastActive }}</span>
          <span class="col-action"><button class="detail-btn" @click.stop="openStudent(s)">查看 →</button></span>
        </div>
      </div>
      <div class="pagination"><span>共 {{ filteredStudents.length }} 条</span></div>
    </template>

    <!-- ========== 学生维度：跨LS概览 + LS列表 ========== -->
    <template v-else-if="viewMode === 'detail' && selectedStudent">
      <div class="detail-header">
        <button class="back-btn" @click="backToList">← 返回学生列表</button>
        <div class="detail-title">
          <div class="student-avatar large">{{ selectedStudent.name.charAt(0) }}</div>
          <div>
            <h2>{{ selectedStudent.name }}</h2>
            <span class="detail-sub">{{ selectedStudent.grade }} · 最后活跃 {{ selectedStudent.lastActive }}</span>
          </div>
        </div>
      </div>

      <!-- 学生跨LS聚合（只有跨LS有意义的数据） -->
      <div class="overview-grid">
        <div class="ov-card primary">
          <span class="ov-label">学习连续性</span>
          <span class="ov-value">{{ selectedStudent.streak }}天</span>
          <span class="ov-sub">连续活跃</span>
        </div>
        <div class="ov-card">
          <span class="ov-label">总交互</span>
          <span class="ov-value">{{ selectedStudent.totalInteractions }}</span>
          <span class="ov-sub">跨所有学习空间</span>
        </div>
        <div class="ov-card">
          <span class="ov-label">平均会话</span>
          <span class="ov-value">{{ selectedStudent.avgSessionDuration }}</span>
          <span class="ov-sub">每次学习时长</span>
        </div>
        <div class="ov-card">
          <span class="ov-label">综合异常率</span>
          <span class="ov-value" :class="{warn: selectedStudent.errorRate >= 5}">{{ selectedStudent.errorRate }}%</span>
          <span class="ov-sub">跨LS加权</span>
        </div>
        <div class="ov-card">
          <span class="ov-label">学习空间</span>
          <span class="ov-value">{{ selectedStudent.learningSpaces.length }}</span>
          <span class="ov-sub">{{ selectedStudent.learningSpaces.filter(l => l.status === 'active').length }}个活跃</span>
        </div>
      </div>

      <!-- 学习空间列表 -->
      <h3 class="section-title">学习空间（点击进入详细诊断）</h3>
      <div class="ls-grid">
        <div v-for="ls in selectedStudent.learningSpaces" :key="ls.id" class="ls-card" :class="{paused: ls.status === 'paused'}" @click="openLS(ls)">
          <div class="ls-card-header">
            <div class="ls-icon">{{ ls.subject === '数学' ? '🔢' : '📖' }}</div>
            <div class="ls-info">
              <h4>{{ ls.name }}</h4>
              <span class="ls-meta">{{ ls.textbook }} · {{ ls.grade }}</span>
            </div>
            <span class="ls-status-tag" :class="ls.status">{{ ls.status === 'active' ? '活跃' : '已暂停' }}</span>
          </div>
          <div class="ls-card-stats">
            <div class="ls-stat">
              <span class="ls-stat-value" :style="{color: masteryColor(ls.avgMastery)}">{{ ls.avgMastery }}%</span>
              <span class="ls-stat-label">掌握度</span>
            </div>
            <div class="ls-stat">
              <span class="ls-stat-value">{{ ls.totalInteractions }}</span>
              <span class="ls-stat-label">交互数</span>
            </div>
            <div class="ls-stat">
              <span class="ls-stat-value" :class="{warn: ls.errorRate >= 5}">{{ ls.errorRate }}%</span>
              <span class="ls-stat-label">异常率</span>
            </div>
            <div class="ls-stat">
              <span class="ls-stat-value">{{ ls.weakKCs.length }}</span>
              <span class="ls-stat-label">薄弱KC</span>
            </div>
          </div>
          <div class="ls-card-footer">
            <span class="ls-beliefs">
              <span v-for="b in ls.beliefs.slice(0,2)" :key="b.claim" class="ls-belief-tag">{{ b.claim }} {{ b.current }}%</span>
            </span>
            <span class="ls-view">查看详情 →</span>
          </div>
        </div>
      </div>
    </template>

    <!-- ========== 学习空间维度：详细诊断 ========== -->
    <template v-else-if="viewMode === 'ls' && selectedStudent && selectedLS">
      <div class="detail-header">
        <button class="back-btn" @click="backToStudent">← 返回 {{ selectedStudent.name }}</button>
        <div class="detail-title">
          <div class="ls-icon-large">{{ selectedLS.subject === '数学' ? '🔢' : '📖' }}</div>
          <div>
            <h2>{{ selectedLS.name }}</h2>
            <span class="detail-sub">{{ selectedStudent.name }} · {{ selectedLS.textbook }} · 最后活跃 {{ selectedLS.lastActive }}</span>
          </div>
        </div>
        <span class="ls-status-tag large" :class="selectedLS.status">{{ selectedLS.status === 'active' ? '活跃' : '已暂停' }}</span>
      </div>

      <!-- LS概览 -->
      <div class="overview-grid">
        <div class="ov-card primary">
          <span class="ov-label">掌握度</span>
          <span class="ov-value" :style="{color: masteryColor(selectedLS.avgMastery)}">{{ selectedLS.avgMastery }}%</span>
          <span class="ov-sub">综合所有Claim</span>
        </div>
        <div class="ov-card">
          <span class="ov-label">交互数</span>
          <span class="ov-value">{{ selectedLS.totalInteractions }}</span>
          <span class="ov-sub">该学习空间</span>
        </div>
        <div class="ov-card">
          <span class="ov-label">异常率</span>
          <span class="ov-value" :class="{warn: selectedLS.errorRate >= 5}">{{ selectedLS.errorRate }}%</span>
          <span class="ov-sub">系统处理异常</span>
        </div>
        <div class="ov-card">
          <span class="ov-label">薄弱KC</span>
          <span class="ov-value">{{ selectedLS.weakKCs.length }}</span>
          <span class="ov-sub">掌握度低于60%</span>
        </div>
        <div class="ov-card">
          <span class="ov-label">Claim数</span>
          <span class="ov-value">{{ selectedLS.beliefs.length }}</span>
          <span class="ov-sub">能力主张</span>
        </div>
      </div>

      <!-- Tab -->
      <div class="tab-bar">
        <button class="tab" :class="{active: activeTab === 'status'}" @click="activeTab = 'status'">学习状态</button>
        <button class="tab" :class="{active: activeTab === 'interaction'}" @click="activeTab = 'interaction'">交互统计</button>
        <button class="tab" :class="{active: activeTab === 'timeline'}" @click="activeTab = 'timeline'">学习轨迹</button>
      </div>

      <!-- 学习状态 -->
      <div v-if="activeTab === 'status'" class="tab-content">
        <div class="content-grid">
          <div class="panel">
            <h3>能力主张（Claim）掌握度</h3>
            <div v-for="b in selectedLS.beliefs" :key="b.claim" class="belief-detail">
              <div class="belief-detail-header">
                <span class="bd-name">{{ b.claim }}</span>
                <span class="bd-change" :class="{up: b.change > 0}">{{ b.change > 0 ? '+' : '' }}{{ b.change }}%</span>
              </div>
              <div class="bd-bar"><div class="bd-fill" :style="{width: b.current + '%', background: masteryColor(b.current)}"></div></div>
              <div class="bd-range"><span>先验 {{ b.previous }}%</span><span>当前 {{ b.current }}%</span></div>
            </div>
          </div>
          <div class="panel">
            <h3>薄弱知识点（KC）</h3>
            <div v-if="selectedLS.weakKCs.length === 0" class="empty-small">暂无薄弱知识点</div>
            <div v-else class="weak-list">
              <div v-for="kc in selectedLS.weakKCs" :key="kc.kcId" class="weak-item">
                <div class="weak-info">
                  <span class="weak-id mono">{{ kc.kcId }}</span>
                  <span class="weak-name">{{ kc.kcName }}</span>
                </div>
                <div class="weak-mastery">
                  <div class="wm-bar"><div class="wm-fill" :style="{width: kc.mastery + '%', background: masteryColor(kc.mastery)}"></div></div>
                  <span class="wm-value">{{ kc.mastery }}%</span>
                </div>
                <span class="weak-evidence">{{ kc.evidenceCount }}条证据</span>
              </div>
            </div>
          </div>
          <div class="panel wide">
            <h3>掌握度趋势</h3>
            <div class="trend-chart">
              <div class="trend-bars">
                <div v-for="(p, i) in selectedLS.masteryTrend" :key="i" class="trend-col">
                  <div class="trend-bar-wrap"><div class="trend-bar" :style="{height: p.value + '%'}"></div></div>
                  <span class="trend-value">{{ p.value }}</span>
                  <span class="trend-date">{{ p.date }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 交互统计 -->
      <div v-else-if="activeTab === 'interaction'" class="tab-content">
        <div class="content-grid">
          <div class="panel">
            <h3>教学动作（Action）分布</h3>
            <div class="action-dist">
              <div v-for="a in selectedLS.actionDistribution" :key="a.type" class="action-row">
                <span class="action-label">{{ a.type }}</span>
                <div class="action-bar"><div class="action-fill" :style="{width: (a.count / Math.max(...selectedLS.actionDistribution.map(x => x.count)) * 100) + '%', background: actionTypeColor[a.type]}"></div></div>
                <span class="action-count">{{ a.count }}</span>
              </div>
            </div>
          </div>
          <div class="panel">
            <h3>交互质量指标</h3>
            <div class="quality-list">
              <div class="quality-item"><span class="q-label">异常率</span><span class="q-value" :class="{warn: selectedLS.errorRate >= 5}">{{ selectedLS.errorRate }}%</span><span class="q-desc">Observation验证失败/降级</span></div>
              <div class="quality-item"><span class="q-label">总交互</span><span class="q-value">{{ selectedLS.totalInteractions }}</span><span class="q-desc">该学习空间累计</span></div>
              <div class="quality-item"><span class="q-label">Claim覆盖</span><span class="q-value">{{ selectedLS.beliefs.length }}</span><span class="q-desc">已建模的能力主张</span></div>
              <div class="quality-item"><span class="q-label">薄弱点</span><span class="q-value">{{ selectedLS.weakKCs.length }}</span><span class="q-desc">需重点关注</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 学习轨迹 -->
      <div v-else-if="activeTab === 'timeline'" class="tab-content">
        <div class="timeline-panel">
          <h3>学习轨迹</h3>
          <div v-if="selectedLS.episodes.length === 0" class="empty-small">暂无学习记录</div>
          <div v-else class="timeline">
            <div v-for="(ep, i) in selectedLS.episodes" :key="i" class="timeline-item">
              <div class="tl-dot" :class="ep.type"></div>
              <div class="tl-line" v-if="i < selectedLS.episodes.length - 1"></div>
              <div class="tl-content">
                <div class="tl-header">
                  <span class="tl-date">{{ ep.date }}</span>
                  <span class="tl-type" :class="ep.type">{{ ep.type === 'lecture' ? '讲解' : ep.type === 'practice' ? '练习' : ep.type === 'qa' ? '答疑' : '复习' }}</span>
                  <span class="tl-mastery">掌握度 {{ ep.masteryChange }}</span>
                </div>
                <span class="tl-title">{{ ep.title }}</span>
                <div class="tl-traces" v-if="ep.traceIds.length > 0">
                  <button v-for="tid in ep.traceIds" :key="tid" class="tl-trace-btn" @click.stop="emit('goTrace', tid)">Trace {{ tid.substring(0,8) }} →</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.student-profile { padding: 20px 24px; height: 100%; overflow-y: auto; }
.page-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.header-sub { font-size: 12px; color: #8a99a8; }

/* 系统统计 */
.sys-stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }
.sys-stat { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.ss-label { font-size: 11px; color: #8a99a8; }
.ss-value { font-size: 24px; font-weight: 700; color: #1a3a2e; }
.ss-value.warn { color: #b85c3c; }

/* 筛选 */
.filter-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-select { padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; background: white; }
.filter-search { flex: 1; min-width: 160px; padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; }
.filter-search:focus { outline: none; border-color: #2d6a4f; }

/* 学生表格 */
.student-table { background: white; border: 1px solid #e1e8ed; border-radius: 10px; overflow: hidden; }
.table-header { display: flex; padding: 12px 16px; background: #f7f9fa; border-bottom: 1px solid #e1e8ed; font-size: 12px; font-weight: 600; color: #5a6b7a; }
.table-row { display: flex; padding: 12px 16px; border-bottom: 1px solid #f5f7fa; cursor: pointer; align-items: center; font-size: 13px; transition: background 0.1s; }
.table-row:hover { background: #f5f9f7; }
.col-name { width: 120px; flex-shrink: 0; display: flex; align-items: center; gap: 8px; font-weight: 500; }
.row-avatar { width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(135deg, #2d6a4f, #40916c); color: white; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; flex-shrink: 0; }
.col-grade { width: 70px; flex-shrink: 0; color: #5a6b7a; }
.col-ls { width: 180px; flex-shrink: 0; display: flex; flex-direction: column; gap: 2px; }
.ls-count { font-size: 11px; color: #4a6fa5; font-weight: 600; }
.ls-primary { font-size: 11px; color: #8a99a8; }
.col-num { width: 90px; flex-shrink: 0; text-align: center; }
.col-num.sortable { cursor: pointer; user-select: none; }
.col-num.sortable:hover { color: #2d6a4f; }
.col-time { width: 110px; flex-shrink: 0; color: #8a99a8; font-size: 12px; }
.col-time.sortable { cursor: pointer; }
.col-action { width: 80px; flex-shrink: 0; text-align: right; }
.mastery-inline { font-weight: 600; }
.warn { color: #b85c3c !important; font-weight: 600; }
.mono { font-family: Consolas, Monaco, monospace; }
.detail-btn { background: none; border: none; color: #2d6a4f; font-size: 12px; cursor: pointer; font-family: inherit; font-weight: 500; }
.detail-btn:hover { text-decoration: underline; }
.pagination { padding: 12px 0; font-size: 12px; color: #8a99a8; }

/* 详情头部 */
.detail-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.back-btn { background: none; border: 1px solid #d0d7de; color: #5a6b7a; padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; flex-shrink: 0; }
.back-btn:hover { background: #f0f4f7; }
.detail-title { display: flex; align-items: center; gap: 12px; flex: 1; }
.detail-title h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.detail-sub { font-size: 12px; color: #8a99a8; }
.student-avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #2d6a4f, #40916c); color: white; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 600; flex-shrink: 0; }
.student-avatar.large { width: 48px; height: 48px; font-size: 20px; }
.ls-icon { font-size: 24px; flex-shrink: 0; }
.ls-icon-large { font-size: 32px; flex-shrink: 0; }
.ls-status-tag { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.ls-status-tag.large { padding: 6px 14px; font-size: 13px; }
.ls-status-tag.active { background: #e8f5ee; color: #1b4332; }
.ls-status-tag.paused { background: #f0f4f7; color: #8a99a8; }

/* 概览 */
.overview-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }
.ov-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.ov-card.primary { border-left: 3px solid #2d6a4f; }
.ov-label { font-size: 11px; color: #8a99a8; }
.ov-value { font-size: 22px; font-weight: 700; color: #1a3a2e; line-height: 1.2; }
.ov-value.warn { color: #b85c3c; }
.ov-sub { font-size: 11px; color: #5a7a6a; }

.section-title { margin: 20px 0 12px 0; font-size: 14px; color: #1a3a2e; }

/* LS卡片 */
.ls-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
.ls-card { background: white; border: 1px solid #e1e8ed; border-radius: 12px; padding: 16px; cursor: pointer; transition: all 0.2s; }
.ls-card:hover { border-color: #2d6a4f; box-shadow: 0 4px 12px rgba(45,106,79,0.1); transform: translateY(-2px); }
.ls-card.paused { opacity: 0.7; }
.ls-card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.ls-info h4 { margin: 0; font-size: 14px; color: #1a3a2e; }
.ls-meta { font-size: 11px; color: #8a99a8; }
.ls-card-header .ls-status-tag { margin-left: auto; }
.ls-card-stats { display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid #f0f4f7; border-bottom: 1px solid #f0f4f7; margin-bottom: 10px; }
.ls-stat { text-align: center; }
.ls-stat-value { display: block; font-size: 18px; font-weight: 700; color: #1a3a2e; }
.ls-stat-value.warn { color: #b85c3c; }
.ls-stat-label { font-size: 10px; color: #8a99a8; }
.ls-card-footer { display: flex; justify-content: space-between; align-items: center; }
.ls-beliefs { display: flex; gap: 4px; flex-wrap: wrap; }
.ls-belief-tag { font-size: 10px; background: #f0f4f7; color: #5a6b7a; padding: 2px 6px; border-radius: 3px; }
.ls-view { font-size: 12px; color: #2d6a4f; font-weight: 600; flex-shrink: 0; }

/* Tab */
.tab-bar { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #e1e8ed; }
.tab { padding: 8px 20px; background: none; border: none; border-bottom: 2px solid transparent; font-size: 14px; color: #5a6b7a; cursor: pointer; font-family: inherit; margin-bottom: -2px; }
.tab.active { color: #1b4332; font-weight: 600; border-bottom-color: #2d6a4f; }

.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.panel { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 16px; }
.panel.wide { grid-column: 1 / -1; }
.panel h3 { margin: 0 0 14px 0; font-size: 14px; color: #1a3a2e; }
.empty-small { text-align: center; padding: 30px; color: #8a99a8; font-size: 13px; }

/* 学习状态 */
.belief-detail { margin-bottom: 16px; }
.belief-detail:last-child { margin-bottom: 0; }
.belief-detail-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
.bd-name { font-size: 13px; font-weight: 500; color: #2c3e50; }
.bd-change { font-size: 12px; color: #b85c3c; font-weight: 600; }
.bd-change.up { color: #2d8a5e; }
.bd-bar { height: 8px; background: #f0f4f7; border-radius: 4px; overflow: hidden; margin-bottom: 4px; }
.bd-fill { height: 100%; border-radius: 4px; }
.bd-range { display: flex; justify-content: space-between; font-size: 11px; color: #8a99a8; }
.weak-list { display: flex; flex-direction: column; gap: 10px; }
.weak-item { display: flex; align-items: center; gap: 10px; padding: 8px; background: #fafbfc; border-radius: 6px; }
.weak-info { display: flex; flex-direction: column; gap: 2px; width: 120px; flex-shrink: 0; }
.weak-id { font-size: 10px; color: #8a99a8; }
.weak-name { font-size: 12px; color: #2c3e50; font-weight: 500; }
.weak-mastery { flex: 1; display: flex; align-items: center; gap: 8px; }
.wm-bar { flex: 1; height: 6px; background: #f0f4f7; border-radius: 3px; overflow: hidden; }
.wm-fill { height: 100%; border-radius: 3px; }
.wm-value { width: 32px; text-align: right; font-size: 12px; font-weight: 600; }
.weak-evidence { font-size: 11px; color: #8a99a8; width: 60px; text-align: right; flex-shrink: 0; }
.trend-chart { padding: 10px 0; }
.trend-bars { display: flex; justify-content: space-around; align-items: flex-end; height: 140px; gap: 8px; }
.trend-col { display: flex; flex-direction: column; align-items: center; gap: 4px; flex: 1; }
.trend-bar-wrap { height: 80px; display: flex; align-items: flex-end; width: 100%; justify-content: center; }
.trend-bar { width: 32px; background: linear-gradient(180deg, #52b788, #2d6a4f); border-radius: 4px 4px 0 0; min-height: 4px; }
.trend-value { font-size: 11px; font-weight: 600; color: #2c3e50; }
.trend-date { font-size: 10px; color: #8a99a8; }

/* 交互统计 */
.action-dist { display: flex; flex-direction: column; gap: 12px; }
.action-row { display: flex; align-items: center; gap: 10px; }
.action-label { width: 40px; font-size: 13px; color: #3a4a5a; flex-shrink: 0; }
.action-bar { flex: 1; height: 16px; background: #f0f4f7; border-radius: 4px; overflow: hidden; }
.action-fill { height: 100%; border-radius: 4px; min-width: 2px; }
.action-count { width: 30px; text-align: right; font-weight: 600; color: #2c3e50; font-size: 13px; }
.quality-list { display: flex; flex-direction: column; gap: 14px; }
.quality-item { display: flex; flex-direction: column; gap: 2px; padding-bottom: 12px; border-bottom: 1px solid #f0f4f7; }
.quality-item:last-child { border-bottom: none; padding-bottom: 0; }
.q-label { font-size: 12px; color: #8a99a8; }
.q-value { font-size: 20px; font-weight: 700; color: #1a3a2e; }
.q-value.warn { color: #b85c3c; }
.q-desc { font-size: 11px; color: #a0aab8; }

/* 学习轨迹 */
.timeline-panel { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 16px; }
.timeline { position: relative; padding-left: 8px; }
.timeline-item { position: relative; padding-bottom: 20px; padding-left: 24px; }
.timeline-item:last-child { padding-bottom: 0; }
.tl-dot { position: absolute; left: 0; top: 4px; width: 12px; height: 12px; border-radius: 50%; background: #2d6a4f; border: 2px solid white; box-shadow: 0 0 0 2px #2d6a4f; z-index: 1; }
.tl-dot.practice { background: #4a6fa5; box-shadow: 0 0 0 2px #4a6fa5; }
.tl-dot.qa { background: #c9942a; box-shadow: 0 0 0 2px #c9942a; }
.tl-dot.review { background: #8a99a8; box-shadow: 0 0 0 2px #8a99a8; }
.tl-line { position: absolute; left: 5px; top: 18px; width: 2px; height: calc(100% - 10px); background: #e1e8ed; }
.tl-content { background: #fafbfc; border-radius: 8px; padding: 12px 14px; }
.tl-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.tl-date { font-size: 12px; color: #8a99a8; font-weight: 500; }
.tl-type { font-size: 10px; padding: 2px 8px; border-radius: 8px; font-weight: 600; }
.tl-type.lecture { background: #e8f5ee; color: #1b4332; }
.tl-type.practice { background: #e8f0f8; color: #2a4a6a; }
.tl-type.qa { background: #fef5e0; color: #6a5a1a; }
.tl-type.review { background: #f0f4f7; color: #5a6b7a; }
.tl-mastery { font-size: 11px; color: #2d8a5e; font-weight: 600; margin-left: auto; }
.tl-title { font-size: 13px; color: #2c3e50; font-weight: 500; display: block; margin-bottom: 8px; }
.tl-traces { display: flex; gap: 6px; flex-wrap: wrap; }
.tl-trace-btn { background: none; border: 1px solid #d0d7de; color: #2d6a4f; padding: 3px 10px; border-radius: 4px; font-size: 11px; cursor: pointer; font-family: inherit; }
.tl-trace-btn:hover { background: #e8f5ee; border-color: #2d6a4f; }

@media (max-width: 1200px) {
  .sys-stats, .overview-grid { grid-template-columns: repeat(3, 1fr); }
  .content-grid { grid-template-columns: 1fr; }
}
</style>
