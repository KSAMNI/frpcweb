import { test, expect, type Page } from '@playwright/test'
import type { State } from '../src/types'

async function createDefaultProxy(page: Page) {
  const state: State = await (await page.request.get('/api/state')).json()
  const response = await page.request.post('/api/proxies', {
    headers: { 'X-CSRF-Token': state.csrf_token },
    data: {
      name: 'default-web',
      display_name: '默认服务',
      type: 'tcp',
      local_ip: '127.0.0.1',
      local_port: 8080,
      remote_port: 19080,
      visible: true,
      favorite: false,
      group: '测试分组',
      access_url: '',
      revision: state.revision,
    },
  })
  expect(response.ok()).toBeTruthy()
}

test.beforeEach(async ({ page, request }) => {
  expect((await request.post('/__test/reset')).ok()).toBeTruthy()
  await createDefaultProxy(page)
})

test('default links and copy use the configured host and proxy remote port', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: async (value: string) => {
          document.documentElement.dataset.copied = value
        },
      },
    })
  })
  await page.goto('/')
  const card = page.getByRole('article', { name: '默认服务', exact: true })
  await expect(card.getByRole('link', { name: /打开服务/ })).toHaveAttribute(
    'href',
    'http://192.168.1.10:19080/',
  )
  await card.getByRole('button', { name: '复制 默认服务 地址' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-copied', 'http://192.168.1.10:19080/')
  await page.getByRole('textbox', { name: '搜索服务' }).fill('192.168.1.10:19080')
  await expect(page.locator('.service-card')).toHaveCount(1)
  await page.getByRole('textbox', { name: '搜索服务' }).fill('')
  for (const name of ['开发服务器', '游戏服务器']) {
    await expect(page.getByRole('article', { name, exact: true }).getByRole('link')).toHaveCount(0)
  }
})

test('inherited links follow host and port changes, while custom links remain unchanged', async ({
  page,
}) => {
  await page.goto('/settings')
  await page.getByRole('textbox', { name: '目标地址' }).fill('services.example.com')
  await page.getByRole('button', { name: '保存地址', exact: true }).click()
  await expect(page.getByText('访问地址已保存，无需重启 frpc')).toBeVisible()
  await page.getByRole('link', { name: '服务入口' }).click()
  await expect(
    page.getByRole('article', { name: '默认服务', exact: true }).getByRole('link'),
  ).toHaveAttribute('href', 'http://services.example.com:19080/')
  await expect(
    page.getByRole('article', { name: '代码仓库', exact: true }).getByRole('link'),
  ).toHaveAttribute('href', 'https://git.example.com/')
  await page.goto('/config')
  await page
    .locator('tr')
    .filter({ hasText: 'default-web' })
    .getByRole('button', { name: '编辑', exact: true })
    .click()
  await expect(page.getByRole('textbox', { name: 'Web 访问地址', exact: true })).toHaveValue('')
  await expect(page.locator('.inherited-address')).toContainText('http://services.example.com:19080/')
  await page.getByLabel('远程端口', { exact: true }).fill('19081')
  await expect(page.locator('.inherited-address')).toContainText('http://services.example.com:19081/')
  await page.getByRole('button', { name: '保存配置', exact: true }).last().click()
  await expect(page.locator('.n-drawer')).toHaveCount(0)
  await page.goto('/')
  await expect(
    page.getByRole('article', { name: '默认服务', exact: true }).getByRole('link'),
  ).toHaveAttribute('href', 'http://services.example.com:19081/')
})

test('custom Web links can be reset to inherited IPv6 addresses', async ({ page }) => {
  await page.goto('/settings')
  await page.getByRole('textbox', { name: '目标地址' }).fill('2001:db8::10')
  await page.getByRole('button', { name: '保存地址', exact: true }).click()
  await expect(page.getByText('访问地址已保存，无需重启 frpc')).toBeVisible()
  await page.goto('/config')
  await page
    .locator('tr')
    .filter({ hasText: 'nas-web' })
    .getByRole('button', { name: '编辑', exact: true })
    .click()
  await page.getByRole('button', { name: '恢复默认地址', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Web 访问地址', exact: true })).toHaveValue('')
  await expect(page.locator('.inherited-address')).toContainText('http://[2001:db8::10]:15000/')
  await page.getByRole('button', { name: '保存配置', exact: true }).last().click()
  await expect(page.locator('.n-drawer')).toHaveCount(0)
  await page.goto('/')
  await expect(
    page.getByRole('article', { name: '我的 NAS', exact: true }).getByRole('link'),
  ).toHaveAttribute('href', 'http://[2001:db8::10]:15000/')
})

test('client protocols, unknown protocols and unsafe custom URLs do not become Web links', async ({
  page,
}) => {
  await page.route('**/api/state', async (route) => {
    const response = await route.fetch()
    const state: State = await response.json()
    const base = state.proxies.find((p) => p.name === 'default-web')!
    state.proxies = [
      ...[22, 3389, 3306, 5432, 6379, 27017].map((port) => ({
        ...base,
        name: `client-${port}`,
        local_port: port,
      })),
      { ...base, name: 'udp', type: 'udp' },
      { ...base, name: 'unknown', type: 'http', remote_port: null, editable: false },
      { ...base, name: 'bad-url', access_url: 'javascript:alert(1)' },
    ]
    await route.fulfill({ response, json: state })
  })
  await page.goto('/')
  await expect(page.locator('.service-card')).toHaveCount(9)
  await expect(page.locator('.service-card a')).toHaveCount(0)
})
