/**
 * Daily eligibility metrics: what the oracle saw, per indexer and per day.
 *
 * The contract says *whether* an indexer is eligible; the metrics subgraph says
 * *why*. Everything here derives from `env.metrics` (see fetch_indexer_metrics
 * in generate_dashboard.py) and from the contract fields already on each
 * indexer. Shared by the server render and the client bundle, so it must stay
 * pure: no clock, no I/O.
 *
 * Three rules from the oracle's publishing design shape this file:
 *
 * - A window day that was never published is unknown, not zero.
 * - Within a published day, an indexer with no row was routed nothing.
 * - The failed_* counters overlap. They name the problem; they never sum.
 */

export const DAY_SECONDS = 86_400

/** Index of each counter in a metrics row. Mirrors METRICS_COLUMNS in Python. */
const COL = {
  day: 0,
  queryAttempts: 1,
  qualifyingQueries: 2,
  qualifyingSubgraphs: 3,
  failedStatus: 4,
  failedLatency: 5,
  failedBlocksBehind: 6,
}

const ZERO = {
  queryAttempts: 0,
  qualifyingQueries: 0,
  qualifyingSubgraphs: 0,
  failedStatus: 0,
  failedLatency: 0,
  failedBlocksBehind: 0,
}

/** Normalizes data.json's `metrics` block. Returns null when there is none. */
export function parseMetrics(raw) {
  if (!raw || typeof raw !== 'object' || !raw.criteria) return null
  const c = raw.criteria
  return {
    subgraphId: raw.subgraph_id ?? null,
    runDate: raw.run_date,
    runDay: Number(raw.run_day),
    runTransaction: raw.run_transaction ?? null,
    runBlock: Number(raw.run_block) || null,
    runTimestamp: Number(raw.run_timestamp) || 0,
    windowStart: Number(raw.window_start_day),
    windowEnd: Number(raw.window_end_day),
    criteria: {
      minOnlineDays: Number(c.min_online_days),
      minSubgraphs: Number(c.min_subgraphs),
      maxLatencyMs: Number(c.max_latency_ms),
      maxBlocksBehind: Number(c.max_blocks_behind),
    },
    publishedDays: (raw.published_days ?? []).map(Number),
    partialDays: (raw.partial_days ?? []).map(Number),
    // Keyed by lowercase address. Kept positional (see COL) because this is
    // embedded in the page.
    indexers: raw.indexers ?? {},
  }
}

/** Only the given addresses' rows, for a page that is about one indexer. */
export function pickMetrics(metrics, addresses) {
  if (!metrics) return null
  const keep = new Set(addresses.map((a) => a.toLowerCase()))
  return {
    ...metrics,
    indexers: Object.fromEntries(Object.entries(metrics.indexers).filter(([a]) => keep.has(a))),
  }
}

/* ------------------------------------------------------------------------ */
/* Dates                                                                    */
/* ------------------------------------------------------------------------ */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

/** Days since 1970-01-01 UTC, from an epoch in seconds. */
export const dayOf = (epochSeconds) => Math.floor(epochSeconds / DAY_SECONDS)

export const dayFromIso = (iso) => Math.floor(Date.parse(`${iso}T00:00:00Z`) / 1000 / DAY_SECONDS)

