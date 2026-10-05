import { useMemo, useState } from 'react'
import {
  Address,
  Avatar,
  Breadcrumbs,
  Button,
  ButtonGroup,
  Card,
  CodeInline,
  CopyButton,
  DescriptionList,
  Divider,
  Link,
  Select,
  Status,
  Table,
  Tooltip,
} from '@graphprotocol/gds-react'
import { ButtonOrLink } from '@graphprotocol/gds-react/base'
import { ArrowRightInteractiveIcon, ArrowSquareOutIcon } from '@graphprotocol/gds-react/icons'
import { createIdenticon } from '@graphprotocol/gds-utils'

import { CELLS, DAY_STATE, DayStrip, Notice, StripLegend } from './components/metrics.jsx'
import {
  DAY_SECONDS,
  analyzeIndexer,
  longDay,
  mediumDay,
  pendingChange,
  reasonTally,
  shortDay,
  windowDays,
} from './lib/metrics.js'
import { arbiscanBase, explorerChain, statusMeta } from './lib/status.js'
import { formatUTC } from './lib/time.js'

const METRICS_SUBGRAPH_REPO = 'https://github.com/graphprotocol/rewards-eligibility-oracle-subgraph'

/**
 * One indexer: the contract's verdict, then the daily metrics that explain it.
 *
 * The page answers, in order: where do I stand (status, until when, what the
 * next run will do, how much margin), why (each day and what failed it), and
 * what a pending criteria change does to me.
 *
 * Without metrics (Arbitrum Sepolia, or the subgraph could not be read) it is
 * the contract half alone.
 */
export function IndexerPage({ env, criteria, now, rootHref }) {
  const indexer = env.indexers[0]
  if (!indexer) {
    return (
      <Card>
        <p className="text-14 text-muted">This indexer is not on the {env.label} roster.</p>
      </Card>
    )
  }

  const name = indexer.ens_name || null
  const shortAddress = `${indexer.address.slice(0, 6)}…${indexer.address.slice(-4)}`
  const meta = statusMeta(indexer.status)
  const metrics = env.metrics
  const periodDays = env.eligibilityPeriod ? Math.round(env.eligibilityPeriod / DAY_SECONDS) : null
  const pending = metrics ? pendingChange(criteria?.upcoming, metrics) : null
  const a = metrics ? analyzeIndexer(indexer, metrics, pending, periodDays) : null

  return (
    <>
      <div className="flex flex-col gap-6">
        <Breadcrumbs>
          <Breadcrumbs.Item href={rootHref} current={false}>
            Rewards Eligibility Oracle
          </Breadcrumbs.Item>
          <Breadcrumbs.Item href={rootHref} current={false}>
            {env.label}
          </Breadcrumbs.Item>
          <Breadcrumbs.Item current>{name ?? shortAddress}</Breadcrumbs.Item>
        </Breadcrumbs>

        <header className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-4">
            <Avatar src={createIdenticon(indexer.address)} alt="" shape="rounded" size="xlarge" />
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-24 font-medium break-all">{name ?? shortAddress}</h1>
                <Status variant={meta.variant}>{meta.label}</Status>
              </div>
              <Address address={indexer.address} size="small" />
            </div>
          </div>
          <ButtonGroup size="small">
            <Button
              href={`https://thegraph.com/explorer/profile/${indexer.address}?view=Indexing&chain=${explorerChain(env.networkId)}`}
              addonAfter={ArrowSquareOutIcon}
            >
              Explorer
            </Button>
            <Button href={`${arbiscanBase(env.networkId)}/address/${indexer.address}`} addonAfter={ArrowSquareOutIcon}>
              Arbiscan
            </Button>
          </ButtonGroup>
        </header>
      </div>

      {a && <IndexerNotices a={a} metrics={metrics} pending={pending} />}

      <HeadlineStats indexer={indexer} a={a} metrics={metrics} pending={pending} meta={meta} />

      {a ? (
        <>
          {/* With no query data at all there is nothing to chart: the notice
              above says why, and every day would read "Not routed". */}
          {a.inSubgraph && (
            <>
              <WindowSection a={a} metrics={metrics} pending={pending} />
              <DailyTable a={a} />
              <Simulator a={a} indexer={indexer} metrics={metrics} pending={pending} />
            </>
          )}
          <Provenance indexer={indexer} metrics={metrics} env={env} />
        </>
      ) : (
        <Card>
          <div className="flex flex-col gap-2">
            <h2 className="text-18 font-medium">No daily metrics</h2>
            <p className="text-14 text-muted">
              {env.networkId === '42161'
                ? 'The metrics subgraph could not be read in the latest refresh. Eligibility above comes from the contract and is current.'
                : `The oracle publishes daily metrics for Arbitrum One only. Eligibility on ${env.label} comes from the contract alone.`}
            </p>
          </div>
        </Card>
      )}
    </>
  )
}

