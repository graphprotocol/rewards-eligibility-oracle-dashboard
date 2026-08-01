/**
 * Roster counts. Lives apart from data.js because data.js imports node:fs and
 * must never reach the client bundle; this runs in both environments.
 */
export function summarize(indexers) {
  const counts = {
    total: indexers.length,
    'eligible-active': 0,
    'eligible-grace': 0,
    'ineligible-expired': 0,
    'ineligible-unqualified': 0,
  }
  for (const indexer of indexers) {
    if (indexer.status in counts) counts[indexer.status] += 1
  }
  counts.earning = counts['eligible-active'] + counts['eligible-grace']
  counts.needsAttention = counts['eligible-grace'] + counts['ineligible-expired']
  return counts
}
