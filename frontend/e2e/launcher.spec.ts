import { expect, test } from '@playwright/test'
import type { State } from '../src/types'

test.beforeEach(async ({ request }) => {
  expect((await request.post('/__test/reset')).ok()).toBeTruthy()
})

test('launcher prioritizes entries and fits twelve services above the desktop fold', async ({
  page,
}, info) => {
  await page.route('**/api/state', async (route) => {
    const response = await route.fetch()
    const data: State = await response.json()
    const examples = data.proxies
    data.proxies = Array.from({ length: 24 }, (_, index) => ({
      ...examples[index % examples.length]!,
      name: `service-${index}`,
    }))
    await route.fulfill({ response, json: data })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await expect(page.locator('.service-card')).toHaveCount(24)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('我的服务')
  await expect(page.locator('.overview-grid, .page-heading')).toHaveCount(0)
  const layout = await page.locator('.service-card').evaluateAll((cards) => {
    const bounds = cards.map((card) => card.getBoundingClientRect())
    return {
      top: bounds[0]!.top,
      height: bounds[0]!.height,
      firstRow: bounds.filter((r) => r.top === bounds[0]!.top).length,
      visible: bounds.filter((r) => r.top >= 0 && r.bottom <= innerHeight).length,
    }
  })
  expect(layout.top).toBeLessThan(260)
  expect(layout.height).toBeLessThan(200)
  expect(layout.firstRow).toBe(4)
  expect(layout.visible).toBeGreaterThanOrEqual(12)
  await page.screenshot({ path: info.outputPath('launcher-dense-desktop.png') })
})

test('groups, favorites and search combine with a recoverable empty state', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '家庭服务', exact: true }).click()
  await expect(page.locator('.service-card')).toHaveCount(3)
  await expect(page.getByRole('button', { name: '家庭服务', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('button', { name: '只看收藏' }).click()
  await expect(page.locator('.service-card')).toHaveCount(2)
  await page.getByRole('textbox', { name: '搜索服务' }).fill('15000')
  await expect(page.locator('.service-card')).toHaveCount(1)
  await page.getByRole('textbox', { name: '搜索服务' }).fill('没有这个服务')
  await expect(page.getByText('没有找到匹配的服务')).toBeVisible()
  await page.getByRole('button', { name: '清除筛选' }).click()
  await expect(page.locator('.service-card')).toHaveCount(6)
  await expect(page.getByRole('button', { name: '只看收藏' })).toHaveAttribute('aria-pressed', 'false')
  await page.getByRole('textbox', { name: '搜索服务' }).fill('git.example.com')
  await expect(page.locator('.service-card')).toHaveCount(1)
  await expect(page.getByRole('heading', { name: '代码仓库' })).toBeVisible()
})

test('whole-card entry, favorite, copy and keyboard actions remain independent', async ({
  page,
  context,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: async (value: string) => {
          document.documentElement.dataset.copied = value
        },
      },
    })
  })
  // The fake Web destination is fulfilled locally: never connect to an actual service.
  await context.route('https://git.example.com/**', (route) =>
    route.fulfill({ contentType: 'text/html', body: '<title>Local fake service</title>' }),
  )
  await page.goto('/')
  const web = page.getByRole('article', { name: '代码仓库', exact: true })
  await web.getByRole('button', { name: '收藏 代码仓库', exact: true }).click()
  await expect(web.getByRole('button', { name: '取消收藏 代码仓库', exact: true })).toBeEnabled()
  await expect(page.locator('html')).not.toHaveAttribute('data-copied')
  expect(context.pages()).toHaveLength(1)
  await web.getByRole('button', { name: '复制 代码仓库 地址' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-copied', 'https://git.example.com/')
  expect(context.pages()).toHaveLength(1)
  const udp = page.getByRole('article', { name: '游戏服务器', exact: true })
  await udp.click({ position: { x: 8, y: 70 } })
  await expect(page.locator('html')).toHaveAttribute('data-copied', '192.168.1.10:27015')
  expect(context.pages()).toHaveLength(1)
  const popupReady = page.waitForEvent('popup')
  await web.click({ position: { x: 8, y: 70 } })
  const popup = await popupReady
  await expect(popup).toHaveURL('https://git.example.com/')
  await popup.close()
  const entry = web.getByRole('link', { name: /打开服务\s*：代码仓库/ })
  await entry.focus()
  await expect(entry).toBeFocused()
  await expect(entry).toHaveAttribute('rel', 'noopener noreferrer')
  const keyboardPopupReady = page.waitForEvent('popup')
  await page.keyboard.press('Enter')
  const keyboardPopup = await keyboardPopupReady
  await expect(keyboardPopup).toHaveURL('https://git.example.com/')
  await keyboardPopup.close()
})

