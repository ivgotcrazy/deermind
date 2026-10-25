import { createApp } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';
import App from './App.vue';
import './structure/style.css';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [{ path: '/:page?', component: { render: () => null } }],
  scrollBehavior: () => ({ top: 0 }),
});
router.beforeEach(to => to.path === '/' ? { path: '/overview', query: to.query, replace: true } : undefined);
createApp(App).use(router).mount('#app');
