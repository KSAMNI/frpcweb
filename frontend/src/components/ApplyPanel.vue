<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, useDialog, useMessage } from 'naive-ui'
import { applyConfig, refreshRuntime, state } from '../api'
import Icon from './Icon.vue'
const dialog = useDialog()
const message = useMessage()
const applying = ref(false)
const description = computed(() => {
  if (!state.runtime.managed)
    return '本地安全模式：保存不会启动或重启 frpc。需要运行验证时，请显式启用进程管理。'
  if (state.runtime.apply_state === 'applied')
    return '已将当前连接配置应用到本控制台管理的 frpc 进程。服务是否可达请结合日志确认。'
  return '保存不会自动重启服务。确认修改完成后再应用，现有连接可能短暂中断。'
})
function apply() {
  dialog.warning({
    title: '应用已保存的配置？',
    content: '将先校验配置，再重启本控制台管理的 frpc 进程。现有连接可能短暂中断。',
    positiveText: '确认应用',
    negativeText: '取消',
    onPositiveClick: async () => {
      applying.value = true
      try {
        await applyConfig()
        message.success('配置已应用，frpc 进程已启动；请结合日志检查代理连接')
      } catch (error) {
        message.error((error as Error).message)
        await refreshRuntime().catch(() => {})
        return false
      } finally {
        applying.value = false
      }
    },
  })
}
</script>
<template>
  <section class="apply-panel">
    <div class="apply-icon"><Icon name="ShieldCheck" :size="22" /></div>
    <div>
      <strong>
        {{
          !state.runtime.managed
            ? '安全编辑，不打断连接'
            : state.runtime.apply_state === 'applied'
              ? '当前配置已应用'
              : '配置保存与服务应用分开进行'
        }}
      </strong>
      <p>{{ description }}</p>
      <p v-if="state.runtime.last_error" class="error-text">{{ state.runtime.last_error }}</p>
    </div>
    <NButton :disabled="!state.runtime.managed" :loading="applying" @click="apply">应用配置</NButton>
  </section>
</template>
