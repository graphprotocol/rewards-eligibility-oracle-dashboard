import { hydrateRoot } from 'react-dom/client'

import { App } from './App.jsx'

/**
 * Hydrates the server-rendered page. The props are embedded in the HTML as a
 * JSON script tag, so the client renders from exactly the same data the server
 * used — no second fetch, and no chance of the two disagreeing.
 */
const payload = document.getElementById('reo-data')
if (payload) {
  const props = JSON.parse(payload.textContent)
  hydrateRoot(document.getElementById('reo-root'), <App {...props} />)
}
