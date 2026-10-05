/**
 * Assembles the HTML document around a rendered body.
 *
 * Pure string work — no React, no filesystem — so it can be imported from
 * source by any caller. The React half lives in entry-server.jsx, which
 * combines the two into renderDocument().
 */

import { pickMetrics } from './metrics.js'

/** Bumped by hand; shown in the footer so a deploy can be identified on sight. */
export const VERSION = 'v0.6.0'

/**
 * Raised when there is nothing worth publishing. Both callers treat this as
 * "keep serving the last good page" rather than "render an empty one" — the
 * dashboard has shipped a blank page to production before, and an empty roster
 * is indistinguishable from a real answer to anyone reading it.
 */
export class NoDataError extends Error {
  constructor(message) {
    super(message)
    this.name = 'NoDataError'
  }
}

/**
 * Derives the props both the server render and the client hydration consume.
 *
 * `now` is fixed here and shipped to the client, so the grace countdown is
 * identical on both sides and hydration cannot mismatch. Callers pass it
 * explicitly rather than letting this module read the clock, so a cached
 * document and its embedded props always agree.
 */
export function buildProps(data, { now, version = VERSION, indexer = null }) {
  const { generatedAt, generatedAtEpoch, criteria } = data
  let { environments } = data

  if (environments.length === 0) {
    throw new NoDataError('No environments in dashboard data — refusing to render an empty page.')
  }

  // Default to the first network that actually has data, so the page never
  // opens on an empty table when a populated one exists.
  let activeId = environments.find((e) => e.available)?.id ?? environments[0].id

  if (!indexer) {
    return { view: 'roster', environments, activeId, generatedAt, generatedAtEpoch, version, now, criteria }
  }

  // An indexer page embeds that indexer only. Rendering ~100 of these per run
  // with the whole roster in each would be ~100x the data for nothing.
  const address = indexer.toLowerCase()
  const has = (e) => e.indexers.some((i) => i.address.toLowerCase() === address)
  if (!environments.some(has)) {
    throw new IndexerNotFoundError(`No indexer ${address} in dashboard data.`)
  }
  environments = environments.map((e) => ({
    ...e,
    available: e.available,
    indexers: e.indexers.filter((i) => i.address.toLowerCase() === address),
    metrics: pickMetrics(e.metrics, [address]),
  }))
  if (!has(environments.find((e) => e.id === activeId))) activeId = environments.find(has).id

  return {
    view: 'indexer',
    address,
    environments,
    activeId,
    generatedAt,
    generatedAtEpoch,
    version,
    now,
    criteria,
  }
}

/** The address is not on any roster. The render function answers 404. */
export class IndexerNotFoundError extends Error {
  constructor(message) {
    super(message)
    this.name = 'IndexerNotFoundError'
  }
}

/** Where an indexer's page lives, relative to the dashboard root. */
export const indexerPath = (address) => `indexer/${address.toLowerCase()}/`

/**
 * The client hydrates from exactly these props, so server and client can never
 * disagree about the data. `available` is a getter, so serialize it explicitly.
 */
export function serializeProps(props) {
  return JSON.stringify({
    ...props,
    environments: props.environments.map((e) => ({ ...e, available: e.available })),
    // </script> inside JSON would close the tag early.
  }).replaceAll('<', '\\u003c')
}

/**
 * An indexer page lives two levels below the dashboard root, which itself may
 * be "/" (Vercel) or "/reo/" (Caddy). A relative <base> points every asset and
 * link back at the root without the page knowing which.
 *
 * That only resolves correctly from ".../indexer/0x…/": without the trailing
 * slash, "../../" climbs one level too far. Links we emit always carry it; the
 * script fixes a hand-typed URL before anything else loads.
 */
const INDEXER_HEAD = `<script>if(!location.pathname.endsWith('/'))location.replace(location.pathname+'/'+location.search+location.hash)</script>
<base href="../../">`

export function documentHtml({ body, favicon, props }) {
  const isIndexer = props.view === 'indexer'
  const name =
    isIndexer &&
    (props.environments.flatMap((e) => e.indexers).find((i) => i.ens_name)?.ens_name ?? props.address)
  const title = isIndexer
    ? `${escapeHtml(name)} · Rewards Eligibility Oracle`
    : 'Rewards Eligibility Oracle · The Graph'

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
${isIndexer ? `${INDEXER_HEAD}\n` : ''}<title>${title}</title>
<meta name="description" content="Live rewards eligibility for indexers on The Graph Network, published by the Rewards Eligibility Oracle (GIP-0079).">
<meta property="og:title" content="${title}">
<meta property="og:description" content="Live rewards eligibility for indexers on The Graph Network.">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,${favicon}">
<link rel="stylesheet" href="gds.css">
</head>
<body>
<div id="reo-root">${body}</div>
<script type="application/json" id="reo-data">${serializeProps(props)}</script>
<script type="module" src="app.js"></script>
</body>
</html>
`
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}
