import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HomeView from './views/HomeView.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView, meta: { title: '服务入口', subtitle: '你的服务，一触即达。' } },
    {
      path: '/config',
      component: () => import('./views/ProxiesView.vue'),
      meta: { title: '代理管理', subtitle: '让每一条连接，都井然有序。' },
    },
    {
      path: '/settings',
      component: () => import('./views/SettingsView.vue'),
      meta: { title: '运行设置', subtitle: '管理访问地址与配置的应用状态。' },
    },
    {
      path: '/logs',
      component: () => import('./views/LogsView.vue'),
      meta: { title: '运行日志', subtitle: '查看 frpc 的最近输出，定位连接问题。' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
router.afterEach((to) => {
  document.title = `${String(to.meta.title)} · FRP Console`
})
createApp(App).use(router).mount('#app')
