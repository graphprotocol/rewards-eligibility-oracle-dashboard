/**
 * Serves the dashboard page.
 *
 * The snapshot architecture is unchanged — nothing is fetched in the browser,
 * the page arrives fully rendered — but the snapshot can no longer be a file in
 * the deployment, because a deployment is immutable and the data refreshes
 * hourly. So the same SSR bundle the prerenderer uses runs here instead, over
 * the data.json that api/refresh.py publishes to Blob.
 *
 * Cost and load are handled by the CDN, not by rendering per visitor: the
 * response is cacheable for an hour, which is the data's own refresh interval,
 * so this executes roughly once per region per refresh.
 */
import { head } from '@vercel/blob'

import {
  parseDashboardData,
  buildProps,
  renderDocument,
  NoDataError,
  IndexerNotFoundError,
} from '../frontend/dist-ssr/entry-server.js'

/**
 * How long a rendered page may be served from the CDN.
 *
 * Five minutes, not the cron's hour: a refresh can land at any point in the
 * hour (a manual one after a deploy, say), and an hour-long entry pinned the
 * page rendered just before it for that whole hour. A render is a few
 * milliseconds, so re-rendering every five minutes costs nothing.
 * `stale-while-revalidate` keeps responses instant while that happens;
 * `stale-if-error` replaces the old renderer's "leave the previous index.html
 * in place" behaviour — if Blob or this function fails, the CDN keeps serving
 * the last good page rather than an error.
 */
const CACHE_CONTROL =
  'public, max-age=0, s-maxage=300, stale-while-revalidate=3600, stale-if-error=86400'

/**
 * The parsed data.json, reused across invocations on a warm instance — but
 * only while it is still the published one. Keyed on the blob's etag, which a
 * cheap head() reads on every render. Without the key, a warm instance kept
 * whatever data.json it first loaded for as long as it stayed warm, so a
 * refresh never reached the page.
 */
let cached = null

async function loadData() {
  const blob = await head('data.json')
  if (cached?.etag === blob.etag) return cached.data
  const response = await fetch(blob.url, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(`Fetching data.json failed: ${response.status} ${response.statusText}`)
  }
  const data = parseDashboardData(await response.json())
  cached = { etag: blob.etag, data }
  return data
}

/**
 * Before the first cron run, Blob has no data.json at all. Rendering an empty
 * roster would publish a verdict the oracle never made, so say plainly that the
 * dashboard has not generated yet.
 *
 * Inlined rather than read from public/: that directory is the static output,
 * which is served by the CDN and is not guaranteed to be present on the
 * function's own filesystem.
 */
const PENDING_PAGE = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rewards Eligibility Oracle · The Graph</title>
<link rel="stylesheet" href="gds.css">
</head>
<body>
<main style="max-width:40rem;margin:20vh auto;padding:0 1.5rem;text-align:center">
<h1>Generating</h1>
<p>The dashboard has not completed its first data refresh yet. It runs hourly — check back shortly.</p>
</main>
</body>
</html>
`

/** An address that is not on any roster. Short-lived, since it may join one. */
const NOT_FOUND_PAGE = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indexer not found · Rewards Eligibility Oracle</title>
<base href="../../">
<link rel="stylesheet" href="gds.css">
</head>
<body>
<main style="max-width:40rem;margin:20vh auto;padding:0 1.5rem;text-align:center">
<h1>Indexer not found</h1>
<p>This address is not on the indexer roster of any network. <a href="./">See all indexers</a>.</p>
</main>
</body>
</html>
`

export default async function handler(request, response) {
  // Set by the /indexer/:address rewrite in vercel.json.
  const indexer = typeof request.query?.indexer === 'string' ? request.query.indexer : null
  try {
    const data = await loadData()
    const props = buildProps(data, { now: Date.now(), indexer })
    const html = renderDocument(props)

    response.setHeader('Content-Type', 'text/html; charset=utf-8')
    response.setHeader('Cache-Control', CACHE_CONTROL)
    return response.status(200).send(html)
  } catch (error) {
    if (error instanceof IndexerNotFoundError) {
      response.setHeader('Content-Type', 'text/html; charset=utf-8')
      response.setHeader('Cache-Control', 'public, max-age=0, s-maxage=300')
      return response.status(404).send(NOT_FOUND_PAGE)
    }
    cached = null

    const notGenerated =
      error instanceof NoDataError || error?.name === 'BlobNotFoundError'
    if (notGenerated) {
      // Not an error condition on a brand-new deployment. Cache briefly so the
      // first successful cron is picked up promptly.
      response.setHeader('Content-Type', 'text/html; charset=utf-8')
      response.setHeader('Cache-Control', 'public, max-age=0, s-maxage=60')
      return response.status(503).send(PENDING_PAGE)
    }

    // Let stale-if-error do its job: a 500 here means the CDN keeps serving the
    // last good page to everyone who is not the unlucky revalidation request.
    console.error('Render failed:', error)
    response.setHeader('Cache-Control', 'no-store')
    return response.status(500).send('Dashboard temporarily unavailable.')
  }
}
