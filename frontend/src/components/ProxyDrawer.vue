<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
  useDialog,
  useMessage,
} from 'naive-ui'
import { ApiError, address, saveProxy, state } from '../api'
import type { ProxyConfig, ProxyDraft } from '../types'
import Icon from './Icon.vue'
const props = defineProps<{ show: boolean; proxy: ProxyConfig | null; clone: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean] }>()
const message = useMessage()
const dialog = useDialog()
const draft = reactive<ProxyDraft>(empty())
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const errorMessage = ref('')
const initial = ref('')
const baseRevision = ref('')
const original = ref<string | null>(null)
const template = ref('custom')
const templates = [
  { label: '自定义', value: 'custom' },
  { label: 'Web 服务', value: 'web' },
  { label: 'SSH 连接', value: 'ssh' },
  { label: '远程桌面', value: 'rdp' },
  { label: 'UDP 服务', value: 'udp' },
]
function empty(): ProxyDraft {
  return {
    name: '',
    type: 'tcp',
    local_ip: '127.0.0.1',
    local_port: null,
    remote_port: null,
    display_name: '',
    visible: true,
    group: '',
    favorite: false,
    access_url: '',
  }
}
const title = computed(() => (original.value ? '编辑代理' : props.clone ? '复制代理' : '新增代理'))
watch(
  () => props.show,
  (show) => {
    if (!show) return
    Object.assign(draft, empty(), props.proxy || {})
    original.value = props.proxy && !props.clone ? props.proxy.name : null
    if (props.clone && props.proxy) {
      let name = `${props.proxy.name}-copy`
      let suffix = 2
      while (state.proxies.some((p) => p.name === name)) name = `${props.proxy.name}-copy-${suffix++}`
      draft.name = name
      draft.display_name = `${props.proxy.display_name} 副本`
      draft.remote_port = null
      draft.access_url = ''
    }
    baseRevision.value = state.revision
    initial.value = JSON.stringify(draft)
    errors.value = {}
    errorMessage.value = ''
    template.value = 'custom'
  },
)
function selectTemplate(value: string) {
  template.value = value
  draft.type = value === 'udp' ? 'udp' : 'tcp'
  draft.local_port = ({ web: 80, ssh: 22, rdp: 3389 } as Record<string, number>)[value] ?? null
  if (value !== 'web') draft.access_url = ''
}
function suggestUrl() {
  if (!draft.remote_port) {
    message.info('请先填写远程端口')
    return
  }
  draft.access_url = `http://${address(state.target_ip, draft.remote_port)}`
}
function close() {
  if (saving.value) return
  if (JSON.stringify(draft) !== initial.value) {
    dialog.warning({
      title: '放弃未保存的修改？',
      content: '关闭后本次输入不会保存。',
      positiveText: '放弃修改',
      negativeText: '继续编辑',
      onPositiveClick: () => emit('update:show', false),
    })
  } else emit('update:show', false)
}
function validate() {
  const result: Record<string, string> = {}
  if (!draft.name.trim()) result.name = '请填写代理名称'
  if (!draft.local_ip.trim()) result.local_ip = '请填写本地 IP 或主机名'
  for (const key of ['local_port', 'remote_port'] as const) {
    const port = draft[key]
    if (port === null || !Number.isInteger(port) || port < 1 || port > 65535)
      result[key] = '填写 1–65535 的整数端口'
  }
  errors.value = result
  return !Object.keys(result).length
}
async function save(keepOpen = false) {
  if (saving.value || !validate()) return
  saving.value = true
  errorMessage.value = ''
  try {
    await saveProxy(
      {
        ...draft,
        name: draft.name.trim(),
        local_ip: draft.local_ip.trim(),
        display_name: draft.display_name.trim(),
        group: draft.group.trim(),
        access_url: draft.access_url.trim(),
      },
      original.value,
      baseRevision.value,
    )
    message.success('配置已保存。首页展示立即更新；连接配置需单独应用。')
    if (keepOpen && !original.value) {
      const { local_ip, type, group } = draft
      Object.assign(draft, empty(), { local_ip, type, group })
      initial.value = JSON.stringify(draft)
      baseRevision.value = state.revision
      errors.value = {}
      template.value = 'custom'
    } else emit('update:show', false)
  } catch (error) {
    errorMessage.value = (error as Error).message
    if (error instanceof ApiError) errors.value = error.fields
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <NDrawer :show="show" width="min(560px, 100vw)" :mask-closable="false" @update:show="close">
    <NDrawerContent :title="title" :native-scrollbar="false">
      <template #header>
        <div class="drawer-heading">
          <span>{{ title }}</span>
          <NButton quaternary circle :disabled="saving" aria-label="关闭编辑抽屉" @click="close">
            <template #icon><Icon name="X" /></template>
          </NButton>
        </div>
      </template>
      <NAlert v-if="clone" type="info" :bordered="false" class="page-alert">
        复制基础配置和展示信息，不复制原代理的高级 FRP 参数。请指定新的远程端口。
      </NAlert>
      <NAlert v-if="errorMessage" type="error" class="page-alert">{{ errorMessage }}</NAlert>
      <NForm :model="draft" label-placement="top" :show-require-mark="false" @submit.prevent="save()">
        <template v-if="!original">
          <div class="form-section-title">从一个模板开始</div>
          <NSelect
            :value="template"
            :options="templates"
            aria-label="代理模板"
            @update:value="selectTemplate"
          />
          <p class="field-help">模板仅预填常用端口，不会自动启动或探测服务。</p>
        </template>
        <div class="form-section-title">
          连接配置
          <span>01</span>
        </div>
        <NFormItem
          label="代理名称"
          :feedback="errors.name"
          :validation-status="errors.name ? 'error' : undefined"
        >
          <NInput
            v-model:value="draft.name"
            placeholder="例如 nas-web，需保持唯一"
            :maxlength="100"
            :input-props="{ 'aria-label': '代理名称' }"
          />
        </NFormItem>
        <div class="form-grid">
          <NFormItem
            label="协议"
            :feedback="errors.type"
            :validation-status="errors.type ? 'error' : undefined"
          >
            <NSelect
              v-model:value="draft.type"
              :options="[
                { label: 'TCP', value: 'tcp' },
                { label: 'UDP', value: 'udp' },
              ]"
              aria-label="协议"
            />
          </NFormItem>
          <NFormItem
            label="本地 IP / 主机名"
            :feedback="errors.local_ip"
            :validation-status="errors.local_ip ? 'error' : undefined"
          >
            <NInput
              v-model:value="draft.local_ip"
              placeholder="127.0.0.1"
              :input-props="{ 'aria-label': '本地地址' }"
            />
          </NFormItem>
        </div>
        <div class="form-grid">
          <NFormItem
            label="本地端口"
            :feedback="errors.local_port"
            :validation-status="errors.local_port ? 'error' : undefined"
          >
            <NInputNumber
              v-model:value="draft.local_port"
              :min="1"
              :max="65535"
              :precision="0"
              :show-button="false"
              placeholder="服务实际监听端口"
              :input-props="{ 'aria-label': '本地端口' }"
            />
          </NFormItem>
          <NFormItem
            label="远程端口"
            :feedback="errors.remote_port"
            :validation-status="errors.remote_port ? 'error' : undefined"
          >
            <NInputNumber
              v-model:value="draft.remote_port"
              :min="1"
              :max="65535"
              :precision="0"
              :show-button="false"
              placeholder="frps 对外访问端口"
              :input-props="{ 'aria-label': '远程端口' }"
            />
          </NFormItem>
        </div>
        <div class="mapping-preview">
          <span>本地 {{ address(draft.local_ip || '…', draft.local_port) }}</span>
          <Icon name="ArrowRight" :size="16" />
          <span>远程 {{ draft.remote_port || '…' }}</span>
        </div>
        <div class="form-section-title">
          首页展示
          <span>02</span>
        </div>
        <div class="form-grid">
          <NFormItem
            label="显示名称"
            :feedback="errors.display_name"
            :validation-status="errors.display_name ? 'error' : undefined"
          >
            <NInput
              v-model:value="draft.display_name"
              placeholder="例如 我的 NAS（选填）"
              :maxlength="100"
              :input-props="{ 'aria-label': '显示名称' }"
            />
          </NFormItem>
          <NFormItem
            label="分组"
            :feedback="errors.group"
            :validation-status="errors.group ? 'error' : undefined"
          >
            <NInput
              v-model:value="draft.group"
              placeholder="例如 家庭服务（选填）"
              :maxlength="50"
              :input-props="{ 'aria-label': '分组' }"
            />
          </NFormItem>
        </div>
        <NFormItem
          label="Web 访问地址（可选）"
          :feedback="errors.access_url"
          :validation-status="errors.access_url ? 'error' : undefined"
        >
          <div class="full-width">
            <NInput
              v-model:value="draft.access_url"
              placeholder="https://nas.example.com"
              :input-props="{ 'aria-label': 'Web 访问地址' }"
            />
            <div class="field-help">
              仅 Web 服务需要填写。
              <button type="button" class="text-button" @click="suggestUrl">
                根据目标地址生成 HTTP 链接
              </button>
            </div>
          </div>
        </NFormItem>
        <div class="switch-row">
          <div>
            <strong>在首页显示</strong>
            <small>作为服务快捷入口展示</small>
          </div>
          <NSwitch v-model:value="draft.visible" aria-label="在首页显示" />
        </div>
        <div class="switch-row">
          <div>
            <strong>加入收藏</strong>
            <small>在首页快速筛选常用服务</small>
          </div>
          <NSwitch v-model:value="draft.favorite" aria-label="加入收藏" />
        </div>
        <p class="field-help" v-if="original">未在表单中展示的高级 FRP 参数会原样保留。</p>
        <button type="submit" class="sr-only" tabindex="-1">保存配置</button>
      </NForm>
      <template #footer>
        <div class="drawer-footer">
          <NButton :disabled="saving" @click="close">取消</NButton>
          <div>
            <NButton v-if="!original" :disabled="saving" @click="save(true)">保存并继续添加</NButton>
            <NButton type="primary" :loading="saving" @click="save()">保存配置</NButton>
          </div>
        </div>
      </template>
    </NDrawerContent>
  </NDrawer>
</template>
