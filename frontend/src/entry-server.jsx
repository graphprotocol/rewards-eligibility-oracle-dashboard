import { renderToString } from 'react-dom/server'

import { App } from './App.jsx'
import { documentHtml } from './lib/document.js'
import { theGraphLogo } from './lib/logo.js'

/**
 * renderToString, not renderToStaticMarkup: only the former emits the comment
 * separators React needs to hydrate adjacent text nodes. renderToStaticMarkup
 * strips them, which produces a hydration mismatch (React error #418).
 */
export function renderPage(props) {
  return renderToString(<App {...props} />)
}

/**
 * The official logomark as a data-URI favicon, taken from the same source as
 * the masthead so the two always match. `currentcolor` is meaningless in a
 * favicon, so brand purple is substituted.
 */
const FAVICON = encodeURIComponent(theGraphLogo.replace('currentcolor', '#6f4cff'))

/**
 * Renders a complete HTML document from props built by buildProps().
 *
 * This is the single rendering entry point. The prerenderer writes its output
 * to disk; the serverless render function returns it as a response. Neither
 * assembles markup of its own, so the two can never drift.
 */
export function renderDocument(props) {
  return documentHtml({ body: renderPage(props), favicon: FAVICON, props })
}

/**
 * Re-exported so a caller needs only this bundle — which vite builds
 * self-contained (ssr.noExternal), so the runtime needs a node binary but no
 * node_modules.
 */
export { theGraphLogo } from './lib/logo.js'
export { parseDashboardData } from './lib/data.js'
export { buildProps, NoDataError, VERSION } from './lib/document.js'
