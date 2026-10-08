<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { NAlert, NButton, NSwitch } from 'naive-ui'
import { fetchLogs } from '../api'
import Icon from '../components/Icon.vue'
const log = ref('')
const loading = ref(false)
const autoRefresh = ref(false)
const truncated = ref(false)
const error = ref('')
const updated = ref('')
async function load() {
  if (loading.value) return
  loading.value = true
  try {
    const result = await fetchLogs()
    log.value = result.log
    truncated.value = result.truncated
    error.value = ''
    updated.value = new Date().toLocaleTimeString('zh-CN')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
let timer: ReturnType<typeof setInterval>
onMounted(() => {
  void load()
  timer = setInterval(() => {
    if (autoRefresh.value && !document.hidden) void load()
  }, 5000)
})
onUnmounted(() => clearInterval(timer))
</script>
<template>
  <section class="logs-panel">
    <div class="section-heading">
      <div>
        <h2>frpc 输出</h2>
        <p>最近 32 KB · {{ updated ? `更新于 ${updated}` : '等待加载' }}</p>
      </div>
      <div class="log-actions">
        <label class="auto-refresh">
          自动刷新
          <NSwitch v-model:value="autoRefresh" size="small" aria-label="自动刷新日志" />
        </label>
        <NButton :loading="loading" @click="load">
          <template #icon><Icon name="RefreshCw" :size="16" /></template>
          刷新日志
        </NButton>
      </div>
    </div>
    <NAlert v-if="error" type="error" class="page-alert">{{ error }}</NAlert>
    <div class="terminal-header">
      <span />
      <span />
      <span />
      <code>frpc · output</code>
    </div>
    <pre class="log-output" tabindex="0" aria-label="日志内容">{{ log || '正在读取日志…' }}</pre>
    <p class="field-help">
      {{ truncated ? '日志较长，已截取文件末尾 32 KB。' : '显示当前日志内容。' }} 自动刷新每 5
      秒执行一次，切换到后台标签时暂停。
    </p>
  </section>
</template>
