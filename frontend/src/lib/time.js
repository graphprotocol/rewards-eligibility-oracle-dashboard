/**
 * Timestamp formatting, shared by the server render and the client bundle.
 *
 * Everything is formatted from UTC parts by hand rather than through
 * toLocaleString: the server and the browser would otherwise disagree about
 * locale and timezone and produce a hydration mismatch. It also keeps the page
 * honest — a reader in UTC+1 seeing "2026-08-04" just after midnight their time
 * needs the clock time and the zone to reconcile it, not a bare date.
 */
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** e.g. "4 Aug 2026, 20:40 UTC" */
export function formatUTC(epochSeconds) {
  if (!epochSeconds) return null
  const d = new Date(epochSeconds * 1000)
  const hh = String(d.getUTCHours()).padStart(2, '0')
  const mm = String(d.getUTCMinutes()).padStart(2, '0')
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${hh}:${mm} UTC`
}

/**
 * Elapsed time, expressed in units rather than calendar terms.
 *
 * Deliberately never says "today": that was computed from elapsed milliseconds,
 * so an oracle run four hours before midnight reported "today" while the date
 * printed next to it was yesterday. Elapsed phrasing cannot contradict the
 * timestamp beside it, and does not depend on the reader's timezone.
 */
export function relativeAge(epochSeconds, nowMs) {
  if (!epochSeconds) return null
  const seconds = Math.max(0, Math.floor((nowMs - epochSeconds * 1000) / 1000))

  if (seconds < 90) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

/** Whole days elapsed, for the staleness threshold copy. */
export function daysSince(epochSeconds, nowMs) {
  if (!epochSeconds) return null
  return Math.floor((nowMs - epochSeconds * 1000) / 86_400_000)
}
