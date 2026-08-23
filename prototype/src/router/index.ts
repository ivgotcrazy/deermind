import { createRouter, createWebHashHistory } from 'vue-router'
import ParentShell from '@/components/ParentShell.vue'

import ParentTodayView from '@/views/parent/ParentTodayView.vue'
import ParentWeeklyView from '@/views/parent/ParentWeeklyView.vue'
import ParentAccountsView from '@/views/parent/ParentAccountsView.vue'
import ParentSpacesView from '@/views/parent/ParentSpacesView.vue'

import AdminShell from '@/components/AdminShell.vue'
import AdminDashboardView from '@/views/admin/AdminDashboardView.vue'
import AdminKnowledgeView from '@/views/admin/AdminKnowledgeView.vue'
import AdminDecisionsView from '@/views/admin/AdminDecisionsView.vue'
import AdminRulesView from '@/views/admin/AdminRulesView.vue'

import StudentShell from '@/components/student/StudentShell.vue'
import StudentLoginView from '@/views/student/StudentLoginView.vue'
import StudentHomeView from '@/views/student/StudentHomeView.vue'
import StudentWrongbookView from '@/views/student/StudentWrongbookView.vue'
import StudentLearnView from '@/views/student/StudentLearnView.vue'
import StudentRecordView from '@/views/student/StudentRecordView.vue'
import StudentPhotoView from '@/views/student/StudentPhotoView.vue'
import StudentConfirmView from '@/views/student/StudentConfirmView.vue'
import StudentExplainView from '@/views/student/StudentExplainView.vue'
import StudentReadingView from '@/views/student/StudentReadingView.vue'
import StudentTeachBackView from '@/views/student/StudentTeachBackView.vue'
import StudentSettingsView from '@/views/student/StudentSettingsView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/student/home' },
    {
      path: '/student',
      component: StudentShell,
      children: [
        { path: '', redirect: '/student/home' },
        { path: 'login', component: StudentLoginView, meta: { fullscreen: true } },
        { path: 'home', component: StudentHomeView },
        { path: 'wrongbook', component: StudentWrongbookView },
        { path: 'learn', component: StudentLearnView },
        { path: 'record', component: StudentRecordView },
        { path: 'photo', component: StudentPhotoView, meta: { fullscreen: true } },
        { path: 'confirm', component: StudentConfirmView, meta: { fullscreen: true } },
        { path: 'explain', component: StudentExplainView, meta: { fullscreen: true } },
        { path: 'reading', component: StudentReadingView, meta: { fullscreen: true } },
        { path: 'teachback', component: StudentTeachBackView, meta: { fullscreen: true } },
        { path: 'settings', component: StudentSettingsView, meta: { fullscreen: true } },
      ],
    },
    {
      path: '/parent',
      component: ParentShell,
      children: [
        { path: '', redirect: '/parent/today' },
        { path: 'today', component: ParentTodayView },
        { path: 'weekly', component: ParentWeeklyView },
        { path: 'students', component: ParentAccountsView },
        { path: 'spaces', component: ParentSpacesView },
      ],
    },
    {
      path: '/admin',
      component: AdminShell,
      children: [
        { path: '', component: AdminDashboardView },
        { path: 'knowledge', component: AdminKnowledgeView },
        { path: 'decisions', component: AdminDecisionsView },
        { path: 'rules', component: AdminRulesView },
      ],
    },
  ],
})

export default router
