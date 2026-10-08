# FRP Console

基于 **Flask + Vue 3 + TypeScript + Vite + Naive UI** 的 frpc 配置与服务入口管理界面。

> 本地测试默认不启动、不停止、不重启 frpc；请先用配置副本验证。Docker 部署默认管理 frpc 进程，升级前请备份配置并阅读下方部署说明。

## 分组与服务入口

- **快速分组**：在代理管理列表的“分组 · 直接修改”中选择已有分组，或输入新分组后按 Enter。新增/编辑抽屉也使用同一个可搜索选择器。
- **批量分组**：勾选多个代理（支持跨页），选择目标分组后点击“移动到分组”；选择“未分组”可取消归类。改变搜索/筛选条件会清空选择，避免误改隐藏的代理。
- **立即生效**：分组仅修改 `app_config.json`，不会重写 `frpc.toml`，不需要重启或应用 frpc；只读协议也支持分组。
- **默认服务地址**：在“运行设置 → 服务访问地址”填写 IP 或域名。普通 TCP 代理未填写自定义 Web 地址时，首页自动使用 `http://服务访问地址:远程端口`，不是本地端口。修改目标地址或代理远程端口后，默认链接随之更新；IPv6 自动补方括号。
- **自定义地址优先**：HTTPS、域名反代或带路径的入口可填写完整的自定义 Web 地址。已有自定义地址不会被覆盖；编辑代理时点击“恢复默认地址”并保存，即可重新跟随运行设置。
- **非网页服务**：UDP、SSH（本地端口 22）、远程桌面（3389）、常见数据库（3306/5432/6379/27017）默认提供连接地址复制，不自动按网页打开。端口识别只是默认规则，特殊场景可用自定义 Web 地址覆盖。

## 本地试用（Windows PowerShell，推荐）

需要 Python 3.11+、Node.js 22 LTS（当前已在 22.17 上验证）、npm。

在项目根目录执行：

```powershell
.\scripts\start-local.ps1
```

脚本会：

1. 创建或复用项目 `.venv` 并安装 Python 依赖。
2. 首次运行安装前端依赖并构建静态文件。
3. **仅首次**将现有 `frpc.toml` 和 `app_config.json` 复制到 `tmp/local-test/`。
4. 使用副本启动 http://127.0.0.1:8000 ，禁用 frpc 进程管理。

后续测试会保留副本内的修改，不会重复覆盖。真实配置文件不受影响。若端口占用或前端修改后需要重建：

```powershell
.\scripts\start-local.ps1 -Port 8001 -Rebuild
```

Ctrl+C 停止。脚本不会修改系统执行策略；如本机策略禁止脚本，可按下方手动方式启动。

### 手动启动 / 热更新开发

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
npm --prefix .\frontend ci
npm --prefix .\frontend run build