/** "Oct 5". Built from UTC parts so server and browser agree. */
export function shortDay(day) {
  const d = new Date(day * DAY_SECONDS * 1000)
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`
}

/** "Mon, Oct 5": for tables, where every row is in the same short window. */
export function mediumDay(day) {
  const d = new Date(day * DAY_SECONDS * 1000)
  return `${WEEKDAYS[d.getUTCDay()]}, ${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`
}

/** "Mon, Oct 5, 2026" */
export function longDay(day) {
  const d = new Date(day * DAY_SECONDS * 1000)
  return `${WEEKDAYS[d.getUTCDay()]}, ${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`
}

/* ------------------------------------------------------------------------ */
/* Criteria                                                                 */
/* ------------------------------------------------------------------------ */

/**
 * The nearest announced change to the subgraphs-per-day threshold, the one
 * threshold the published counters can be re-judged against exactly.
 *
 * Upcoming changes come from ELIGIBILITY_CRITERIA.md, not from the chain, and
 * only carry numbers when the prose could be read unambiguously (see
 * _extract_threshold_changes). Without a number there is nothing to apply.
 */
export function pendingChange(upcoming, metrics) {
  if (!metrics) return null
  for (const row of upcoming ?? []) {
    const k = row.changes?.MIN_SUBGRAPHS
    const effectiveDay = dayFromIso(row.effective_date)
    if (k && k !== metrics.criteria.minSubgraphs && effectiveDay > metrics.runDay) {
      return { ...row, effectiveDay, minSubgraphs: k }
    }
  }
  return null
}

/* ------------------------------------------------------------------------ */
/* Per-day                                                                  */
/* ------------------------------------------------------------------------ */

export const isQualifying = (row, minSubgraphs) =>
  row.qualifyingQueries >= 1 && row.qualifyingSubgraphs >= minSubgraphs

/** The largest failed_* counter names the problem. */
export function failureReason(row, minSubgraphs) {
  if (row.queryAttempts === 0) return { key: 'not-routed', label: 'Not routed' }
  if (row.qualifyingQueries === 0) {
    const counters = [
      ['behind', 'Behind chainhead', row.failedBlocksBehind],
      ['slow', 'Too slow', row.failedLatency],
      ['status', 'Error responses', row.failedStatus],
    ].sort((a, b) => b[2] - a[2])
    if (counters[0][2] === 0) return { key: 'unmeasured', label: 'No latency or block data' }
    return { key: counters[0][0], label: counters[0][1] }
  }
  if (row.qualifyingSubgraphs < minSubgraphs) {
    return { key: 'coverage', label: `${row.qualifyingSubgraphs} of ${minSubgraphs} subgraphs` }
  }
  return null
}

/** One entry per window day, judged at `minSubgraphs`. */
export function windowDays(metrics, address, minSubgraphs) {
  const published = new Set(metrics.publishedDays)
  const partial = new Set(metrics.partialDays)
  const rows = new Map(
    (metrics.indexers[address.toLowerCase()] ?? []).map((r) => [
      r[COL.day],
      {
        queryAttempts: r[COL.queryAttempts],
        qualifyingQueries: r[COL.qualifyingQueries],
        qualifyingSubgraphs: r[COL.qualifyingSubgraphs],
        failedStatus: r[COL.failedStatus],
        failedLatency: r[COL.failedLatency],
        failedBlocksBehind: r[COL.failedBlocksBehind],
      },
    ]),
  )

  const out = []
  for (let day = metrics.windowStart; day <= metrics.windowEnd; day++) {
    const base = { day, isFinal: !partial.has(day) }
    if (!published.has(day)) {
      out.push({ ...base, ...ZERO, state: 'unpublished', reason: null })
      continue
    }
    const row = { ...base, ...ZERO, ...rows.get(day) }
    const qualifies = isQualifying(row, minSubgraphs)
    out.push({
      ...row,
      state: qualifies ? 'qualified' : row.queryAttempts === 0 ? 'not-routed' : 'failed',
      reason: qualifies ? null : failureReason(row, minSubgraphs),
    })
  }
  return out
}

const onlineIn = (days, from, to) =>
  days.filter((d) => d.day >= from && d.day <= to && d.state === 'qualified').length

/** Count failed days by reason, most common first. */
export function reasonTally(days) {
  const tally = new Map()
  for (const d of days) {
    if (!d.reason) continue
    const entry = tally.get(d.reason.key) ?? {
      key: d.reason.key,
      label: d.reason.key === 'coverage' ? 'Too few subgraphs' : d.reason.label,
      days: 0,
    }
    entry.days++
    tally.set(d.reason.key, entry)
  }
  return [...tally.values()].sort((a, b) => b.days - a.days)
}

/* ------------------------------------------------------------------------ */
/* Per-indexer                                                              */
/* ------------------------------------------------------------------------ */

/**
 * The next run's verdict, under the criteria that run applies.
 *
 * Its window drops today's oldest day and adds tomorrow, which it sees only
 * partially; today is also partial and gets restated. One day short is
 * therefore genuinely undecided.
 */
function forecast(days, metrics) {
  const kept = onlineIn(days, metrics.runDay + 1 - 28, metrics.runDay)
  const short = metrics.criteria.minOnlineDays - kept
  if (short <= 0) return { key: 'renews', label: 'Will be renewed', variant: 'success', count: kept }
  if (short === 1) return { key: 'at-risk', label: 'Needs 1 more day', variant: 'warning', count: kept }
  return { key: 'lapses', label: 'Won’t be renewed', variant: 'error', count: kept }
}

const UNKNOWN = { key: 'unknown', label: 'Not enough data', variant: 'default' }

export const FORECAST_RANK = { lapses: 0, 'at-risk': 1, unknown: 2, renews: 3 }

/**
 * Everything the roster row and the indexer page show for one indexer.
 *
 * `periodDays` is the contract's eligibility period, used for the worst-case
 * "eligible until" if no further day qualifies.
 */
export function analyzeIndexer(indexer, metrics, pending, periodDays) {
  const days = windowDays(metrics, indexer.address, metrics.criteria.minSubgraphs)
  // The window judged under the pending threshold, whenever it takes effect…
  const pendingDays = pending ? windowDays(metrics, indexer.address, pending.minSubgraphs) : days
  // …and under whatever the next run actually applies.
  const pendingFromRun = (run) => Boolean(pending) && run >= pending.effectiveDay
  const nextDays = pendingFromRun(metrics.runDay + 1) ? pendingDays : days
  const nextK = pendingFromRun(metrics.runDay + 1) ? pending.minSubgraphs : metrics.criteria.minSubgraphs

  const publishedCount = days.filter((d) => d.state !== 'unpublished').length
  // Unknown days can only add online days, so "renews" holds on partial data;
  // a shortfall does not.
  const partial = publishedCount < days.length
  const guard = (f) => (partial && f.key !== 'renews' ? { ...UNKNOWN, count: f.count } : f)

  const online = onlineIn(days, metrics.windowStart, metrics.windowEnd)
  const onlinePending = onlineIn(pendingDays, metrics.windowStart, metrics.windowEnd)
  const next = guard(forecast(nextDays, metrics))
  const renewsUnderCurrent = guard(forecast(days, metrics)).key === 'renews'
  const underPending = guard(forecast(pendingDays, metrics)).key

  // Worst case: no qualifying day from today on. Each later run keeps fewer of
  // today's online days; the last one still holding enough renews once more.
  // Runs on or after a pending change judge the days under it.
  let lastRenewal = null
  for (let run = metrics.runDay + 1; run <= metrics.runDay + 29; run++) {
    const judged = pendingFromRun(run) ? pendingDays : days
    if (onlineIn(judged, run - 28, metrics.runDay) >= metrics.criteria.minOnlineDays) lastRenewal = run
    else break
  }

  const status = indexer.status
  const eligibleNow = status === 'eligible-active' || status === 'eligible-grace'
  const inSubgraph = (metrics.indexers[indexer.address.toLowerCase()] ?? []).some((r) => r[COL.queryAttempts] > 0)
  const untilDay = Number(indexer.eligible_until) ? dayOf(Number(indexer.eligible_until)) : null

  return {
    days,
    pendingDays,
    nextK,
    online,
    onlinePending,
    forecast: next,
    /** Renewing under today's rule, would not be under the pending one. */
    affected: Boolean(pending) && renewsUnderCurrent && underPending !== 'renews' && underPending !== 'unknown',
    worstCaseUntilDay: lastRenewal != null && periodDays ? lastRenewal + periodDays : untilDay,
    untilDay,
    leavingThisWeek: onlineIn(nextDays, metrics.windowStart, metrics.windowStart + 6),
    publishedCount,
    partial,
    inSubgraph,
    eligibleNow,
    /**
     * The window qualifies but the latest run did not renew it: a renewal batch
     * halted before reaching this address. The contract alone cannot tell this
     * apart from failing to qualify.
     */
    qualifiedNotRenewed: status !== 'eligible-active' && !partial && inSubgraph && online >= metrics.criteria.minOnlineDays,
  }
}