/** Only the states the contract alone cannot express get a notice. */
function IndexerNotices({ a, metrics, pending }) {
  const span = metrics.windowEnd - metrics.windowStart + 1
  const notices = []
  if (!a.inSubgraph) {
    notices.push(
      <Notice key="absent" title="No query data in this window">
        The gateway routed no queries to this indexer in the last {span} days, so the oracle had
        nothing to evaluate. That is about routing and allocations, not response quality.
      </Notice>,
    )
  }
  if (a.qualifiedNotRenewed) {
    notices.push(
      <Notice key="stalled" tone="info" title="Qualified, but not renewed by the latest run">
        This window has {a.online} online days, but the contract shows no renewal from the latest
        run. A renewal batch may have stopped before reaching this indexer. Nothing is needed from
        you; the next run should renew it.
      </Notice>,
    )
  }
  if (a.affected) {
    notices.push(
      <Notice
        key="affected"
        tone="warning"
        title={`The ${shortDay(pending.effectiveDay)} criteria change affects this indexer`}
        action={
          <Button size="small" href="#simulator-heading" addonAfter={ArrowRightInteractiveIcon}>
            See the days
          </Button>
        }
      >
        {a.online} online days under today’s rule, {a.onlinePending} at {pending.minSubgraphs} subgraphs
        per day.
        {a.untilDay != null &&
          ` Eligibility still runs until ${shortDay(a.untilDay)}; it will not be renewed after that unless more days reach ${pending.minSubgraphs} subgraphs.`}
      </Notice>,
    )
  }
  if (a.partial) {
    notices.push(
      <Notice key="partial" tone="info" title={`${a.publishedCount} of ${span} days published`}>
        The rest of the window has not been published to the metrics subgraph, so those days are
        unknown and online-day counts are a lower bound. Eligibility itself always comes from the
        contract.
      </Notice>,
    )
  }
  return notices.length > 0 ? <div className="flex flex-col gap-4">{notices}</div> : null
}

/** Stat row, as in GDS's details-page pattern: a dl separated by dividers. */
function HeadlineStats({ indexer, a, metrics, pending, meta }) {
  const renewed = Number(indexer.eligibility_renewal_time) || 0
  const items = [
    {
      label: 'Contract status',
      value: (
        <Status variant={meta.variant} size="large">
          {meta.label}
        </Status>
      ),
      sub: renewed ? `Last renewed ${formatUTC(renewed)}` : 'Never renewed',
    },
    {
      label: 'Eligible until',
      value: indexer.eligible_until_short || 'Not set',
      sub: !a?.eligibleNow
        ? 'No active eligibility period'
        : a.worstCaseUntilDay > a.untilDay
          ? `At least ${shortDay(a.worstCaseUntilDay)} even if no further day qualifies`
          : 'Fixed period. Not qualifying does not shorten it',
    },
  ]
  if (a) {
    const span = metrics.windowEnd - metrics.windowStart + 1
    items.push(
      {
        label: `Next run · ${shortDay(metrics.runDay + 1)}`,
        value: (
          <Status variant={a.forecast.variant} size="large">
            {a.forecast.label}
          </Status>
        ),
        sub:
          a.forecast.key === 'unknown'
            ? `${a.publishedCount} of ${span} days published so far`
            : `${a.forecast.count} of ${metrics.criteria.minOnlineDays} online days at ${a.nextK} ${a.nextK === 1 ? 'subgraph' : 'subgraphs'}/day`,
      },
      {
        label: 'Online days',
        value: (
          <>
            {a.online} <span className="text-14 text-muted">of {span}</span>
          </>
        ),
        sub:
          a.leavingThisWeek > 0
            ? `${metrics.criteria.minOnlineDays} required · ${a.leavingThisWeek} leave the window this week`
            : `${metrics.criteria.minOnlineDays} required`,
      },
    )
  }

  return (
    <dl className="grid gap-6 sm:grid-cols-2 lg:flex lg:gap-8">
      {items.map((item, i) => (
        <div key={item.label} className="flex gap-8 lg:flex-1">
          {i > 0 && <Divider orientation="vertical" className="max-lg:hidden" />}
          <div className="flex flex-col gap-1">
            <dt className="text-12 text-caption text-muted">{item.label}</dt>
            <dd className="text-20 font-medium">{item.value}</dd>
            {item.sub && <dd className="text-14 text-muted">{item.sub}</dd>}
          </div>
        </div>
      ))}
    </dl>
  )
}

