export interface ProxyConfig {
  name: string
  type: string
  local_ip: string
  local_port: number | null
  remote_port: number | null
  display_name: string
  visible: boolean
  group: string
  favorite: boolean
  access_url: string
  editable: boolean
}
export type ProxyDraft = Omit<ProxyConfig, 'editable'>
export interface Runtime {
  managed: boolean
  running: boolean
  apply_state: 'unknown' | 'pending' | 'applied'
  last_error: string | null
}
export interface State {
  proxies: ProxyConfig[]
  target_ip: string
  revision: string
  frpc_revision: string
  csrf_token: string
  runtime: Runtime
}
