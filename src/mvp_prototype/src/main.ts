import { createApp } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';
import App from './App.vue';
import StudentView from './views/StudentView.vue';
import ParentView from './views/ParentView.vue';
import AdminView from './views/AdminView.vue';
import './style.css';
import './intent.css';
import './learning.css';
import './lesson.css';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/student/home' },
    { path: '/student/:page?', component: StudentView },
    { path: '/parent/:page?', component: ParentView },
    { path: '/admin/:page?', component: AdminView },
    { path: '/:pathMatch(.*)*', redirect: '/student/home' },
  ],
  scrollBehavior: () => ({ top: 0 }),
});
createApp(App).use(router).mount('#app');
