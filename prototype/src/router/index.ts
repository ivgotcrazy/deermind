import { createRouter, createWebHashHistory } from 'vue-router'
import ChildShell from '@/components/ChildShell.vue'
import ParentShell from '@/components/ParentShell.vue'

import HomeView from '@/views/child/HomeView.vue'
import MogiView from '@/views/child/MogiView.vue'
import PhotoView from '@/views/child/PhotoView.vue'
import AttributionView from '@/views/child/AttributionView.vue'
import ReadingView from '@/views/child/ReadingView.vue'
import ExplainView from '@/views/child/ExplainView.vue'
import PracticeView from '@/views/child/PracticeView.vue'
import VariantView from '@/views/child/VariantView.vue'
import SummaryView from '@/views/child/SummaryView.vue'
import ReviewView from '@/views/child/ReviewView.vue'
import ProgressView from '@/views/child/ProgressView.vue'
import ProfileView from '@/views/child/ProfileView.vue'

import SpacesView from '@/views/parent/SpacesView.vue'
import SpaceCreateView from '@/views/parent/SpaceCreateView.vue'
import TodayView from '@/views/parent/TodayView.vue'
import WeeklyView from '@/views/parent/WeeklyView.vue'
import ErrorDetailView from '@/views/parent/ErrorDetailView.vue'
import ParentInputView from '@/views/parent/ParentInputView.vue'
import MemoryView from '@/views/parent/MemoryView.vue'
import ParentSettingsView from '@/views/parent/ParentSettingsView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/child/home' },
    {
      path: '/child',
      component: ChildShell,
      children: [
        { path: '', redirect: '/child/home' },
        { path: 'home', component: HomeView },
        { path: 'mogi', component: MogiView },
        { path: 'photo', component: PhotoView },
        { path: 'attribution', component: AttributionView },
        { path: 'reading', component: ReadingView },
        { path: 'explain', component: ExplainView },
        { path: 'practice', component: PracticeView },
        { path: 'variant', component: VariantView },
        { path: 'summary', component: SummaryView },
        { path: 'review', component: ReviewView },
        { path: 'progress', component: ProgressView },
        { path: 'profile', component: ProfileView },
      ],
    },
    {
      path: '/parent',
      component: ParentShell,
      children: [
        { path: '', redirect: '/parent/today' },
        { path: 'spaces', component: SpacesView },
        { path: 'space-create', component: SpaceCreateView },
        { path: 'today', component: TodayView },
        { path: 'weekly', component: WeeklyView },
        { path: 'errors', component: ErrorDetailView },
        { path: 'input', component: ParentInputView },
        { path: 'memory', component: MemoryView },
        { path: 'settings', component: ParentSettingsView },
      ],
    },
  ],
})

export default router
