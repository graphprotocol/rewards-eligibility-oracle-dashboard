#!/usr/bin/env node
/**
 * Visual smoke test for a deployed dashboard.
 *
 *   node frontend/scripts/verify-deployment.mjs https://hub.thegraph.foundation/reo
 *
 * Every check here exists because something shipped broken that an HTTP 200
 * would not have caught:
 *
 * - The page returned 200 while gds.css and app.js 404'd, rendering completely
 *   unstyled — because the URL had no trailing slash and relative asset paths
 *   resolved against the domain root.
 * - The page rendered with zero rows because only one network was configured
 *   and that network's oracle had never run.
 * - The page rendered but was inert because the client bundle was missing from
 *   the image, so nothing hydrated.
 *
 * Exits non-zero on any failure and always writes screenshots so a human can
 * look at what was actually served.
 */
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from 'playwright'

const target = process.argv[2]
if (!target) {
  console.error('usage: node verify-deployment.mjs <url>')
  process.exit(2)
}

const shotDir = process.env.REO_VERIFY_SHOTS
  ?? join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'verification-shots')
mkdirSync(shotDir, { recursive: true })

const base = target.replace(/\/+$/, '')
const failures = []
const notes = []

function check(ok, label, detail = '') {
  if (ok) notes.push(`  PASS  ${label}${detail ? ` — ${detail}` : ''}`)
  else failures.push(`  FAIL  ${label}${detail ? ` — ${detail}` : ''}`)
}

const browser = await chromium.launch()

try {
  // Both spellings must work. The no-slash form is what people actually type
  // and paste, and it is the one that broke.
  for (const [label, url] of [['no-slash', base], ['slash', `${base}/`]]) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
    const badResponses = []
    const pageErrors = []
    page.on('response', (r) => {
      if (r.status() >= 400) badResponses.push(`${r.status()} ${r.url()}`)
    })
    page.on('pageerror', (e) => pageErrors.push(e.message.split('\n')[0]))
    page.on('console', (m) => {
      if (m.type() === 'error') pageErrors.push(`console: ${m.text()}`)
    })

    const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 60_000 })
    await page.waitForTimeout(1500)
    await page.screenshot({ path: join(shotDir, `desktop-${label}.png`), fullPage: false })

    check(response.status() < 400, `${label}: page loads`, `HTTP ${response.status()}`)
    check(badResponses.length === 0, `${label}: no failed requests`, badResponses.slice(0, 3).join(' | '))
    check(pageErrors.length === 0, `${label}: no console/page errors`, pageErrors.slice(0, 2).join(' | '))

    // A page can return 200 and still be visually broken. These assertions are
    // what actually distinguishes "styled" from "raw HTML".
    const visual = await page.evaluate(() => {
      const canvas = document.querySelector('.bg-canvas') ?? document.body
      const h1 = document.querySelector('h1')
      return {
        canvasBg: getComputedStyle(canvas).backgroundColor,
        h1Size: parseFloat(getComputedStyle(h1).fontSize),
        h1Font: getComputedStyle(h1).fontFamily,
        stylesheets: document.styleSheets.length,
      }
    })
    check(visual.stylesheets > 0, `${label}: stylesheet attached`, `${visual.stylesheets} sheet(s)`)
    check(
      visual.canvasBg !== 'rgba(0, 0, 0, 0)' && visual.canvasBg !== 'rgb(255, 255, 255)',
      `${label}: themed background applied`,
      visual.canvasBg,
    )
    check(visual.h1Size >= 28, `${label}: heading uses the type scale`, `${visual.h1Size}px`)
    check(/Euclid/i.test(visual.h1Font), `${label}: brand font loaded`, visual.h1Font.split(',')[0])

    await page.close()
  }

  // Everything below is checked once, on the canonical URL.
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 60_000 })
  await page.waitForTimeout(1500)

  const rows = await page.locator('tbody tr').count()
  check(rows > 0, 'roster renders indexers', `${rows} rows`)

  const criteria = await page.locator('#criteria-heading').isVisible().catch(() => false)
  check(criteria, 'eligibility criteria section present')

  // Proves the client bundle loaded AND hydrated: a filter click must change
  // the rendered row count.
  let hydrated = false
  try {
    const before = await page.locator('tbody tr').count()
    await page.getByRole('button', { name: /^Unqualified/ }).click()
    await page.waitForTimeout(600)
    const after = await page.locator('tbody tr').count()
    hydrated = after !== before || after === 0
  } catch {
    hydrated = false
  }
  check(hydrated, 'client bundle hydrated (filter changes the table)')

  await page.screenshot({ path: join(shotDir, 'desktop-full.png'), fullPage: true })
  await page.close()

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await mobile.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 60_000 })
  await mobile.waitForTimeout(1500)
  const cards = await mobile.locator('ul > li').count()
  const overflow = await mobile.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  check(cards > 0, 'mobile renders indexer cards', `${cards} cards`)
  check(!overflow, 'no horizontal overflow at 390px')
  await mobile.screenshot({ path: join(shotDir, 'mobile.png'), fullPage: false })
  await mobile.close()
} finally {
  await browser.close()
}

console.log(`\nVerifying ${base}\n`)
for (const line of notes) console.log(line)
for (const line of failures) console.log(line)
console.log(`\nScreenshots: ${shotDir}`)

if (failures.length > 0) {
  console.error(`\n${failures.length} check(s) FAILED — look at the screenshots before declaring the deploy good.\n`)
  process.exit(1)
}
console.log('\nAll checks passed.\n')