const REASON_HELP = {
  'not-routed': 'The gateway sent no queries. That is about routing and allocations, not response quality.',
  behind: 'Most failing responses were too far behind chainhead.',
  slow: 'Most failing responses were too slow.',
  status: 'Most failing responses were not 200 OK.',
  coverage: 'Qualifying queries landed on fewer subgraphs than the day requires.',
  unmeasured: 'Attempts carried no latency or chainhead data, so none could qualify.',
}

/** Open on the most recent day worth explaining: the last failed one, else the last complete one. */
function defaultDay(days) {
  const recent = days.filter((d) => d.isFinal && d.state !== 'unpublished')
  const failed = [...recent].reverse().find((d) => d.state === 'failed')
  return (failed ?? recent.at(-1) ?? days.at(-1)).day
}

function WindowSection({ a, metrics, pending }) {
  const [selected, setSelected] = useState(() => defaultDay(a.days))
  const day = a.days.find((d) => d.day === selected)

  return (
    <section aria-labelledby="window-heading" className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-1">
            <h2 id="window-heading" className="text-18 font-medium">
              Last {a.days.length} days
            </h2>
            <p className="text-14 text-muted">
              Each day as the oracle counted it. Select a day for its numbers.
            </p>
          </div>
          <DayStrip days={a.days} leavingThisWeek={a.leavingThisWeek} selected={selected} onSelect={setSelected} />
          <StripLegend minOnlineDays={metrics.criteria.minOnlineDays} />
          <Divider />
          <DayDetail day={day} criteria={metrics.criteria} />
        </div>
      </Card>
      <Card>
        <ReasonPanel a={a} pending={pending} />
      </Card>
    </section>
  )
}

function DayDetail({ day, criteria }) {
  const meta = DAY_STATE[day.state]
  const title = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-16 font-medium">{longDay(day.day)}</h3>
      <Status variant={meta.variant}>{day.reason ? day.reason.label : meta.label}</Status>
    </div>
  )
  if (day.state === 'unpublished') {
    return (
      <div className="flex flex-col gap-2">
        {title}
        <p className="text-14 text-muted">
          This day was never published to the metrics subgraph. It is unknown, not zero.
        </p>
      </div>
    )
  }
  const n = (v) => v.toLocaleString('en-US')
  return (
    <div className="flex flex-col gap-4">
      {title}
      {!day.isFinal && (
        <p className="text-14 text-muted">
          Partial: published with the day still in progress. The next run restates it in full.
        </p>
      )}
      {day.reason && <p className="text-14 text-muted">{REASON_HELP[day.reason.key]}</p>}
      <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <DescriptionList size="small">
          <DescriptionList.Item label="Qualifying subgraphs">{day.qualifyingSubgraphs}</DescriptionList.Item>
          <DescriptionList.Item label="Qualifying queries">{n(day.qualifyingQueries)}</DescriptionList.Item>
          <DescriptionList.Item label="Query attempts">{n(day.queryAttempts)}</DescriptionList.Item>
        </DescriptionList>
        <DescriptionList size="small">
          <DescriptionList.Item label="Not 200 OK">{n(day.failedStatus)}</DescriptionList.Item>
          <DescriptionList.Item label={`${n(criteria.maxLatencyMs)} ms or slower`}>
            {n(day.failedLatency)}
          </DescriptionList.Item>
          <DescriptionList.Item label={`${n(criteria.maxBlocksBehind)}+ blocks behind`}>
            {n(day.failedBlocksBehind)}
          </DescriptionList.Item>
        </DescriptionList>
      </div>
      <p className="text-12 text-muted">
        One response can fail more than one check, so the failure counts overlap and need not add up.
      </p>
    </div>
  )
}

