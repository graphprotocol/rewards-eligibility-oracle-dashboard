import { useEffect, useMemo, useState } from 'react'
import { GDSProvider, Card, Status, Table, Divider, ThemeSwitcher } from '@graphprotocol/gds-react'

import { theGraphLogo } from './lib/logo.js'

import { statusMeta, statusDetail, STATUS_ORDER, explorerChain, arbiscanBase } from './lib/status.js'
import { summarize } from './lib/summary.js'

/**
 * The Graph Council's vote ratifying GIP-0079 — GGP-0058, passed 6-0 and closed
 * 2025-11-30. This is the actual ratification, as distinct from the GIP text.
 */
const COUNCIL_VOTE_URL =
  'https://snapshot.org/#/s:council.graphprotocol.eth/proposal/0x68265745988129067231366a8c56e9e13e32693522dd80930a9cc557eebabd22'

/** The GIP the council ratified (Stage: Approved). */
const GIP_0079_URL =
  'https://github.com/graphprotocol/graph-improvement-proposals/blob/main/gips/0079.md'

/** The GIP's discussion thread. */
const GIP_0079_FORUM_URL =
  'https://forum.thegraph.com/t/gip-0079-indexer-rewards-eligibility-oracle/6734'

/**
 * The page is split into the two jobs the critique found were being served at
 * equal weight and therefore served badly:
 *
 *   1. "Am I eligible, and what do I do?"  — the indexer, answered first.
 *   2. "Is the oracle healthy?"            — the foundation, answered below.
 *
 * The same component tree renders on the server and hydrates on the client, so
 * there is one implementation of the UI rather than a static version plus a
 * separate pile of DOM-poking JavaScript.
 */
export function App({ environments, activeId, generatedAt, version, now, criteria }) {
  const [networkId, setNetworkId] = useState(activeId)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sort, setSort] = useState({ column: 'status', direction: 'ascending' })

  // Read deep-link state after mount rather than during render: the server has
  // no URL, so doing this inline would cause a hydration mismatch.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const network = params.get('network')
    const indexer = params.get('indexer')
    const status = params.get('status')
    if (network && environments.some((e) => e.id === network)) setNetworkId(network)
    if (indexer) setQuery(indexer)
    if (status) setStatusFilter(status)
  }, [environments])

  const active = environments.find((e) => e.id === networkId) ?? environments[0]

  return (
    <GDSProvider defaultTheme="dark" persistTheme="localStorage">
      <div className="flex min-h-screen flex-col bg-canvas text-default">
        <a
          href="#roster-heading"
          className="sr-only rounded-4 bg-brand-default px-4 py-2 text-14 text-white focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
        >
          Skip to indexer list
        </a>
        <Masthead environments={environments} active={active} onSelect={setNetworkId} />
        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-14 px-4 py-12 md:px-8">
          <SelfLookup env={active} query={query} onQuery={setQuery} now={now} />
          <EligibilityCriteria criteria={criteria} />
          <OracleHealth
            env={active}
            now={now}
            query={query}
            statusFilter={statusFilter}
            onStatusFilter={setStatusFilter}
            sort={sort}
            onSort={setSort}
            onReset={() => {
              setStatusFilter('all')
              setQuery('')
            }}
          />
        </main>
        <SiteFooter generatedAt={generatedAt} version={version} env={active} />
      </div>
    </GDSProvider>
  )
}

function Masthead({ environments, active, onSelect }) {
  return (
    <header className="border-b border-subtle">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 md:px-8">
        <a href="https://thegraph.com" className="flex items-center gap-3 no-underline">
          <GraphMark />
          <span className="text-16 font-semibold text-default">The Graph</span>
        </a>

        <div className="ml-auto flex items-center gap-2">
          <NetworkSwitch environments={environments} active={active} onSelect={onSelect} />
          <ThemeSwitcher />
        </div>
      </div>
    </header>
  )
}

/**
 * The Graph's official logomark, imported from @graphprotocol/gds-icons so it
 * tracks the design system rather than being a copy that can drift. The asset
 * uses fill="currentcolor", so it takes its colour from the surrounding text.
 */
function GraphMark() {
  return (
    <span
      role="img"
      aria-label="The Graph"
      // GDS emits no text-brand-* utility, so the token is referenced directly.
      // Brand purple here matches the favicon and the thegraph.com treatment.
      style={{ color: 'var(--color-brand-500)' }}
      className="inline-flex size-7 shrink-0"
      dangerouslySetInnerHTML={{ __html: theGraphLogo }}
    />
  )
}

