<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NEmpty, NInput, NTag, useMessage } from 'naive-ui'
import { address, safeWebUrl, saveProxy, state } from '../api'
import type { ProxyConfig } from '../types'
import Icon from '../components/Icon.vue'
import '../launcher.css'

const search = ref('')
const group = ref<string | null>(null)
const favoriteOnly = ref(false)
const saving = ref(false)
const message = useMessage()
const visible = computed(() => state.proxies.filter((p) => p.visible))
const groups = computed(() => [
  { label: '全部服务', value: null, count: visible.value.length },
  ...[...new Set(visible.value.map((p) => p.group))].map((name) => ({
    label: name || '未分组',
    value: name,
    count: visible.value.filter((p) => p.group === name).length,
  })),
])
const filtered = computed(() =>
  visible.value.filter(
    (p) =>
      (group.value === null || p.group === group.value) &&
      (!favoriteOnly.value || p.favorite) &&
      `${p.display_name} ${p.name} ${p.local_ip} ${p.remote_port ?? ''} ${p.access_url} ${p.group}`
        .toLowerCase()
        .includes(search.value.trim().toLowerCase()),
  ),
)
function entryAddress(proxy: ProxyConfig) {
  return safeWebUrl(proxy.access_url) || address(state.target_ip, proxy.remote_port)
}
async function copy(proxy: ProxyConfig) {
  const value = entryAddress(proxy)
  try {
    await navigator.clipboard.writeText(value)
    message.success('访问地址已复制')
  } catch {
    message.warning(`无法访问剪贴板，请手动复制：${value}`)
  }
}
async function favorite(proxy: ProxyConfig) {
  if (saving.value) return
  saving.value = true
  try {
    await saveProxy({ ...proxy, favorite: !proxy.favorite }, proxy.name, state.revision)
  } catch (error) {
    message.error((error as Error).message)
  } finally {
    saving.value = false
  }
}
function clearFilters() {
  search.value = ''
  group.value = null
  favoriteOnly.value = false
}
function serviceKind(proxy: ProxyConfig) {
  if (safeWebUrl(proxy.access_url)) return { icon: 'Globe', label: 'Web 应用' }
  if (proxy.local_port === 22) return { icon: 'Terminal', label: 'SSH 终端' }
  if (proxy.local_port === 3389) return { icon: 'Monitor', label: '远程桌面' }
  if ([3306, 5432, 6379, 27017].includes(proxy.local_port ?? 0))
    return { icon: 'Database', label: '数据服务' }
  if (proxy.type === 'udp') return { icon: 'Network', label: 'UDP 服务' }
  return { icon: 'Box', label: '网络服务' }
}
// Stable group colors without external favicons or extra network requests.
function serviceTone(proxy: ProxyConfig) {
  const key = proxy.group || proxy.name
  const hash = Array.from(key).reduce((value, char) => (value * 31 + char.charCodeAt(0)) >>> 0, 0)
  return ['teal', 'blue', 'violet', 'amber', 'rose'][hash % 5]
}
</script>

