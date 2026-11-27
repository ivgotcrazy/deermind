<script setup lang="ts">
import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus';
import { ref } from 'vue';
import AuthGate from '../shared/auth/AuthGate.vue';
import AdminSignIn from './AdminSignIn.vue';
import DomainWorkspace from './features/domain/DomainWorkspace.vue';
import { clearCreateDraft } from './features/domain/draft';
import TextbookWorkspace from './features/materials/TextbookWorkspace.vue';
import ClaimWorkspace from './features/evaluation/ClaimWorkspace.vue';
import ActivityGuides from './features/interaction/ActivityGuides.vue';
import TargetWorkspace from './features/learning/TargetWorkspace.vue';
import SpaceWorkspace from './features/learning/SpaceWorkspace.vue';

const definitionPages = [
  { id: 'textbooks', label: '教材管理' },
  { id: 'domain', label: '领域管理' },
  { id: 'evaluation', label: '评估管理' },
  { id: 'interaction', label: '交互活动' },
  { id: 'targets', label: '目标管理' },
] as const;
const selection = ref<(typeof definitionPages)[number]['id'] | 'spaces'>(
  window.location.hash === '#textbooks' ? 'textbooks' : 'domain',
);

function resetWorkspace() {
  clearCreateDraft();
  selection.value = 'domain';
}
</script>

<template>
  <div class="admin-app">
    <AuthGate role="admin" @sign-out="resetWorkspace">
      <template #entry="entry">
        <AdminSignIn v-bind="entry" />
      </template>
      <template
        #workspace="{ session, busy, error, signOut, realtimeState, reconnect, storageUnavailable }"
      >
        <div class="admin-frame">
          <header class="admin-topbar">
            <strong>DeerMind</strong>
            <span>管理后台</span>
            <ElDropdown trigger="click" :disabled="busy" @command="signOut">
              <ElButton text aria-label="管理员账号与退出登录" :title="session.account.display_name"
                >管理员</ElButton
              >
              <template #dropdown>
                <ElDropdownMenu>
                  <ElDropdownItem disabled>{{ session.account.display_name }}</ElDropdownItem>
                  <ElDropdownItem command="sign-out">退出登录</ElDropdownItem>
                </ElDropdownMenu>
              </template>
            </ElDropdown>
          </header>

          <aside class="admin-sidebar">
            <nav aria-label="管理功能">
              <div class="admin-nav-group" aria-label="内容与定义">
                <p>内容与定义</p>
                <ElButton
                  v-for="page in definitionPages"
                  :key="page.id"
                  text
                  :aria-current="selection === page.id ? 'page' : undefined"
                  @click="selection = page.id"
                >
                  {{ page.label }}
                </ElButton>
              </div>
              <div class="admin-nav-group" aria-label="学习运行">
                <p>学习运行</p>
                <ElButton
                  text
                  :aria-current="selection === 'spaces' ? 'page' : undefined"
                  @click="selection = 'spaces'"
                >
                  学习空间
                </ElButton>
              </div>
            </nav>
          </aside>

          <main class="admin-main">
            <p v-if="error" role="alert">{{ error }}</p>
            <p v-if="storageUnavailable" role="status">待核对的消息暂存在本页，刷新后可能丢失。</p>
            <p v-if="realtimeState === 'reconnecting'" role="status">实时连接中断，正在重连…</p>
            <p v-else-if="realtimeState === 'unavailable'" role="status">
              实时连接暂不可用。<ElButton text @click="reconnect">重新连接</ElButton>
            </p>
            <DomainWorkspace v-if="selection === 'domain'" :session="session" />
            <TextbookWorkspace v-else-if="selection === 'textbooks'" :session="session" />
            <ClaimWorkspace v-else-if="selection === 'evaluation'" :session="session" />
            <ActivityGuides v-else-if="selection === 'interaction'" :session="session" />
            <TargetWorkspace v-else-if="selection === 'targets'" :session="session" />
            <SpaceWorkspace v-else :session="session" />
          </main>
        </div>
      </template>
    </AuthGate>
  </div>
</template>
