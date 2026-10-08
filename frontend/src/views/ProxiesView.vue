<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import {
  NButton,
  NDataTable,
  NEmpty,
  NInput,
  NSelect,
  NTag,
  useDialog,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'
import { address, deleteProxy, groupOptions, saveGroups, state } from '../api'
import type { ProxyConfig } from '../types'
import ApplyPanel from '../components/ApplyPanel.vue'
import ProxyDrawer from '../components/ProxyDrawer.vue'
import Icon from '../components/Icon.vue'
import GroupSelect from '../components/GroupSelect.vue'
const search = ref('')
const type = ref('all')
const visibility = ref('all')
const groupFilter = ref<string | null>(null)
const checked = ref<string[]>([])
const batchGroup = ref('')
const grouping = ref(false)
const groupFilters = computed(() =>
  groupOptions.value.map((option) => ({
    ...option,
    label: `${option.label} (${state.proxies.filter((p) => p.group === option.value).length})`,
  })),
)
const drawer = ref(false)
const selected = ref<ProxyConfig | null>(null)
const cloning = ref(false)
const deleting = ref('')
const dialog = useDialog()
const message = useMessage()
const filtered = computed(() =>
  state.proxies.filter(
    (p) =>
      (type.value === 'all' || p.type === type.value) &&
      (groupFilter.value === null || p.group === groupFilter.value) &&
      (visibility.value === 'all' || p.visible === (visibility.value === 'visible')) &&
      `${p.name} ${p.display_name} ${p.group} ${p.local_ip} ${p.local_port} ${p.remote_port}`
        .toLowerCase()
        .includes(search.value.toLowerCase()),
  ),
)
// Never silently apply a batch operation to rows hidden by a changed filter.
watch([search, type, visibility, groupFilter], () => {
  checked.value = []
})
watch(filtered, (proxies) => {
  const names = new Set(proxies.map((p) => p.name))
  checked.value = checked.value.filter((name) => names.has(name))
})
async function changeGroups(names: string[], group: string, batch = false) {
  if (grouping.value || !names.length) return
  grouping.value = true
  try {
    await saveGroups([...names], group)
    if (batch) checked.value = []
    message.success('分组已更新，首页立即生效，无需重启 frpc')
  } catch (error) {
    message.error((error as Error).message)
  } finally {
    grouping.value = false
  }
}
function edit(proxy: ProxyConfig | null = null, clone = false) {
  selected.value = proxy
  cloning.value = clone
  drawer.value = true
}
function remove(proxy: ProxyConfig) {
  dialog.warning({
    title: `删除“${proxy.display_name}”？`,
    content: '将从配置及首页移除此代理。删除保存后，仍需应用配置才会停止对应连接。',
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      deleting.value = proxy.name
      try {
        await deleteProxy(proxy.name)
        message.success('代理已删除；请按需应用配置')
      } catch (error) {
        message.error((error as Error).message)
        return false
      } finally {
        deleting.value = ''
      }
    },
  })
}
const columns: DataTableColumns<ProxyConfig> = [
  { type: 'selection', disabled: () => grouping.value },
  {
    title: '服务 / 代理名称',
    key: 'display_name',
    minWidth: 180,
    sorter: 'default',
    render: (p) =>
      h('div', { class: 'table-name' }, [
        h('span', { class: 'table-avatar' }, h(Icon, { name: 'Box', size: 18 })),
        h('div', {}, [h('strong', {}, p.display_name), h('small', {}, p.name)]),
      ]),
  },
  {
    title: '分组 · 直接修改',
    key: 'group',
    width: 190,
    render: (p) =>
      h(GroupSelect, {
        modelValue: p.group,
        label: `${p.display_name} 的分组`,
        size: 'small',
        disabled: grouping.value,
        'onUpdate:modelValue': (group: string) => changeGroups([p.name], group),
      }),
  },
  {
    title: '协议',
    key: 'type',
    width: 86,
    render: (p) =>
      h(
        NTag,
        { size: 'small', bordered: false, type: p.type === 'tcp' ? 'info' : 'warning' },
        { default: () => p.type.toUpperCase() },
      ),
  },
  {
    title: '本地地址',
    key: 'local_ip',
    minWidth: 180,
    render: (p) => h('code', { class: 'table-code' }, address(p.local_ip, p.local_port)),
  },
  {
    title: '远程端口',
    key: 'remote_port',
    width: 115,
    sorter: (a, b) => (a.remote_port ?? 0) - (b.remote_port ?? 0),
    render: (p) => h('code', { class: 'port-pill' }, String(p.remote_port ?? '—')),
  },
  {
    title: '首页展示',
    key: 'visible',
    width: 100,
    render: (p) =>
      h('span', { class: p.visible ? 'visibility-label' : 'muted' }, p.visible ? '● 已显示' : '已隐藏'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 195,
    fixed: 'right',
    render: (p) =>
      h('div', { class: 'table-actions' }, [
        h(
          NButton,
          { size: 'small', quaternary: true, type: 'primary', disabled: !p.editable, onClick: () => edit(p) },
          { default: () => (p.editable ? '编辑' : '只读') },
        ),
        h(
          NButton,
          { size: 'small', quaternary: true, disabled: !p.editable, onClick: () => edit(p, true) },
          { default: () => '复制' },
        ),
        h(
          NButton,
          {
            size: 'small',
            quaternary: true,
            type: 'error',
            loading: deleting.value === p.name,
            onClick: () => remove(p),
          },
          { default: () => '删除' },
        ),
      ]),
  },
]
</script>

<template>
  <ApplyPanel />
  <section class="table-panel">
    <div class="section-heading">
      <div>
        <h2>
          代理配置
          <span class="count-badge">{{ state.proxies.length }}</span>
        </h2>
        <p>直接修改分组，或勾选多个代理批量归类</p>
      </div>
      <NButton type="primary" @click="edit()">
        <template #icon><Icon name="Plus" /></template>
        新增代理
      </NButton>
    </div>
    <div class="table-toolbar">
      <NInput
        v-model:value="search"
        clearable
        placeholder="搜索名称、分组、IP 或端口"
        aria-label="搜索代理"
        class="search-input"
      >
        <template #prefix><Icon name="Search" :size="16" /></template>
      </NInput>
      <NSelect
        v-model:value="groupFilter"
        :options="groupFilters"
        clearable
        filterable
        placeholder="全部分组"
        aria-label="筛选分组"
        :input-props="{ 'aria-label': '筛选分组' }"
        class="filter-select"
      />
      <NSelect
        v-model:value="type"
        aria-label="筛选协议"
        :options="[
          { label: '全部协议', value: 'all' },
          { label: 'TCP', value: 'tcp' },
          { label: 'UDP', value: 'udp' },
        ]"
        class="filter-select"
      />
      <NSelect
        v-model:value="visibility"
        aria-label="筛选展示状态"
        :options="[
          { label: '全部展示状态', value: 'all' },
          { label: '首页显示', value: 'visible' },
          { label: '首页隐藏', value: 'hidden' },
        ]"
        class="filter-select"
      />
    </div>
    <div v-if="checked.length" class="batch-group-toolbar" role="region" aria-label="批量分组">
      <strong>已选 {{ checked.length }} 个代理</strong>
      <GroupSelect
        v-model="batchGroup"
        label="批量目标分组"
        :disabled="grouping"
        class="batch-group-select"
      />
      <NButton type="primary" :loading="grouping" @click="changeGroups(checked, batchGroup, true)">
        {{ batchGroup ? '移动到分组' : '移至未分组' }}
      </NButton>
      <NButton :disabled="grouping" @click="checked = []">取消选择</NButton>
      <small>支持跨页选择；切换筛选会清空选择</small>
    </div>
    <NDataTable
      v-model:checked-row-keys="checked"
      :columns="columns"
      :data="filtered"
      :row-key="(row: ProxyConfig) => row.name"
      :bordered="false"
      :scroll-x="1180"
      :pagination="{ defaultPageSize: 12, showSizePicker: true, pageSizes: [12, 24, 48] }"
    >
      <template #empty>
        <NEmpty
          :description="
            state.proxies.length ? '没有匹配的代理，试试调整筛选条件' : '还没有代理，从一个常用模板开始'
          "
        >
          <template #extra>
            <NButton v-if="!state.proxies.length" @click="edit()">添加第一个代理</NButton>
          </template>
        </NEmpty>
      </template>
    </NDataTable>
    <div class="table-footnote">
      <Icon name="ShieldCheck" :size="15" />
      分组修改立即生效，无需应用配置。连接规则编辑支持 TCP / UDP；其他协议也可分组，原连接配置保持只读。
    </div>
  </section>
  <ProxyDrawer v-model:show="drawer" :proxy="selected" :clone="cloning" />
</template>
