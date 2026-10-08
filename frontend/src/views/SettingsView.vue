<script setup lang="ts">
import { ref } from 'vue'
import { NAlert, NButton, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import { ApiError, saveSettings, state } from '../api'
import ApplyPanel from '../components/ApplyPanel.vue'
import Icon from '../components/Icon.vue'
const target = ref(state.target_ip)
const revision = ref(state.revision)
const error = ref('')
const saving = ref(false)
const message = useMessage()
async function save() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    await saveSettings(target.value.trim(), revision.value)
    revision.value = state.revision
    message.success('访问地址已保存，无需重启 frpc')
  } catch (e) {
    error.value = e instanceof ApiError ? e.fields.target_ip || e.message : (e as Error).message
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <div class="settings-grid">
    <section class="settings-panel">
      <div class="section-heading">
        <div>
          <h2>服务访问地址</h2>
          <p>代理默认使用此地址 + 各自的远程端口</p>
        </div>
        <div class="stat-icon teal"><Icon name="Globe" :size="21" /></div>
      </div>
      <NForm @submit.prevent="save">
        <NFormItem label="目标 IP / 域名" :feedback="error" :validation-status="error ? 'error' : undefined">
          <NInput
            v-model:value="target"
            placeholder="例如 192.168.1.100 或 example.com"
            :input-props="{ 'aria-label': '目标地址' }"
          />
        </NFormItem>
        <p class="field-help">
          只填写 IP 或域名，不含协议、端口和路径。未设置自定义链接的 Web 入口自动使用
          http://此地址:远程端口；保存后立即更新，无需逐个编辑代理。不会修改 frpc 的
          serverAddr，也不会覆盖已设置的自定义 Web 链接。
        </p>
        <NButton type="primary" attr-type="submit" :loading="saving">保存地址</NButton>
      </NForm>
    </section>
    <section class="settings-note">
      <Icon name="ShieldCheck" :size="27" />
      <h3>你的配置，仍在本地</h3>
      <p>
        连接规则继续保存在
        <code>frpc.toml</code>
        ，显示名称、分组和收藏保存在
        <code>app_config.json</code>
        。
      </p>
      <p>编辑现有代理时，未展示的高级字段会保留。TOML 重新序列化可能改变格式和注释，重要配置请先备份。</p>
    </section>
  </div>
  <section class="settings-panel runtime-settings">
    <div class="section-heading">
      <div>
        <h2>frpc 运行管理</h2>
        <p>显式应用，避免编辑过程中反复中断连接</p>
      </div>
    </div>
    <ApplyPanel />
    <div class="runtime-detail">
      <span>进程管理</span>
      <strong>{{ state.runtime.managed ? '已启用' : '未启用 · 本地安全模式' }}</strong>
    </div>
    <div class="runtime-detail">
      <span>控制台管理的进程</span>
      <strong>{{ state.runtime.running ? '运行中' : '未运行' }}</strong>
    </div>
    <NAlert type="info" :bordered="false">
      本地测试默认不启动 frpc。如需验证实际连接，请配置适合操作系统的 FRPC_BIN，并显式设置
      FRPC_MANAGE=1。不会接管或停止控制台之外启动的进程。
    </NAlert>
  </section>
  <div class="info-strip">
    <Icon name="ShieldCheck" :size="18" />
    <span>本版本未内置登录系统。请仅用于可信网络；公网部署必须在反向代理层配置身份认证与 HTTPS。</span>
  </div>
</template>