function NetworkSwitch({ environments, active, onSelect }) {
  // A binary network switch is a segmented control, not a form <select>. The
  // network changes the meaning of every number on the page, so it stays a
  // loud, persistent state marker. Rendered as links so it works without JS.
  return (
    <div role="group" aria-label="Network" className="flex rounded-4 border border-default p-0.5">
      {environments.map((env) => {
        const selected = env.id === active.id
        return (
          <a
            key={env.id}
            href={`?network=${env.id}`}
            aria-current={selected ? 'true' : undefined}
            onClick={(event) => {
              if (event.metaKey || event.ctrlKey) return
              event.preventDefault()
              onSelect(env.id)
              const url = new URL(window.location.href)
              url.searchParams.set('network', env.id)
              window.history.replaceState({}, '', url)
            }}
            className={[
              'rounded-4 px-3 py-1.5 text-14 no-underline transition-colors',
              selected ? 'bg-brand-default text-white' : 'text-muted',
            ].join(' ')}
          >
            {env.label}
            {!env.available && <span className="ml-1.5 text-12 opacity-70">· no data</span>}
          </a>
        )
      })}
    </div>
  )
}

/** Surface 1 — the indexer's question, answered before anything else. */
function SelfLookup({ env, query, onQuery, now }) {
  const match = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 3) return null
    return (
      env.indexers.find((i) => i.address.toLowerCase() === q) ??
      env.indexers.find((i) => (i.ens_name ?? '').toLowerCase() === q) ??
      env.indexers.find(
        (i) => i.address.toLowerCase().includes(q) || (i.ens_name ?? '').toLowerCase().includes(q),
      ) ??
      null
    )
  }, [env, query])

  return (
    <section aria-labelledby="lookup-heading" className="flex flex-col gap-4">
      <h1 id="lookup-heading" className="text-32 font-semibold text-default md:text-40">
        Rewards Eligibility Oracle
      </h1>
      <p className="max-w-2xl text-16 text-muted">
        Indexer eligibility for indexing rewards on The Graph Network. Look up any indexer on{' '}
        {env.label} to see where it stands.
      </p>

      <div className="max-w-2xl">
        <label htmlFor="indexer-lookup" className="mb-2 block text-14 font-medium text-default">
          Indexer address or ENS name
        </label>
        <input
          id="indexer-lookup"
          type="search"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          autoComplete="off"
          spellCheck="false"
          placeholder="0x… or yourname.eth"
          aria-describedby="lookup-hint"
          className="w-full rounded-4 border border-default bg-canvas px-4 py-3 text-16 text-default"
        />
        <p id="lookup-hint" className="mt-2 text-14 text-muted">
          Share a direct link with <code className="text-14">?indexer=0x…</code>
        </p>
      </div>

      <div aria-live="polite" className="min-h-0">
        {query.trim().length >= 3 &&
          (match ? (
            <IndexerVerdict indexer={match} env={env} now={now} />
          ) : (
            <p className="text-16 text-muted">
              No indexer on {env.label} matches “{query.trim()}”. Check the address, or switch
              network above.
            </p>
          ))}
      </div>
    </section>
  )
}

/**
 * The single-subject view. This is the high-stakes moment the critique found
 * had received the least design attention: an indexer discovering they are days
 * from losing rewards eligibility.
 */
function IndexerVerdict({ indexer, env, now }) {
  const meta = statusMeta(indexer.status)
  const detail = statusDetail(indexer, env.eligibilityPeriod, now)
  const chain = explorerChain(env.networkId)

  return (
    <Card>
      <div className="flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-3">
          <Status variant={meta.variant} size="large">
            {meta.label}
          </Status>
          {detail && <span className="text-16 text-muted">{detail}</span>}
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-20 font-semibold text-default">
            {indexer.ens_name || indexer.address}
          </span>
          {indexer.ens_name && (
            <span className="font-mono text-14 text-muted">{indexer.address}</span>
          )}
        </div>

        <p className="text-16 text-default">{meta.summary}</p>

        <div className="flex flex-wrap gap-x-8 gap-y-2 text-14 text-muted">
          <span>Last renewed: {indexer.eligibility_renewal_time_readable || 'never'}</span>
          {indexer.eligible_until_readable && (
            <span>Eligible until: {indexer.eligible_until_readable}</span>
          )}
        </div>

        <div className="flex flex-wrap gap-4 text-14">
          <a
            href={`https://thegraph.com/explorer/profile/${indexer.address}?view=Indexing&chain=${chain}`}
            className="underline underline-offset-4"
          >
            View on Explorer
          </a>
          {/* Points at the criteria already on this page, not off-site: the
              answer to "why am I in this state" is a few hundred pixels below. */}
          <a href="#criteria-heading" className="underline underline-offset-4">
            How eligibility is decided
          </a>
        </div>
      </div>
    </Card>
  )
}

