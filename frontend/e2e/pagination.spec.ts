import { expect, test, type Page } from '@playwright/test'
import type { State } from '../src/types'

async function pageSize(page: Page, size: number) {
  await page.locator('.n-pagination .n-select').click()
  await page
    .locator('.n-base-select-menu:visible')
    .getByText(new RegExp(`^${size} /`))
    .click()
  await expect(page.locator('.n-base-select-menu:visible')).toHaveCount(0)
  await expect(page.locator('.n-pagination .n-select')).toContainText(`${size} /`)
}

test.beforeEach(async ({ page, request }) => {
  expect((await request.post('/__test/reset')).ok()).toBeTruthy()
  await page.route('**/api/state', async (route) => {
    const response = await route.fetch()
    const state: State = await response.json()
    state.proxies = Array.from({ length: 60 }, (_, index) => ({
      ...state.proxies[0]!,
      name: `pagination-${String(index + 1).padStart(2, '0')}`,
      display_name: `分页测试 ${index + 1}`,
      remote_port: 20001 + index,
    }))
    await route.fulfill({ response, json: state })
  })
  await page.goto('/config')
})

test('page-size selection changes the rendered rows between 12, 48 and 24', async ({ page }) => {
  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(12)
  await pageSize(page, 48)
  await expect(rows).toHaveCount(48)
  await expect(rows.last()).toContainText('pagination-48')
  await page.locator('.n-pagination-item').filter({ hasText: /^2$/ }).click()
  await expect(rows).toHaveCount(12)
  await expect(rows.first()).toContainText('pagination-49')
  await pageSize(page, 24)
  await expect(rows).toHaveCount(24)
  await page.locator('.n-pagination-item').filter({ hasText: /^3$/ }).click()
  await expect(rows).toHaveCount(12)
  await expect(rows.first()).toContainText('pagination-49')
  await pageSize(page, 12)
  await expect(rows).toHaveCount(12)
  await page.locator('.n-pagination-item').filter({ hasText: /^5$/ }).click()
  await expect(rows.first()).toContainText('pagination-49')
  // Enlarging from page 5 clamps to the new last page, never an empty page.
  await pageSize(page, 48)
  await expect(rows).toHaveCount(12)
  await expect(rows.first()).toContainText('pagination-49')
  await page.locator('.n-pagination-item').filter({ hasText: /^1$/ }).click()
  await expect(rows).toHaveCount(48)
  await expect(rows.first()).toContainText('pagination-01')
})

test('chosen page size survives selection, filtering and a data refresh', async ({ page }) => {
  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(12)
  await pageSize(page, 48)
  await expect(rows).toHaveCount(48)
  await rows.first().getByRole('checkbox').check()
  await expect(page.getByRole('region', { name: '批量分组' })).toContainText('已选 1 个代理')
  await expect(rows).toHaveCount(48)
  const search = page.getByPlaceholder('搜索名称、分组、IP 或端口')
  await search.fill('pagination-60')
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText('pagination-60')
  await search.fill('')
  await expect(rows).toHaveCount(48)
  await page.getByRole('button', { name: '刷新数据', exact: true }).click()
  await expect(rows).toHaveCount(48)
  await expect(page.locator('.n-pagination .n-select')).toContainText('48 /')
})
