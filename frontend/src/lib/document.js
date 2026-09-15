/**
 * Assembles the HTML document around a rendered body.
 *
 * Pure string work — no React, no filesystem — so it can be imported from
 * source by any caller. The React half lives in entry-server.jsx, which
 * combines the two into renderDocument().
 */

/** Bumped by hand; shown in the footer so a deploy can be identified on sight. */
export const VERSION = 'v0.5.0'

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
export function buildProps(data, { now, version = VERSION }) {
  const { environments, generatedAt, generatedAtEpoch, criteria } = data

  if (environments.length === 0) {
    throw new NoDataError('No environments in dashboard data — refusing to render an empty page.')
  }

  // Default to the first network that actually has data, so the page never
  // opens on an empty table when a populated one exists.
  const activeId = environments.find((e) => e.available)?.id ?? environments[0].id

  return { environments, activeId, generatedAt, generatedAtEpoch, version, now, criteria }
}

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

export function documentHtml({ body, favicon, props }) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rewards Eligibility Oracle · The Graph</title>
<meta name="description" content="Live rewards eligibility for indexers on The Graph Network, published by the Rewards Eligibility Oracle (GIP-0079).">
<meta property="og:title" content="Rewards Eligibility Oracle · The Graph">
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
