import { test, expect, type Page } from '@playwright/test'
import type { State } from '../src/types'

async function selectGroup(page: Page, label: string, group: string) {
  await page.locator(`.n-select[aria-label="${label}"]`).click()
  await page.getByRole('textbox', { name: label, exact: true }).fill(group)
  await page.keyboard.press('Enter')
  await expect(page.locator('.n-base-select-menu:visible')).toHaveCount(0)
}
async function getState(page: Page): Promise<State> {
  return (await page.request.get('/api/state')).json()
}

test.beforeEach(async ({ request }) => {
  expect((await request.post('/__test/reset')).ok()).toBeTruthy()
})

test('inline grouping creates and reuses groups without editing connection rules', async ({ page }) => {
  await page.goto('/config')
  const before = await getState(page)
  await selectGroup(page, '我的 NAS 的分组', '常用服务')
  await expect(page.getByText('分组已更新，首页立即生效，无需重启 frpc')).toBeVisible()
  const first = await getState(page)
  expect(first.frpc_revision).toBe(before.frpc_revision)
  expect(first.proxies.find((p) => p.name === 'nas-web')?.group).toBe('常用服务')
  await page.locator('.n-select[aria-label="影音中心 的分组"]').click()
  await page.locator('.n-base-select-menu:visible').getByText('常用服务', { exact: true }).click()
  await expect
    .poll(async () => (await getState(page)).proxies.find((p) => p.name === 'jellyfin')?.group)
    .toBe('常用服务')
  await page.reload()
  await expect(page.locator('.n-select[aria-label="我的 NAS 的分组"]')).toContainText('常用服务')
  await page.goto('/')
  await page.getByRole('button', { name: '常用服务', exact: true }).click()
  await expect(page.locator('.service-card')).toHaveCount(2)
})

test('selected proxies can be grouped together and moved back to ungrouped', async ({ page }, info) => {
  await page.goto('/config')
  const before = await getState(page)
  for (const name of ['nas-web', 'ssh-server']) {
    await page.locator('tr').filter({ hasText: name }).getByRole('checkbox').check()
  }
  const batch = page.getByRole('region', { name: '批量分组' })
  await expect(batch).toContainText('已选 2 个代理')
  await selectGroup(page, '批量目标分组', '常用服务')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(batch.getByRole('button', { name: '移动到分组' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.screenshot({ path: info.outputPath('batch-group-mobile.png'), fullPage: true })
  await batch.getByRole('button', { name: '移动到分组' }).click()
  await expect(batch).toHaveCount(0)
  const after = await getState(page)
  expect(after.frpc_revision).toBe(before.frpc_revision)
  expect(
    after.proxies
      .filter((p) => p.group === '常用服务')
      .map((p) => p.name)
      .sort(),
  ).toEqual(['nas-web', 'ssh-server'])
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.reload()
  await page.locator('tr').filter({ hasText: 'nas-web' }).getByRole('checkbox').check()
  await batch.getByRole('button', { name: '移至未分组' }).click()
  await expect(batch).toHaveCount(0)
  expect((await getState(page)).proxies.find((p) => p.name === 'nas-web')?.group).toBe('')
})

test('group filtering clears selection and shows only matching proxies', async ({ page }) => {
  await page.goto('/config')
  await page.locator('tr').filter({ hasText: 'nas-web' }).getByRole('checkbox').check()
  await page.locator('.n-select[aria-label="筛选分组"]').click()
  await page.locator('.n-base-select-menu:visible').getByText('开发工具 (2)', { exact: true }).click()
  await expect(page.getByRole('region', { name: '批量分组' })).toHaveCount(0)
  await expect(page.locator('tbody tr')).toHaveCount(2)
  await expect(page.locator('tbody')).toContainText('ssh-server')
  await expect(page.locator('tbody')).not.toContainText('nas-web')
})

test('stale batch grouping is rejected without losing selection or overwriting data', async ({ page }) => {
  await page.goto('/config')
  await page.locator('tr').filter({ hasText: 'nas-web' }).getByRole('checkbox').check()
  await selectGroup(page, '批量目标分组', '过期修改')
  const state = await getState(page)
  const response = await page.request.put('/api/settings', {
    headers: { 'X-CSRF-Token': state.csrf_token },
    data: { target_ip: 'changed.example.com', revision: state.revision },
  })
  expect(response.ok()).toBeTruthy()
  await page.getByRole('button', { name: '移动到分组' }).click()
  await expect(page.getByText(/配置已被其他页面或程序修改/)).toBeVisible()
  await expect(page.getByRole('region', { name: '批量分组' })).toContainText('已选 1 个代理')
  expect((await getState(page)).proxies.find((p) => p.name === 'nas-web')?.group).toBe('家庭服务')
})

test('batch selection survives pagination and only updates checked proxies', async ({ page }) => {
  let state = await getState(page)
  for (let index = 0; index < 8; index++) {
    const response = await page.request.post('/api/proxies', {
      headers: { 'X-CSRF-Token': state.csrf_token },
      data: {
        ...state.proxies[0],
        name: `extra-${index}`,
        display_name: `额外服务 ${index}`,
        remote_port: 21000 + index,
        revision: state.revision,
      },
    })
    expect(response.ok()).toBeTruthy()
    state = await response.json()
  }
  await page.goto('/config')
  await page.locator('tr').filter({ hasText: 'nas-web' }).getByRole('checkbox').check()
  await page.locator('.n-pagination-item').filter({ hasText: /^2$/ }).click()
  await page.locator('tr').filter({ hasText: 'extra-7' }).getByRole('checkbox').check()
  await expect(page.getByRole('region', { name: '批量分组' })).toContainText('已选 2 个代理')
  await selectGroup(page, '批量目标分组', '跨页分组')
  await page.getByRole('button', { name: '移动到分组' }).click()
  await expect(page.getByRole('region', { name: '批量分组' })).toHaveCount(0)
  const saved = await getState(page)
  expect(saved.frpc_revision).toBe(state.frpc_revision)
  expect(
    saved.proxies
      .filter((p) => p.group === '跨页分组')
      .map((p) => p.name)
      .sort(),
  ).toEqual(['extra-7', 'nas-web'])
})