/** The dominant failure reason per day, tallied: what to fix, not a score. */
function ReasonPanel({ a, pending }) {
  const tally = reasonTally(a.days)
  const qualified = a.days.filter((d) => d.state === 'qualified').length
  const lost = pending
    ? a.days.filter((d, i) => d.state === 'qualified' && a.pendingDays[i].state !== 'qualified').length
    : 0
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-18 font-medium">Why days did not count</h2>
        <p className="text-14 text-muted">
          {qualified} of {a.publishedCount} published days counted.
          {tally.length > 0 && ' For the rest, the main reason:'}
        </p>
      </div>
      {tally.length > 0 && (
        <ul className="flex flex-col">
          {tally.map((t) => (
            <li key={t.key} className="flex flex-col gap-1 py-3 not-first:border-t not-first:border-subtle">
              <div className="flex items-center justify-between gap-4 text-14">
                <Status variant={t.key === 'not-routed' ? 'default' : 'error'}>{t.label}</Status>
                <span className="text-muted">
                  {t.days} {t.days === 1 ? 'day' : 'days'}
                </span>
              </div>
              <p className="text-12 text-muted">{REASON_HELP[t.key]}</p>
            </li>
          ))}
        </ul>
      )}
      {lost > 0 && (
        <div className="flex flex-col gap-1 border-t border-subtle pt-4">
          <h3 className="text-14 font-medium">
            From {shortDay(pending.effectiveDay)}, at {pending.minSubgraphs} subgraphs per day
          </h3>
          <p className="text-14 text-muted">
            {lost} of these online days would not count, leaving {a.onlinePending}. Each needed more
            subgraphs with a qualifying query, not better responses.
          </p>
        </div>
      )}
    </div>
  )
}

/**
 * Re-tallies the published counters under other thresholds. Exact for
 * subgraphs-per-day and online-days; latency and blocks-behind decide what
 * counts as qualifying in the first place, so they cannot be simulated.
 */