const COLUMNS = [
  { key: 'indexer', label: 'Indexer' },
  { key: 'status', label: 'Status' },
  { key: 'renewed', label: 'Last renewed' },
  { key: 'until', label: 'Eligible until' },
]

/** Surface 2 — the foundation's question. */
function OracleHealth({ env, now, query, statusFilter, onStatusFilter, sort, onSort, onReset }) {
  // Hooks must run unconditionally, so both of these precede the early return.
  const counts = useMemo(() => summarize(env.indexers), [env])
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    let list = env.indexers
    if (statusFilter !== 'all') list = list.filter((i) => i.status === statusFilter)
    if (q.length >= 3) {
      list = list.filter(
        (i) => i.address.toLowerCase().includes(q) || (i.ens_name ?? '').toLowerCase().includes(q),
      )
    }
    return sortRows(list, sort)
  }, [env, query, statusFilter, sort])

  if (!env.available) return <NoNetworkData env={env} />

  return (
    <section aria-labelledby="roster-heading" className="flex flex-col gap-4">
      <h2 id="roster-heading" className="text-24 font-semibold text-default">
        All indexers on {env.label}
      </h2>
      <OracleFreshness env={env} now={now} />

      <StatusFilter counts={counts} value={statusFilter} onChange={onStatusFilter} />

      <p aria-live="polite" className="text-14 text-muted">
        Showing {rows.length} of {env.indexers.length} indexers
      </p>

      {/* Below md the six-column table would push Status — the answer people
          came for — off-screen behind a horizontal scroll, so small screens get
          a card per indexer instead. Same rows, same order; presentation only. */}
      <ul className={rows.length === 0 ? 'hidden' : 'flex flex-col gap-2 md:hidden'}>
        {rows.map((indexer) => (
          <IndexerCard key={indexer.address} indexer={indexer} env={env} now={now} />
        ))}
      </ul>

      {rows.length === 0 && <NoMatches onReset={onReset} />}

      <Card className={rows.length === 0 ? 'hidden' : 'hidden md:block'}>
        <div className="overflow-x-auto">
          <Table>
            <caption className="sr-only">
              Indexers on {env.label} and their rewards eligibility status
            </caption>
            {/* Table.Header renders its own <tr>; passing one would nest <tr>
                inside <tr>, which the HTML parser hoists — breaking hydration. */}
            <Table.Header>
              {COLUMNS.map((column) => (
                <SortableHeader key={column.key} column={column} sort={sort} onSort={onSort} />
              ))}
            </Table.Header>
            <Table.Body>
              {rows.map((indexer) => (
                <IndexerRow key={indexer.address} indexer={indexer} env={env} now={now} />
              ))}
            </Table.Body>
          </Table>
        </div>
      </Card>
    </section>
  )
}

/**
 * A real <button> inside the header cell, with aria-sort on the cell. The
 * previous dashboard's sortable headers were bare <th> elements with click
 * handlers: unreachable by keyboard and silent to screen readers.
 */
function SortableHeader({ column, sort, onSort }) {
  const isActive = sort.column === column.key
  const ariaSort = isActive ? sort.direction : 'none'

  return (
    <Table.HeaderCell scope="col" aria-sort={ariaSort}>
      <button
        type="button"
        onClick={() =>
          onSort({
            column: column.key,
            direction: isActive && sort.direction === 'ascending' ? 'descending' : 'ascending',
          })
        }
        className="inline-flex items-center gap-1 text-inherit"
      >
        {column.label}
        <span aria-hidden="true" className="text-12 opacity-60">
          {isActive ? (sort.direction === 'ascending' ? '↑' : '↓') : '↕'}
        </span>
      </button>
    </Table.HeaderCell>
  )
}

