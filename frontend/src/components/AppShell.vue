<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NAlert, NButton, NSkeleton, NTag, useMessage } from 'naive-ui'
import { loaded, loadError, refresh, refreshing, refreshRuntime, state } from '../api'
import Icon from './Icon.vue'
const route = useRoute()
const message = useMessage()
const menuOpen = ref(false)
const nav = [
  { path: '/', title: '服务入口', icon: 'LayoutGrid' },
  { path: '/config', title: '代理管理', icon: 'Network' },
  { path: '/settings', title: '运行设置', icon: 'Settings2' },
  { path: '/logs', title: '运行日志', icon: 'ScrollText' },
]
const applyLabel = computed(
  () =>
    ({ unknown: '应用状态未知', pending: '有待应用配置', applied: '配置已应用' })[state.runtime.apply_state],
)
async function reload() {
  try {
    await refresh()
  } catch (error) {
    message.error((error as Error).message)
  }
}
let timer: ReturnType<typeof setInterval>
onMounted(() => {
  void reload()
  timer = setInterval(() => {
    if (loaded.value && !document.hidden)
      void refreshRuntime().catch(() => {
        /* Preserve data; explicit refresh reports connection failures. */
      })
  }, 15000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="app-layout">
    <button v-if="menuOpen" class="sidebar-scrim" aria-label="关闭导航" @click="menuOpen = false" />
    <aside class="sidebar" :class="{ open: menuOpen }">
      <RouterLink to="/" class="brand" @click="menuOpen = false">
        <span class="brand-mark"><Icon name="Network" :size="24" /></span>
        <span>
          FRP
          <strong>Console</strong>
          <small>连接你的每一项服务</small>
        </span>
      </RouterLink>
      <div class="nav-caption">工作空间</div>
      <nav aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: route.path === item.path }"
          @click="menuOpen = false"
        >
          <Icon :name="item.icon" />
          <span>{{ item.title }}</span>
          <span v-if="item.path === '/config' && loaded" class="nav-count">{{ state.proxies.length }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-bottom">
        <div class="connection-label">
          <span class="status-dot" :class="{ live: state.runtime.running }" />
          {{
            state.runtime.running
              ? 'frpc 进程运行中'
              : state.runtime.managed
                ? 'frpc 进程未运行'
                : '本地安全模式'
          }}
        </div>
        <p>{{ state.runtime.managed ? '进程状态不代表服务可达性' : '允许保存配置，不自动重启服务' }}</p>
        <div class="sidebar-footer">
          <Icon name="ShieldCheck" :size="15" />
          自托管 · 轻量控制台
        </div>
      </div>
    </aside>
    <div class="main-column">
      <header class="topbar">
        <div class="breadcrumbs">
          <button class="mobile-menu icon-control" aria-label="打开导航" @click="menuOpen = true">
            <Icon name="Menu" />
          </button>
          <span>工作空间</span>
          <Icon name="ChevronRight" :size="14" />
          <strong>{{ route.meta.title }}</strong>
        </div>
        <div class="topbar-actions">
          <NTag
            v-if="loaded"
            :type="state.runtime.apply_state === 'applied' ? 'success' : 'default'"
            size="small"
            round
            :bordered="false"
          >
            {{ applyLabel }}
          </NTag>
          <NButton quaternary circle :loading="refreshing" aria-label="刷新数据" @click="reload">
            <template #icon><Icon name="RefreshCw" /></template>
          </NButton>
          <span class="avatar">FR</span>
        </div>
      </header>
      <main class="main-content" :class="{ 'launcher-content': route.path === '/' }" id="main-content">
        <div v-if="route.path !== '/'" class="page-heading">
          <div>
            <div class="eyebrow">YOUR CONNECTIONS, SIMPLIFIED</div>
            <h1>{{ route.meta.title }}</h1>
            <p>{{ route.meta.subtitle }}</p>
          </div>
        </div>
        <NAlert v-if="loadError" type="error" title="数据加载失败" class="page-alert">
          <span>{{ loadError }}</span>
          <NButton size="small" :loading="refreshing" @click="reload">重试</NButton>
        </NAlert>
        <template v-if="!loaded && !loadError">
          <NSkeleton :height="route.path === '/' ? '42px' : '112px'" :sharp="false" />
          <NSkeleton height="240px" :sharp="false" style="margin-top: 24px" />
        </template>
        <RouterView v-if="loaded" />
        <footer class="page-footer">
          <span>FRP Console</span>
          <span>简单管理，自由连接。</span>
        </footer>
      </main>
    </div>
  </div>
</template>
