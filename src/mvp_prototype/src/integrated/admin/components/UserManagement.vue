<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import {useRouter} from 'vue-router';
import {journey} from '../../../journeyState';
const router=useRouter();
const search=ref(''),role=ref('all'),page=ref(1);
const profiles=computed(()=>journey.accounts.profiles);
const filtered=computed(()=>profiles.value.filter(p=>(role.value==='all'||p.role===role.value)&&`${p.name} ${p.id}`.includes(search.value)));
const pages=computed(()=>Math.max(1,Math.ceil(filtered.value.length/15)));
const rows=computed(()=>filtered.value.slice((page.value-1)*15,page.value*15));
watch([search,role],()=>{page.value=1;});
function manage(){void router.push('/account');}
</script>
<template><div class="user-management">
 <div class="page-header"><h2>用户管理</h2><button class="add-btn" @click="manage">开户、关系与找回</button></div>
 <p class="user-source">来自本浏览器“账号与授权”流程的合成档案，新增后在此显示；不代表已创建真实登录账号。观测页面的示例学生目录与这些档案分别标识。</p>
 <div class="stats-row"><div class="stat-card"><span class="stat-label">档案总数</span><span class="stat-value">{{ profiles.length }}</span></div><div class="stat-card"><span class="stat-label">学生</span><span class="stat-value">{{ profiles.filter(p=>p.role==='student').length }}</span></div><div class="stat-card"><span class="stat-label">家长</span><span class="stat-value">{{ profiles.filter(p=>p.role==='parent').length }}</span></div><div class="stat-card"><span class="stat-label">有效亲子关联</span><span class="stat-value">{{ journey.accounts.links.filter(l=>l.active).length }}</span></div></div>
 <div class="filter-bar"><select v-model="role" class="filter-select" aria-label="用户角色"><option value="all">全部角色</option><option value="student">学生</option><option value="parent">家长</option></select><input v-model="search" class="filter-search" aria-label="查找用户" placeholder="搜索姓名或编号"/></div>
 <div class="user-table"><div class="table-header"><span class="col-user">用户</span><span class="col-role">角色</span><span class="col-detail">关联与凭据记录</span><span class="col-action">操作</span></div><div v-for="user in rows" :key="user.id" class="table-row"><span class="col-user"><div class="user-avatar">{{ user.name.slice(0,1) }}</div><div class="user-info"><span class="user-name">{{ user.name }}</span><span class="user-email">{{ user.id }}</span></div></span><span class="col-role">{{ user.role==='student'?'学生':'家长' }}</span><span class="col-detail">凭据记录 v{{ user.credentialRevision }} · {{ journey.accounts.links.filter(l=>l.active&&(l.parent===user.id||l.child===user.id)).length }} 个关联</span><span class="col-action"><button class="action-btn" @click="manage">管理关系</button></span></div></div>
 <div class="user-pages"><span>{{ filtered.length }} 条 · {{ page }}/{{ pages }} 页</span><button :disabled="page===1" @click="page--">上一页</button><button :disabled="page>=pages" @click="page++">下一页</button></div>
</div></template>
<style scoped>
.user-management { padding: 20px 24px; height: 100%; display: flex; flex-direction: column; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.add-btn { background: #2d6a4f; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; }
.add-btn:hover { background: #245440; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px 16px; }
.stat-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 6px; }
.stat-value { display: block; font-size: 24px; font-weight: 700; color: #1a3a2e; }
.filter-bar { display: flex; gap: 10px; margin-bottom: 16px; }
.filter-select { padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; background: white; }
.filter-search { flex: 1; min-width: 200px; padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; }
.filter-search:focus { outline: none; border-color: #2d6a4f; }
.user-table { flex: 1; background: white; border: 1px solid #e1e8ed; border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; }
.table-header { display: flex; padding: 12px 16px; background: #f7f9fa; border-bottom: 1px solid #e1e8ed; font-size: 12px; font-weight: 600; color: #5a6b7a; flex-shrink: 0; }
.table-row { display: flex; padding: 14px 16px; border-bottom: 1px solid #f5f7fa; align-items: center; font-size: 13px; }
.col-user { width: 220px; flex-shrink: 0; display: flex; align-items: center; gap: 10px; }
.user-avatar { width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #2d6a4f, #40916c); color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; flex-shrink: 0; }
.user-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.user-name { font-weight: 600; color: #2c3e50; }
.user-email { font-size: 11px; color: #8a99a8; }
.col-role { width: 80px; flex-shrink: 0; }
.role-tag { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.col-detail { flex: 1; display: flex; flex-wrap: wrap; gap: 8px; min-width: 0; }
.detail-item { font-size: 11px; background: #f0f4f7; padding: 2px 8px; border-radius: 4px; color: #5a6b7a; white-space: nowrap; }
.col-status { width: 80px; flex-shrink: 0; display: flex; align-items: center; gap: 6px; font-size: 12px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.col-time { width: 110px; flex-shrink: 0; font-size: 12px; color: #8a99a8; }
.col-action { width: 120px; flex-shrink: 0; display: flex; gap: 6px; }
.action-btn { background: none; border: 1px solid #d0d7de; color: #5a6b7a; padding: 4px 10px; border-radius: 4px; font-size: 12px; cursor: pointer; font-family: inherit; }
.action-btn:hover { background: #f0f4f7; }
.action-btn.danger { color: #b85c3c; border-color: #e8c4b8; }
.action-btn.danger:hover { background: #fdf0ed; }
.mono { font-family: Consolas, Monaco, monospace; }
</style>

<style scoped>.user-source{line-height:1.8;color:#7a8c80;margin-bottom:18px}.user-pages{display:flex;align-items:center;gap:14px;margin-top:18px}.user-pages button{padding:8px;border:1px solid #d3dfd8;background:white;border-radius:6px;cursor:pointer}.user-pages button:disabled{opacity:.5}</style>