function Simulator({ a, indexer, metrics, pending }) {
  const current = metrics.criteria
  const [k, setK] = useState(pending?.minSubgraphs ?? current.minSubgraphs)
  const [minDays, setMinDays] = useState(current.minOnlineDays)
  const sim = useMemo(() => windowDays(metrics, indexer.address, k), [metrics, indexer, k])
  const online = sim.filter((d) => d.state === 'qualified').length

  // The axis is about the threshold, not the peak: indexers serve anywhere from
  // 1 to 1,000+ subgraphs a day, and a linear scale to the peak flattens the
  // line that decides the day. Taller bars run off the top; tooltips are exact.
  const peak = Math.max(...a.days.map((d) => d.qualifyingSubgraphs))
  const ceiling = Math.min(Math.max(Math.ceil(peak / 5) * 5, 10), Math.max(Math.ceil((k * 3) / 5) * 5, 10))
  const clipped = peak > ceiling
  const pct = (n) => `${(Math.min(n, ceiling) / ceiling) * 100}%`
  const columns = { gridTemplateColumns: `repeat(${sim.length}, minmax(0, 1fr))` }
  const subgraphOptions = [...new Set([1, 2, 3, 4, 5, 6, 8, 10, current.minSubgraphs, k])].sort((x, y) => x - y)
  const dayOptions = [...new Set([3, 5, 7, 10, 14, current.minOnlineDays])].sort((x, y) => x - y)

  const results = [
    { label: `Today’s rule · ${current.minSubgraphs} ${current.minSubgraphs === 1 ? 'subgraph' : 'subgraphs'}`, days: a.online, need: current.minOnlineDays },
    pending && { label: `From ${shortDay(pending.effectiveDay)} · ${pending.minSubgraphs} subgraphs`, days: a.onlinePending, need: current.minOnlineDays },
    { label: `Simulated · ${k} ${k === 1 ? 'subgraph' : 'subgraphs'}, ${minDays} days`, days: online, need: minDays },
  ].filter(Boolean)

  return (
    <section aria-labelledby="simulator-heading">
      <Card>
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div className="flex max-w-160 flex-col gap-1">
              <h2 id="simulator-heading" className="text-18 font-medium">
                Criteria simulator
              </h2>
              <p className="text-14 text-muted">
                Qualifying subgraphs per day against a threshold.
                {pending && ` From ${shortDay(pending.effectiveDay)} the oracle requires ${pending.minSubgraphs}.`} Latency and
                chainhead limits cannot be simulated, since they decide which queries qualify in the
                first place.
              </p>
            </div>
            <div className="flex flex-wrap gap-4">
              <Select
                label="Subgraphs per day"
                size="small"
                value={k}
                onValueChange={(v) => v != null && setK(v)}
                options={subgraphOptions}
                optionLabel={(v) =>
                  v === pending?.minSubgraphs
                    ? `${v} (from ${shortDay(pending.effectiveDay)})`
                    : v === current.minSubgraphs
                      ? `${v} (today)`
                      : String(v)
                }
                className="w-48"
              />
              <Select
                label="Online days required"
                size="small"
                value={minDays}
                onValueChange={(v) => v != null && setMinDays(v)}
                options={dayOptions}
                optionLabel={(v) => (v === current.minOnlineDays ? `${v} (today)` : String(v))}
                className="w-40"
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-2">
              <div className="flex h-40 flex-col justify-between text-end text-10 text-muted">
                <span>{clipped ? `${ceiling}+` : ceiling}</span>
                <span>0</span>
              </div>
              <div className="h-40 border-b border-muted">
                <div
                  className={`grid h-full items-end gap-0.5 sm:gap-1 *:min-h-0.5 ${CELLS} *:rounded-t-4 *:rounded-b-none *:data-[state=not-routed]:bg-transparent *:data-[state=failed]:bg-status-error-muted`}
                  style={columns}
                >
                  {sim.map((d) => (
                    <Tooltip
                      key={d.day}
                      content={`${longDay(d.day)} · ${d.state === 'unpublished' ? 'no data' : `${d.qualifyingSubgraphs} qualifying subgraphs`}`}
                    >
                      <ButtonOrLink
                        aria-label={`${longDay(d.day)}: ${d.qualifyingSubgraphs} qualifying subgraphs`}
                        data-state={d.state}
                        style={{ height: pct(d.qualifyingSubgraphs) }}
                      />
                    </Tooltip>
                  ))}
                </div>
                <div
                  className="pointer-events-none absolute inset-x-0 border-t-2 border-dashed border-strong"
                  style={{ bottom: pct(k) }}
                >
                  <span className="absolute inset-e-0 -top-5 rounded-4 bg-canvas px-1 text-10">
                    {k} {k === 1 ? 'subgraph' : 'subgraphs'}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex justify-between ps-5 text-12 text-muted">
              <span>{shortDay(metrics.windowStart)}</span>
              <span>{shortDay(metrics.windowEnd)}</span>
            </div>
          </div>

          <Divider />

          <dl className="grid gap-6 sm:grid-cols-3">
            {results.map((r) => {
              const ok = r.days >= r.need
              return (
                <div key={r.label} className="flex flex-col gap-1">
                  <dt className="text-12 text-caption text-muted">{r.label}</dt>
                  <dd className="text-20 font-medium">
                    {r.days} <span className="text-14 text-muted">online days</span>
                  </dd>
                  <dd>
                    <Status variant={ok ? 'success' : a.partial ? 'default' : 'error'}>
                      {ok
                        ? 'Would qualify'
                        : a.partial
                          ? `Short of ${r.need} on published days`
                          : `Short of ${r.need}, would not qualify`}
                    </Status>
                  </dd>
                </div>
              )
            })}
          </dl>
        </div>
      </Card>
    </section>
  )
}

const INITIAL_DAILY_ROWS = 7