test('long names, many groups and read-only entries fit narrow and wide screens', async ({ page }, info) => {
  await page.route('**/api/state', async (route) => {
    const response = await route.fetch()
    const data: State = await response.json()
    data.proxies = data.proxies.map((proxy, index) => ({
      ...proxy,
      display_name: `很长的服务名称需要保持布局稳定-${index}-abcdefghijklmnopqrstuv`,
      group: index === 0 ? '' : index === 1 ? '全部服务' : `较长的分组名称-${index}`,
      editable: index !== 0,
    }))
    await route.fulfill({ response, json: data })
  })
  await page.goto('/')
  await expect(page.locator('.service-card')).toHaveCount(6)
  await expect(page.locator('.service-card').first().getByText('只读')).toBeVisible()
  for (const width of [320, 390, 600, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
      `overflow at ${width}px`,
    ).toBeLessThanOrEqual(width)
    const first = await page.locator('.service-card').first().boundingBox()
    expect(first!.height).toBeLessThan(200)
    if (width === 390) {
      expect(first!.y).toBeLessThan(270)
      await page.screenshot({ path: info.outputPath('launcher-long-names-mobile.png') })
    }
  }
  await page.getByRole('button', { name: '未分组', exact: true }).click()
  await expect(page.locator('.service-card')).toHaveCount(1)
  // An actual group named “全部服务” must not be confused with the all-services filter.
  await page.getByRole('button', { name: '全部服务', exact: true }).nth(1).click()
  await expect(page.locator('.service-card')).toHaveCount(1)
  await page.getByRole('button', { name: '全部服务', exact: true }).first().click()
  await expect(page.locator('.service-card')).toHaveCount(6)
})

test('copy stays bottom-left and primary actions bottom-right at every viewport', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.service-card')).toHaveCount(6)
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    const layout = await page.locator('.service-card').evaluateAll((cards) =>
      cards.map((card) => {
        const bounds = card.getBoundingClientRect()
        const footer = card.querySelector('.service-card-bottom')!.getBoundingClientRect()
        const actions = card.querySelector('.service-card-actions')!.getBoundingClientRect()
        const primary = card.querySelector('.service-open')!.getBoundingClientRect()
        const hint = card.querySelector('.service-hint')?.getBoundingClientRect()
        const copy = card.querySelector('.service-copy')?.getBoundingClientRect()
        return {
          rightGap: footer.right - actions.right,
          leftGap: actions.left - footer.left,
          bottomGap: bounds.bottom - primary.bottom,
          primaryInFooter: primary.top >= footer.top && primary.bottom <= footer.bottom,
          hintBeforeActions: !hint || hint.right <= actions.left,
          copyAtBottomLeft:
            !copy ||
            (Math.abs(copy.left - footer.left) < 1 &&
              bounds.bottom - copy.bottom < 22 &&
              copy.right < primary.left),
        }
      }),
    )
    for (const card of layout) {
      expect(Math.abs(card.rightGap)).toBeLessThan(1)
      expect(card.leftGap).toBeGreaterThanOrEqual(0)
      expect(card.bottomGap).toBeLessThan(22)
      expect(card.primaryInFooter).toBeTruthy()
      expect(card.hintBeforeActions).toBeTruthy()
      expect(card.copyAtBottomLeft).toBeTruthy()
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  }
})

test('the tab icon is served locally and renders at small sizes on every route', async ({
  page,
  request,
}) => {
  await page.goto('/')
  const icon = page.locator('link[rel="icon"]')
  await expect(icon).toHaveAttribute('type', 'image/svg+xml')
  await expect(icon).toHaveAttribute('sizes', 'any')
  const href = (await icon.getAttribute('href'))!
  expect(href).toBe('/favicon.svg?v=portals-1')
  const response = await request.get(href)
  expect(response.ok()).toBeTruthy()
  expect(response.headers()['content-type']).toContain('image/svg+xml')
  const source = await response.text()
  expect(source).toContain('FRP Console — connected portals')
  expect(source).not.toContain('<text')
  const rendered = await page.evaluate(async (url) => {
    const image = new Image()
    image.src = url
    await image.decode()
    return [16, 32].map((size) => {
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = size
      const context = canvas.getContext('2d')!
      context.drawImage(image, 0, 0, size, size)
      const pixels = context.getImageData(0, 0, size, size).data
      return pixels.some((value, index) => index % 4 === 3 && value > 0)
    })
  }, href)
  expect(rendered).toEqual([true, true])
  for (const route of ['/config', '/settings', '/logs']) {
    await page.goto(route)
    await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', href)
  }
})
