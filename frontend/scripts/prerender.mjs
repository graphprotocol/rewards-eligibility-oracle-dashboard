#!/usr/bin/env node
/**
 * Renders output/index.html from output/data.json.
 *
 * This is the snapshot architecture: nothing is fetched in the browser. Python
 * writes the data, this renders it once, and freshness comes from regeneration
 * (every ~5 minutes in production) — exactly as before the rebuild.
 *
 * Runs against a self-contained bundle built by `vite build`, so it needs a
 * node binary but no node_modules.
 */
import { mkdirSync, writeFileSync, renameSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { loadDashboardData } from '../src/lib/data.js'

/** Bumped by hand; shown in the footer so a deploy can be identified on sight. */
const VERSION = 'v0.4.0'

const here = dirname(fileURLToPath(import.meta.url))
const frontendRoot = join(here, '..')
const repoRoot = join(frontendRoot, '..')


const outputDir = resolve(repoRoot, process.env.REO_OUTPUT_DIR ?? 'output')
const dataPath = join(outputDir, 'data.json')

const { renderPage, theGraphLogo } = await import(join(frontendRoot, 'dist-ssr/entry-server.js'))

/**
 * The official logomark as a data-URI favicon, taken from the SSR bundle so it
 * matches the masthead exactly and needs no filesystem access at runtime.
 * `currentcolor` is meaningless in a favicon, so brand purple is substituted.
 */
const FAVICON = encodeURIComponent(theGraphLogo.replace('currentcolor', '#6f4cff'))

const { generatedAt, environments, criteria } = loadDashboardData(dataPath)
if (environments.length === 0) {
  console.error(`No environments in ${dataPath} — refusing to render an empty page.`)
  process.exit(1)
}

// Default to the first network that actually has data, so the page never opens
// on an empty table when a populated one exists.
const activeId = environments.find((e) => e.available)?.id ?? environments[0].id

// `now` is fixed at render time and shipped to the client, so the grace
// countdown is identical on both sides and hydration cannot mismatch.
const props = { environments, activeId, generatedAt, version: VERSION, now: Date.now(), criteria }
const body = renderPage(props)

// The client hydrates from exactly these props, so server and client can never
// disagree about the data. `available` is a getter, so serialize it explicitly.
const serializedProps = JSON.stringify(
  { ...props, environments: environments.map((e) => ({ ...e, available: e.available })) },
  // </script> inside JSON would close the tag early.
).replaceAll('<', '\\u003c')

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rewards Eligibility Oracle · The Graph</title>
<meta name="description" content="Live rewards eligibility for indexers on The Graph Network, published by the Rewards Eligibility Oracle (GIP-0079).">
<meta property="og:title" content="Rewards Eligibility Oracle · The Graph">
<meta property="og:description" content="Live rewards eligibility for indexers on The Graph Network.">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,${FAVICON}">
<link rel="stylesheet" href="gds.css">
</head>
<body>
<div id="reo-root">${body}</div>
<script type="application/json" id="reo-data">${serializedProps}</script>
<script type="module" src="app.js"></script>
</body>
</html>
`

// Write atomically so Caddy never serves a half-written page.
mkdirSync(outputDir, { recursive: true })
const tmp = join(outputDir, `.index.html.${process.pid}.tmp`)
try {
  writeFileSync(tmp, html, 'utf8')
  renameSync(tmp, join(outputDir, 'index.html'))
} catch (error) {
  rmSync(tmp, { force: true })
  throw error
}

const total = environments.reduce((n, e) => n + e.indexers.length, 0)
console.log(
  `Rendered index.html — ${environments.length} networks, ${total} indexers, generated ${generatedAt}`,
)
