/**
 * Eligibility domain logic, shared by the server render and the client bundle.
 *
 * The four-state model comes from GIP-0079 and is the one part of the previous
 * dashboard the critique rated as sound. What was missing was any expression of
 * it: Expired and Unqualified rendered as the same badge, and the grace
 * countdown — the defining number in the spec — was never computed at all.
 */

/** Maps an oracle status onto a GDS `Status` variant and human-facing copy. */
export const STATUS_META = {
  'eligible-active': {
    variant: 'success',
    label: 'Eligible',
    // Reassurance for the good case: the previous dashboard gave an Active
    // indexer a bare green pill and nothing else.
    summary: 'Renewed in the latest oracle update.',
  },
  'eligible-grace': {
    variant: 'warning',
    label: 'Grace',
    summary: 'Still earning rewards, but not renewed in the latest update.',
  },
  'ineligible-expired': {
    variant: 'error',
    label: 'Expired',
    summary: 'The grace period lapsed. Rewards eligibility has been lost.',
  },
  'ineligible-unqualified': {
    // Deliberately not `error`: "never qualified" and "qualified then lapsed"
    // are different situations needing different actions, and collapsing them
    // into one red badge is the exact defect this rebuild is fixing.
    variant: 'default',
    label: 'Unqualified',
    summary: 'Has not yet met the eligibility criteria.',
  },
}

export const STATUS_ORDER = [
  'eligible-grace',
  'ineligible-expired',
  'ineligible-unqualified',
  'eligible-active',
]

export function statusMeta(status) {
  return STATUS_META[status] ?? {
    variant: 'default',
    label: 'Unknown',
    summary: 'The oracle reported a status this dashboard does not recognize.',
  }
}

/** True for the two states that still earn rewards. */
export function isEarning(status) {
  return status === 'eligible-active' || status === 'eligible-grace'
}

/**
 * Days remaining before eligibility lapses.
 *
 * `eligibility_renewal_time` is a unix timestamp of the last renewal;
 * `eligibilityPeriod` is the oracle's window in seconds (1209600 = 14 days).
 * Returns null when the indexer has never renewed, so callers can distinguish
 * "no deadline" from "zero days left".
 */
export function daysRemaining(indexer, eligibilityPeriod, now = Date.now()) {
  const renewedAt = Number(indexer?.eligibility_renewal_time) || 0
  const period = Number(eligibilityPeriod) || 0
  if (!renewedAt || !period) return null

  const expiresAt = (renewedAt + period) * 1000
  const msLeft = expiresAt - now
  return Math.ceil(msLeft / 86_400_000)
}

/**
 * Badge copy that explains itself, so the page no longer needs a detached
 * legend card sitting between the controls and the table.
 */
export function statusDetail(indexer, eligibilityPeriod, now = Date.now()) {
  const left = daysRemaining(indexer, eligibilityPeriod, now)
  switch (indexer.status) {
    case 'eligible-grace':
      if (left === null) return 'needs renewal'
      return left <= 0 ? 'expires today' : `${left} day${left === 1 ? '' : 's'} left`
    case 'eligible-active':
      return left === null || left <= 0 ? 'renewed' : `renews in ${left} days`
    case 'ineligible-expired':
      return indexer.last_status_change_date ? `lapsed ${indexer.last_status_change_date}` : 'lapsed'
    case 'ineligible-unqualified':
      return 'never renewed'
    default:
      return ''
  }
}

/** Explorer chain slug, derived rather than hardcoded to arbitrum-one. */
export function explorerChain(networkId) {
  return String(networkId) === '421614' ? 'arbitrum-sepolia' : 'arbitrum-one'
}

export function arbiscanBase(networkId) {
  return String(networkId) === '421614'
    ? 'https://sepolia.arbiscan.io'
    : 'https://arbiscan.io'
}
