import { reactive, ref } from 'vue'
import type { ProxyDraft, State, Runtime } from './types'

export const state = reactive<State>({
  proxies: [],
  target_ip: '',
  revision: '',
  frpc_revision: '',
  csrf_token: '',
  runtime: { managed: false, running: false, apply_state: 'unknown', last_error: null },
})
export const loaded = ref(false)
export const loadError = ref('')
export const refreshing = ref(false)

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fields: Record<string, string> = {},
  ) {
    super(message)
  }
}

async function request<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      signal: AbortSignal.timeout(30000),
      headers:
        data === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf_token },
      body: data === undefined ? undefined : JSON.stringify(data),
    })
  } catch {
    throw new ApiError('无法连接后端或请求超时，请检查服务；重试保存前请先刷新确认结果', 0)
  }
  const result = await response.json().catch(() => ({}))
  if (!response.ok)
    throw new ApiError(result.message || `请求失败 (${response.status})`, response.status, result.fields)
  return result as T
}

export async function refresh() {
  refreshing.value = true
  try {
    Object.assign(state, await request<State>('/state'))
    loaded.value = true
    loadError.value = ''
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '加载失败'
    throw error
  } finally {
    refreshing.value = false
  }
}

export async function saveProxy(draft: ProxyDraft, original: string | null, revision: string) {
  Object.assign(
    state,
    await request<State>(
      original === null ? '/proxies' : `/proxies/${encodeURIComponent(original)}`,
      original === null ? 'POST' : 'PUT',
      { ...draft, revision },
    ),
  )
}
export async function deleteProxy(name: string) {
  Object.assign(
    state,
    await request<State>(`/proxies/${encodeURIComponent(name)}`, 'DELETE', { revision: state.revision }),
  )
}
export async function saveSettings(target_ip: string, revision: string) {
  Object.assign(state, await request<State>('/settings', 'PUT', { target_ip, revision }))
}
export async function applyConfig() {
  Object.assign(state, await request<State>('/runtime/apply', 'POST', { revision: state.revision }))
}
export async function refreshRuntime() {
  state.runtime = await request<Runtime>('/runtime')
}
export function fetchLogs() {
  return request<{ log: string; truncated: boolean }>('/logs')
}
export function address(host: string, port: number | null) {
  return `${host.includes(':') ? `[${host}]` : host}${port == null ? '' : `:${port}`}`
}
export function safeWebUrl(url: string) {
  try {
    const parsed = new URL(url)
    return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password
      ? parsed.href
      : ''
  } catch {
    return ''
  }
}
