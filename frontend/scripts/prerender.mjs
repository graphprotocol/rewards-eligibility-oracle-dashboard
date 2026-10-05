#!/usr/bin/env node
/**
 * Renders output/index.html, and output/indexer/<address>/index.html for every
 * indexer, from output/data.json.
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
import { existsSync, mkdirSync, writeFileSync, renameSync, rmSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const frontendRoot = join(here, '..')
const repoRoot = join(frontendRoot, '..')

const outputDir = resolve(repoRoot, process.env.REO_OUTPUT_DIR ?? 'output')
const dataPath = join(outputDir, 'data.json')

const { parseDashboardData, buildProps, renderDocument, indexerPath, NoDataError } = await import(
  join(frontendRoot, 'dist-ssr/entry-server.js')
)

const data = parseDashboardData(JSON.parse(readFileSync(dataPath, 'utf8')))
// One clock for every page of the run, so they all agree with each other.
const now = Date.now()

/** Write atomically so a web server never serves a half-written page. */
function writePage(relativePath, html) {
  const target = join(outputDir, relativePath)
  mkdirSync(dirname(target), { recursive: true })
  const tmp = `${target}.${process.pid}.tmp`
  try {
    writeFileSync(tmp, html, 'utf8')
    renameSync(tmp, target)
  } catch (error) {
    rmSync(tmp, { force: true })
    throw error
  }
}

let html
try {
  html = renderDocument(buildProps(data, { now }))
} catch (error) {
  if (error instanceof NoDataError) {
    console.error(`${error.message} (${dataPath})`)
    process.exit(1)
  }
  throw error
}

// Indexer pages first: the roster links to them, so they must exist by the time
// a new roster is served. A failure here leaves the previous pages in place.
const addresses = [
  ...new Set(data.environments.flatMap((e) => e.indexers.map((i) => i.address.toLowerCase()))),
]
for (const address of addresses) {
  writePage(join(indexerPath(address), 'index.html'), renderDocument(buildProps(data, { now, indexer: address })))
}

// Drop pages for indexers that have left every roster, so their old verdict is
// not left online.
const indexerDir = join(outputDir, 'indexer')
const current = new Set(addresses)
for (const entry of existsSync(indexerDir) ? readdirSync(indexerDir, { withFileTypes: true }) : []) {
  if (entry.isDirectory() && !current.has(entry.name)) {
    rmSync(join(indexerDir, entry.name), { recursive: true, force: true })
  }
}

writePage('index.html', html)

const total = data.environments.reduce((n, e) => n + e.indexers.length, 0)
console.log(
  `Rendered index.html and ${addresses.length} indexer pages — ${data.environments.length} networks, ${total} indexers, generated ${data.generatedAt}`,
)
