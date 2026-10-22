import { createApp } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';

// Role-specific bundles keep the retained parent UI independent of the new clients.
const role = new URLSearchParams(location.search).get('role') || 'student';
const router = createRouter({
  history: createWebHashHistory(),
  routes: [{ path: '/:page?', component: { render: () => null } }],
  scrollBehavior: () => ({ top: 0 }),
});
router.beforeEach(to => {
  if (to.path === '/') return { path: role === 'admin' ? '/dashboard' : role === 'parent' ? '/overview' : '/home', query: to.query, replace: true };
});
async function mount() {
  if (role === 'parent') {
    await import('../structure/style.css');
    const { default: App } = await import('../structure/App.vue');
    createApp(App).use(router).mount('#app');
  } else if (role === 'admin') {
    await import('./admin/style.css');
    const { default: App } = await import('./admin/App.vue');
    createApp(App).use(router).mount('#app');
  } else {
    await import('./student/style.css');
    const { default: App } = await import('./student/App.vue');
    createApp(App).use(router).mount('#app');
  }
}
void mount();
