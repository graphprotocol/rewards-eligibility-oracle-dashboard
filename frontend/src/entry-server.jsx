import { renderToString } from 'react-dom/server'

import { App } from './App.jsx'

/**
 * renderToString, not renderToStaticMarkup: only the former emits the comment
 * separators React needs to hydrate adjacent text nodes. renderToStaticMarkup
 * strips them, which produces a hydration mismatch (React error #418).
 */
export function renderPage(props) {
  return renderToString(<App {...props} />)
}

/**
 * The official logomark, re-exported for the favicon. It is bundled into this
 * file, so the prerenderer never has to read node_modules — which do not exist
 * in the runtime image.
 */
export { theGraphLogo } from './lib/logo.js'