/** What was published, as published: no pending criteria here, that is the simulator's job. */
function DailyTable({ a }) {
  const [all, setAll] = useState(false)
  const newest = [...a.days].reverse()
  const rows = all ? newest : newest.slice(0, INITIAL_DAILY_ROWS)

  return (
    <section aria-labelledby="daily-heading" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id="daily-heading" className="text-18 font-medium">
          Daily breakdown
        </h2>
        <p className="text-14 text-muted">
          The published counters, newest first. Subgraphs and queries count qualifying ones only.
          The three failure columns overlap: one slow, stale response counts in both.
        </p>
      </div>
      <Table>
        <Table.Header>
          {/* Short headers on purpose: eight columns of monospace captions only
              fit the page width at this length. The paragraph above says what
              "Subgraphs" and "Queries" count. */}
          <Table.HeaderCell width="fr">Day</Table.HeaderCell>
          <Table.HeaderCell>Result</Table.HeaderCell>
          <Table.HeaderCell align="end">Subgraphs</Table.HeaderCell>
          <Table.HeaderCell align="end">Queries</Table.HeaderCell>
          <Table.HeaderCell align="end">Attempts</Table.HeaderCell>
          <Table.HeaderCell align="end">Not 200</Table.HeaderCell>
          <Table.HeaderCell align="end">Slow</Table.HeaderCell>
          <Table.HeaderCell align="end">Behind</Table.HeaderCell>
        </Table.Header>
        <Table.Body>
          {rows.map((d) => {
            const meta = DAY_STATE[d.state]
            const unknown = d.state === 'unpublished'
            const num = (v) => (unknown ? '–' : v.toLocaleString('en-US'))
            return (
              <Table.Row key={d.day}>
                <Table.Cell>
                  {mediumDay(d.day)}
                  {!d.isFinal && !unknown && <span className="text-muted"> · partial</span>}
                </Table.Cell>
                <Table.Cell>
                  <Status variant={meta.variant}>{d.reason ? d.reason.label : meta.label}</Status>
                </Table.Cell>
                <Table.Cell>{num(d.qualifyingSubgraphs)}</Table.Cell>
                <Table.Cell>{num(d.qualifyingQueries)}</Table.Cell>
                <Table.Cell>{num(d.queryAttempts)}</Table.Cell>
                <Table.Cell>{num(d.failedStatus)}</Table.Cell>
                <Table.Cell>{num(d.failedLatency)}</Table.Cell>
                <Table.Cell>{num(d.failedBlocksBehind)}</Table.Cell>
              </Table.Row>
            )
          })}
        </Table.Body>
      </Table>
      {!all && newest.length > INITIAL_DAILY_ROWS && (
        <Link href={undefined} onClick={() => setAll(true)} addonAfter={ArrowRightInteractiveIcon} className="self-start text-14">
          Show all {newest.length} days
        </Link>
      )}
    </section>
  )
}

function Provenance({ indexer, metrics, env }) {
  const query = `{
  indexer(id: "${indexer.address.toLowerCase()}") {
    onlineDays
    daysWithAttempts
    lastDayWithAttempts { date }
    days(
      where: { dayNumber_gte: ${metrics.windowStart} }
      orderBy: dayNumber
      orderDirection: desc
    ) {
      date isFinal isOnlineDay
      queryAttempts qualifyingQueries qualifyingSubgraphs
      failedStatus failedLatency failedBlocksBehind
    }
  }
}`
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section aria-labelledby="query-heading" className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-4">
          <h2 id="query-heading" className="text-18 font-medium">
            Query this yourself
          </h2>
          <CopyButton size="small" value={query}>
            Copy query
          </CopyButton>
        </div>
        <p className="text-14 text-muted">
          Everything above comes from the{' '}
          <Link href={METRICS_SUBGRAPH_REPO}>eligibility metrics subgraph</Link>. Build your own
          alerting on it.
        </p>
        {/* Not CodeBlock: its syntax highlighter adds ~9 MB to the single-file
            client bundle this page ships. */}
        <pre className="overflow-x-auto rounded-8 border border-muted bg-subtle p-4 font-mono text-12">
          {query}
        </pre>
      </section>
      <section aria-labelledby="source-heading" className="flex flex-col gap-3">
        <h2 id="source-heading" className="text-18 font-medium">
          Where these numbers come from
        </h2>
        <DescriptionList size="small">
          <DescriptionList.Item label="Eligibility">RewardsEligibilityOracle contract</DescriptionList.Item>
          <DescriptionList.Item label="Daily metrics">Metrics subgraph</DescriptionList.Item>
          <DescriptionList.Item label="Latest run">
            {metrics.runTimestamp ? formatUTC(metrics.runTimestamp) : metrics.runDate}
          </DescriptionList.Item>
          <DescriptionList.Item label="Window">
            {shortDay(metrics.windowStart)} – {shortDay(metrics.windowEnd)},{' '}
            {metrics.windowEnd - metrics.windowStart + 1} days inclusive
          </DescriptionList.Item>
          <DescriptionList.Item label="Criteria">
            <CodeInline>
              {`${metrics.criteria.minOnlineDays}-${metrics.criteria.minSubgraphs}-${metrics.criteria.maxLatencyMs}-${metrics.criteria.maxBlocksBehind}`}
            </CodeInline>
          </DescriptionList.Item>
          {metrics.runTransaction && (
            <DescriptionList.Item
              label="Metrics transaction"
              action={
                <Button href={`${arbiscanBase(env.networkId)}/tx/${metrics.runTransaction}`}>
                  <ArrowSquareOutIcon alt="View on Arbiscan" />
                </Button>
              }
            >
              <Address address={metrics.runTransaction} />
            </DescriptionList.Item>
          )}
        </DescriptionList>
      </section>
    </div>
  )
}