function StatusFilter({ counts, value, onChange }) {
  const options = [
    { id: 'all', label: 'All', count: counts.total },
    { id: 'eligible-grace', label: 'Grace', count: counts['eligible-grace'] },
    { id: 'ineligible-expired', label: 'Expired', count: counts['ineligible-expired'] },
    { id: 'eligible-active', label: 'Eligible', count: counts['eligible-active'] },
    { id: 'ineligible-unqualified', label: 'Unqualified', count: counts['ineligible-unqualified'] },
  ]

  return (
    <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={value === option.id}
          onClick={() => onChange(option.id)}
          className={[
            'rounded-4 border px-3 py-1.5 text-14 transition-colors',
            value === option.id
              ? 'border-brand-default bg-brand-default text-white'
              : 'border-default text-muted',
          ].join(' ')}
        >
          {option.label} <span className="opacity-70">{option.count}</span>
        </button>
      ))}
    </div>
  )
}

function IndexerRow({ indexer, env, now }) {
  const meta = statusMeta(indexer.status)
  const detail = statusDetail(indexer, env.eligibilityPeriod, now)
  const chain = explorerChain(env.networkId)

  return (
    <Table.Row>
      <Table.Cell>
        <a
          href={`https://thegraph.com/explorer/profile/${indexer.address}?view=Indexing&chain=${chain}`}
          className="text-default underline decoration-transparent underline-offset-4 transition-colors hover:decoration-current focus-visible:decoration-current"
        >
          {indexer.ens_name || `${indexer.address.slice(0, 10)}…${indexer.address.slice(-4)}`}
        </a>
      </Table.Cell>
      <Table.Cell>
        {/* The badge explains itself, so no detached legend card is needed. */}
        <Status variant={meta.variant}>
          {meta.label}
          {detail ? ` · ${detail}` : ''}
        </Status>
      </Table.Cell>
      <Table.Cell>{indexer.eligibility_renewal_time_short || 'Never'}</Table.Cell>
      <Table.Cell>{indexer.eligible_until_short || 'Not set'}</Table.Cell>
    </Table.Row>
  )
}

/** Mobile presentation of a roster row: status first, then supporting detail. */
function IndexerCard({ indexer, env, now }) {
  const meta = statusMeta(indexer.status)
  const detail = statusDetail(indexer, env.eligibilityPeriod, now)
  const chain = explorerChain(env.networkId)

  return (
    <li>
      <Card>
        <a
          href={`https://thegraph.com/explorer/profile/${indexer.address}?view=Indexing&chain=${chain}`}
          className="flex flex-col gap-2 p-4 no-underline"
        >
          <Status variant={meta.variant}>
            {meta.label}
            {detail ? ` · ${detail}` : ''}
          </Status>
          <span className="truncate text-16 font-semibold text-default">
            {indexer.ens_name || `${indexer.address.slice(0, 10)}…${indexer.address.slice(-4)}`}
          </span>
          {/* The status line already says "never renewed", so only show a date
              when there is one. */}
          {indexer.eligibility_renewal_time_short && (
            <span className="text-14 text-muted">
              Last renewed {indexer.eligibility_renewal_time_short}
            </span>
          )}
        </a>
      </Card>
    </li>
  )
}

/**
 * When the oracle last posted, and whether that is longer ago than the
 * eligibility period. Without this the page cannot report on the health of the
 * thing it exists to monitor: a stalled oracle looks identical to a healthy one.
 */
function OracleFreshness({ env, now }) {
  if (!env.oracleUpdatedAt) return null

  const lastRun = new Date(env.oracleUpdatedAt * 1000)
  const daysAgo = Math.floor((now - env.oracleUpdatedAt * 1000) / 86_400_000)
  const stale = env.eligibilityPeriod > 0 && now - env.oracleUpdatedAt * 1000 > env.eligibilityPeriod * 1000
  const when = lastRun.toISOString().slice(0, 10)

  if (!stale) {
    return (
      <p className="text-14 text-muted">
        Oracle last ran {when} ({daysAgo === 0 ? 'today' : `${daysAgo} days ago`}).
      </p>
    )
  }

  return (
    <Card>
      <div className="flex flex-col gap-1 p-4">
        <span className="text-14 font-semibold text-default">
          The oracle has not run for {daysAgo} days
        </span>
        <span className="text-14 text-muted">
          It last posted an update on {when}, longer ago than the{' '}
          {Math.round(env.eligibilityPeriod / 86400)}-day eligibility period. Statuses below are the
          last ones it recorded and may no longer reflect current service quality.
        </span>
      </div>
    </Card>
  )
}

function NoMatches({ onReset }) {
  return (
    <div className="flex flex-col items-start gap-3 p-6">
      <p className="text-16 text-default">No indexers match the current filter and search.</p>
      <button
        type="button"
        onClick={onReset}
        className="rounded-4 border border-default px-3 py-1.5 text-14 text-default"
      >
        Clear filter
      </button>
    </div>
  )
}