<template>
  <section class="service-section" aria-labelledby="launcher-title">
    <div class="launcher-toolbar">
      <div class="launcher-heading">
        <h1 id="launcher-title">我的服务</h1>
        <span class="launcher-count" role="status">{{ filtered.length }} 个入口</span>
      </div>
      <div class="launcher-tools">
        <NInput
          v-model:value="search"
          clearable
          placeholder="搜索服务、地址或端口"
          :input-props="{ 'aria-label': '搜索服务' }"
          class="launcher-search"
        >
          <template #prefix><Icon name="Search" :size="17" /></template>
        </NInput>
        <RouterLink to="/config" class="primary-link launcher-add">
          <Icon name="Plus" :size="17" />
          添加服务
        </RouterLink>
      </div>
    </div>
    <div class="service-filters">
      <div class="group-tabs" role="group" aria-label="服务分组">
        <button
          v-for="item in groups"
          :key="item.value === null ? 'all' : `group:${item.value}`"
          :class="{ selected: group === item.value }"
          :aria-pressed="group === item.value"
          @click="group = item.value"
        >
          {{ item.label }}
          <span class="group-count" aria-hidden="true">{{ item.count }}</span>
        </button>
      </div>
      <button
        class="favorite-filter"
        :class="{ selected: favoriteOnly }"
        :aria-pressed="favoriteOnly"
        @click="favoriteOnly = !favoriteOnly"
      >
        <Icon name="Star" :size="15" />
        只看收藏
      </button>
    </div>
    <div v-if="filtered.length" class="service-grid">
      <article
        v-for="proxy in filtered"
        :key="proxy.name"
        class="service-card"
        :class="`tone-${serviceTone(proxy)}`"
        :aria-label="proxy.display_name"
      >
        <div class="service-card-top">
          <div class="service-icon">
            <Icon :name="serviceKind(proxy).icon" :size="24" />
          </div>
          <div class="service-identity">
            <h2 :title="proxy.display_name">{{ proxy.display_name }}</h2>
            <p class="service-description">
              <span class="service-group" :title="proxy.group || '未分组'">
                {{ proxy.group || '未分组' }}
              </span>
              <span>{{ serviceKind(proxy).label }}</span>
            </p>
          </div>
          <button
            v-if="proxy.editable"
            class="star-button icon-control"
            :class="{ starred: proxy.favorite }"
            :disabled="saving"
            :aria-label="`${proxy.favorite ? '取消收藏' : '收藏'} ${proxy.display_name}`"
            :aria-pressed="proxy.favorite"
            @click="favorite(proxy)"
          >
            <Icon name="Star" :size="17" />
          </button>
          <NTag v-else size="small" :bordered="false">只读</NTag>
        </div>
        <div class="service-address" :title="entryAddress(proxy)">
          <span class="service-protocol">{{ proxy.type.toUpperCase() }}</span>
          <code>
            {{
              entryAddress(proxy)
                .replace(/^https?:\/\//, '')
                .replace(/\/$/, '')
            }}
          </code>
        </div>
        <div class="service-card-bottom">
          <button
            v-if="safeWebUrl(proxy.access_url)"
            class="icon-control service-copy"
            :aria-label="`复制 ${proxy.display_name} 地址`"
            @click="copy(proxy)"
          >
            <Icon name="Copy" :size="15" />
          </button>
          <span v-if="!safeWebUrl(proxy.access_url)" class="service-hint">
            {{ proxy.type === 'udp' ? 'UDP 客户端连接' : '在客户端中连接' }}
          </span>
          <div class="service-card-actions">
            <a
              v-if="safeWebUrl(proxy.access_url)"
              :href="safeWebUrl(proxy.access_url)"
              target="_blank"
              rel="noopener noreferrer"
              class="service-open"
              :title="`${proxy.display_name} · ${entryAddress(proxy)}`"
            >
              打开服务
              <span class="sr-only">：{{ proxy.display_name }}</span>
              <Icon name="ArrowUpRight" :size="17" />
            </a>
            <button
              v-else
              class="service-open copy-main"
              :title="`${proxy.display_name} · ${entryAddress(proxy)}`"
              @click="copy(proxy)"
            >
              复制地址
              <span class="sr-only">：{{ proxy.display_name }}</span>
              <Icon name="Copy" :size="15" />
            </button>
          </div>
        </div>
      </article>
    </div>
    <div v-else class="empty-panel">
      <NEmpty :description="visible.length ? '没有找到匹配的服务' : '还没有服务入口，添加第一个代理吧'">
        <template #extra>
          <RouterLink v-if="!visible.length" to="/config" class="primary-link">
            <Icon name="Plus" :size="16" />
            添加代理
          </RouterLink>
          <NButton v-else @click="clearFilters">清除筛选</NButton>
        </template>
      </NEmpty>
    </div>
  </section>
</template>
