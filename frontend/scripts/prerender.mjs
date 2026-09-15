#!/usr/bin/env node
/**
 * Renders output/index.html from output/data.json.
 *
 * This is the snapshot architecture: nothing is fetched in the browser. Python
 * writes the data, this renders it once, and freshness comes from regeneration
 * — exactly as before the rebuild.
 *
 * Markup assembly lives in the SSR bundle (renderDocument), shared with the
 * serverless render function, so a page rendered here and a page rendered on
 * Vercel are byte-identical for the same data.
 *
 * Runs against a self-contained bundle built by `vite build`, so it needs a
 * node binary but no node_modules.
 */
import { mkdirSync, writeFileSync, renameSync, rmSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const frontendRoot = join(here, '..')
const repoRoot = join(frontendRoot, '..')

const outputDir = resolve(repoRoot, process.env.REO_OUTPUT_DIR ?? 'output')
const dataPath = join(outputDir, 'data.json')

const { parseDashboardData, buildProps, renderDocument, NoDataError } = await import(
  join(frontendRoot, 'dist-ssr/entry-server.js')
)

const data = parseDashboardData(JSON.parse(readFileSync(dataPath, 'utf8')))

let html
let props
try {
  props = buildProps(data, { now: Date.now() })
  html = renderDocument(props)
} catch (error) {
  if (error instanceof NoDataError) {
    console.error(`${error.message} (${dataPath})`)
    process.exit(1)
  }
  throw error
}

// Write atomically so a web server never serves a half-written page.
mkdirSync(outputDir, { recursive: true })
const tmp = join(outputDir, `.index.html.${process.pid}.tmp`)
try {
  writeFileSync(tmp, html, 'utf8')
  renameSync(tmp, join(outputDir, 'index.html'))
} catch (error) {
  rmSync(tmp, { force: true })
  throw error
}

const total = data.environments.reduce((n, e) => n + e.indexers.length, 0)
console.log(
  `Rendered index.html — ${data.environments.length} networks, ${total} indexers, generated ${data.generatedAt}`,
)