function NoNetworkData({ env }) {
  return (
    <section aria-labelledby="empty-heading">
      <Card>
        <div className="flex flex-col gap-2 p-6">
          <h2 id="empty-heading" className="text-20 font-semibold text-default">
            The oracle has not run on {env.label} yet
          </h2>
          <p className="text-16 text-muted">
            {env.indexers.length > 0
              ? `${env.indexers.length} indexers are active on this network, but the oracle has never posted an eligibility update here. No eligibility verdict exists for any of them yet — this is not a judgement about their service.`
              : 'No eligibility data is available for this network yet.'}
          </p>
        </div>
      </Card>
    </section>
  )
}

/**
 * The rules the oracle applies, placed directly under the hero so an indexer
 * meets them before the roster rather than after it.
 *
 * Deliberately compact: label, then the rule, with the qualifying-query
 * conditions inline rather than as a nested list. It is reference material a
 * reader scans, not prose they work through.
 *
 * Fetched from the oracle's own ELIGIBILITY_CRITERIA.md at generation time
 * rather than hardcoded, because the criteria change.
 */
function EligibilityCriteria({ criteria }) {
  if (!criteria?.items?.length) return null

  return (
    <section aria-labelledby="criteria-heading" className="flex flex-col gap-4">
      <h2 id="criteria-heading" className="text-24 font-semibold text-default">
        How eligibility is decided
      </h2>

      <Card>
        <dl className="flex flex-col divide-y divide-subtle">
          {criteria.items.map((item) => (
            <div key={item.detail} className="flex flex-col gap-1 px-6 py-4 sm:flex-row sm:gap-6">
              <dt className="text-14 font-semibold text-default sm:w-40 sm:shrink-0">
                {item.label || 'Requirement'}
              </dt>
              <dd className="max-w-prose text-16 text-muted">
                {item.detail}
                {item.children.length > 0 && (
                  <span className="mt-1 block text-14 text-muted">
                    {item.children.join(' · ')}
                  </span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      <p className="text-14 text-muted">
        Qualifying keeps you earning for the full qualification period (14 days by default), even
        if the criteria change afterwards.
        {criteria.is_fallback && ' Showing last-known values — the live criteria could not be read.'}
      </p>

      {/* Two different artifacts, so both are linked and their roles named: the
          ratified instrument that established the oracle, and the living
          document it delegates the criteria to. */}
      <p className="text-14 text-muted">
        Established by{' '}
        <a href={GIP_0079_URL} className="underline underline-offset-4">
          GIP-0079
        </a>
        ,{' '}
        <a href={COUNCIL_VOTE_URL} className="underline underline-offset-4">
          ratified by The Graph Council
        </a>
        . The requirements above are maintained in the oracle's{' '}
        <a href={criteria.source_url} className="underline underline-offset-4">
          eligibility criteria document
        </a>
        , which this page reads directly.
      </p>
    </section>
  )
}

function SiteFooter({ generatedAt, version, env }) {
  const base = arbiscanBase(env.networkId)
  const contract = env.contractAddress

  return (
    <footer className="border-t border-subtle">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-6 text-14 text-muted md:px-8">
        <a href={GIP_0079_URL} className="underline underline-offset-4">
          GIP-0079
        </a>
        <a href={COUNCIL_VOTE_URL} className="underline underline-offset-4">
          Council vote
        </a>
        <a href={GIP_0079_FORUM_URL} className="underline underline-offset-4">
          Discussion
        </a>
        {contract && (
          <a href={`${base}/address/${contract}`} className="underline underline-offset-4">
            Oracle contract
          </a>
        )}
        <span className="ml-auto">
          Updated {generatedAt} · refreshes every 5 minutes · {version}
        </span>
      </div>
    </footer>
  )
}

function sortRows(list, sort) {
  const direction = sort.direction === 'ascending' ? 1 : -1
  const value = (indexer) => {
    switch (sort.column) {
      case 'indexer':
        return (indexer.ens_name || indexer.address).toLowerCase()
      case 'renewed':
        return Number(indexer.eligibility_renewal_time) || 0
      case 'until':
        return Number(indexer.eligible_until) || 0
      case 'status':
      default:
        return STATUS_ORDER.indexOf(indexer.status)
    }
  }

  return [...list].sort((a, b) => {
    const av = value(a)
    const bv = value(b)
    if (av < bv) return -1 * direction
    if (av > bv) return 1 * direction
    return 0
  })
}