New-Item -ItemType Directory -Path .\tmp\local-test -Force
# 只复制不存在的测试文件，避免覆盖之前的测试修改。
foreach ($name in @('frpc.toml', 'app_config.json')) {
    if (-not (Test-Path -LiteralPath ".\tmp\local-test\$name")) {
        Copy-Item -LiteralPath ".\$name" -Destination ".\tmp\local-test\$name"
    }
}
$env:FRPC_CONFIG = Join-Path (Get-Location) 'tmp\local-test\frpc.toml'
$env:APP_CONFIG = Join-Path (Get-Location) 'tmp\local-test\app_config.json'
$env:FRPC_LOG = Join-Path (Get-Location) 'tmp\local-test\frpc.log'
$env:FRPC_MANAGE = '0'
$env:FRPC_AUTOSTART = '0'
$env:HOST = '127.0.0.1'
$env:PORT = '8000'
.\.venv\Scripts\python.exe -B .\main.py
```

访问 http://127.0.0.1:8000 查看生产构建。开发时另开一个终端执行：

```powershell
npm --prefix .\frontend run dev
```

访问 http://127.0.0.1:5173 使用热更新；Vite 将 `/api` 代理到后端 8000 端口。开发模式后端需保持在 8000，或自行调整 `frontend/vite.config.ts`。

## 功能与交互

- **服务入口**：服务优先的紧凑启动台，分组色彩卡片、搜索、收藏；点击卡片打开 Web 应用或复制客户端地址，收藏与复制按钮独立操作。Web 地址复制使用配置的访问 URL。
- **代理管理**：紧凑列表、协议/可见性筛选、分页、新增/编辑抽屉、复制基础配置。
- **便捷添加**：Web、SSH、远程桌面、UDP 模板，字段错误反馈，保存并继续添加。
- **数据保护**：后端端口/主机名/名称/URL 校验，重名和同协议端口冲突检查，修订版本冲突返回 409，失败时保留表单。
- **明确生效状态**：保存不等于应用；首页展示信息立即更新，连接规则需要单独应用。
- **日志**：只读取最后 32 KB，可选每 5 秒刷新，页面在后台时暂停。
- **加载**：无外部字体/CDN，路由懒加载，哈希静态资源长缓存，Brotli/gzip 压缩，不再增删改后整页刷新。

### 配置兼容和已知边界

- 沿用 `frpc.toml`、`app_config.json`，保留服务器认证参数和未编辑的代理高级字段；API 不返回服务器认证信息。
- 可视化编辑当前支持 TCP / UDP。HTTP、HTTPS、STCP 等已有协议按只读方式展示，不静默转换协议。
- **复制仅复制基础字段与展示信息**，不复制隐藏的插件、认证等高级参数。
- `proxies_display` 新增可选字段：`group`、`favorite`、`accessUrl`，原有 `displayName`、`visible` 保持兼容。
- 为避免把 SSH / UDP 等误当成网页，旧代理默认提供“复制地址”。要恢复“打开服务”，请在编辑抽屉显式填写 HTTP/HTTPS 访问地址。
- 目标地址仅用于复制地址和生成链接，不修改 `serverAddr`，也不批量改写自定义链接。
- `toml` 序列化会保留数据字段，但**不保证注释和原格式**；重要配置请另行备份。
- 同协议远程端口校验仅覆盖当前文件，不代表能探测其他 frpc 客户端占用的 frps 端口。
- 文件写入优先使用同目录临时文件替换；Docker 单文件挂载无法替换时采用兼容写入。两文件写入失败会尝试回滚，但不保证掉电时跨文件事务原子性。
- 修订检查和线程锁保护单个 Web 进程的操作；请勿同时运行多个写配置的实例或外部自动写入程序。

## 真实 frpc 运行验证（显式启用）

仓库内的 `frp/frpc` 是 Linux 文件。Windows 需要自行提供对应版本的 `frpc.exe`。

在已设置测试配置路径的终端中：

```powershell
$env:FRPC_BIN = 'C:\Tools\frp\frpc.exe'
$env:FRPC_MANAGE = '1'
$env:FRPC_AUTOSTART = '0'
.\.venv\Scripts\python.exe -B .\main.py
```

在界面点击“应用配置”并确认。后端先运行 `frpc verify -c ...`，成功后重启**当前控制台拥有的进程**。需使用支持该命令的 frpc 版本。不会接管或停止外部已有进程；请避免启动重复实例。

- 进程运行状态不代表代理连接成功或业务服务健康。
- 应用失败可查看日志；校验失败不会停止原进程。启动失败不会自动回滚到历史连接配置。
- `create_app()` 无启动副作用。只在 `main.py` 入口且 `FRPC_AUTOSTART=1` 时自动启动。
- 使用单进程、多线程 Waitress，**不要用多个 WSGI worker 管理同一个 frpc/config 文件**。

## Docker

多阶段构建：Node 只在构建阶段使用，运行镜像是 Python + 静态文件 + frpc。镜像内只包含 `examples/` 中的空白占位配置，不会烘焙真实服务器地址或 token；正式运行必须挂载自己的配置。

本地安全测试，先运行上面的脚本/复制步骤生成 `tmp/local-test` 配置：

```powershell
docker compose -f .\docker-compose.local.yml up --build
```

访问 http://127.0.0.1:8000 。测试 compose 只绑定 loopback，禁用 frpc 管理。

推送 `main` 后，GitHub Actions 自动构建并发布镜像：

- GHCR：`ghcr.io/ksamni/frpcweb:latest`
- Docker Hub：`yancjycj/frpcweb:latest`
- 同时提供 `main` 和 `sha-<短提交号>` 标签，便于固定版本。

`docker-compose.yml` 使用新的 GHCR 地址；旧的 `ghcr.io/yancj9ya/frpcweb` 地址因账号更名不再作为发布目标。升级前备份配置，在镜像发布成功后运行：

```powershell
docker compose pull
docker compose up -d
```

正式镜像默认启用 FRPC_MANAGE/FRPC_AUTOSTART，并监听 0.0.0.0；先验证挂载配置、网络与访问控制，再用于正式部署。

## 安全边界

**本版本未提供登录/用户权限系统。不要直接暴露到公网。** API 有会话 CSRF 校验、同源检查和非 GET 删除，但这些不替代身份认证。可信内网以外的部署必须使用带身份认证的反向代理和 HTTPS，必要时设置 `SECRET_KEY` 并配置安全 Cookie。反向代理需保留正确 Host；本地默认只监听 127.0.0.1。

## 自动测试

后端单元/接口测试均在临时目录操作，运行时进程控制使用 mock：

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s .\tests -v
npm --prefix .\frontend run build
```

浏览器测试（不读写真实配置），先构建前端。在终端一启动独立 fixture 服务：

```powershell
.\.venv\Scripts\python.exe -B .\tests\serve_fixture.py
```

终端二：

```powershell
# 使用本机 Chrome；无 Chrome 可在 frontend 目录运行 npx playwright install chromium，省略该环境变量。
$env:PLAYWRIGHT_CHANNEL = 'chrome'
npm --prefix .\frontend run test:e2e
```

服务地址 http://127.0.0.1:18080 。fixture 的重置接口仅存在于测试脚本，不在生产应用注册。
测试覆盖新增/编辑/复制/删除、重复校验、继续添加、设置、日志、首页密度、组合筛选、卡片与键盘操作、长名称、320–1920px 布局和无外部请求；截图保存在 `frontend/test-results/`。

## 目录

```text
app/api.py             JSON API 与请求保护
app/config_store.py    校验、配置读写和修订冲突检查
app/frpc.py            单进程 frpc 生命周期与日志
app/__init__.py        应用工厂、SPA 静态资源与压缩
frontend/src/          Vue 页面、组件与样式
scripts/start-local.ps1 配置副本本地试用入口
tests/                 后端测试与独立浏览器测试服务
```

旧 `app/routes.py`、Jinja 模板与样式暂时保留作迁移参考，不在新版应用中注册或加载。
