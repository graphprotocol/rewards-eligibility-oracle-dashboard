import { useEffect, useMemo, useState } from 'react'
import {
  Address,
  Button,
  ButtonGroup,
  Card,
  Chip,
  CodeInline,
  DescriptionList,
  GDSProvider,
  Input,
  Link,
  SegmentedControl,
  Status,
  Table,
  ThemeSwitcher,
} from '@graphprotocol/gds-react'
import { ButtonOrLink } from '@graphprotocol/gds-react/base'
import { MagnifyingGlassIcon, TheGraphLogoIcon } from '@graphprotocol/gds-react/icons'

import {
  statusMeta,
  statusDetail,
  statusRank,
  explorerChain,
  arbiscanBase,
} from './lib/status.js'
import { summarize } from './lib/summary.js'
import { formatUTC, relativeAge, daysSince } from './lib/time.js'

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

/** Roster sort applied before the reader touches a column header. */
const DEFAULT_SORT = { column: 'status', order: 'asc' }

function explorerUrl(indexer, env) {
  const chain = explorerChain(env.networkId)
  return `https://thegraph.com/explorer/profile/${indexer.address}?view=Indexing&chain=${chain}`
}

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
 *
 * Every control on this page is a GDS component. The hand-rolled equivalents
 * that used to live here — a pill row, a segmented control built from anchors,
 * sortable headers, a styled search box — each reimplemented something the
 * design system already ships, and each did it with worse keyboard and screen
 * reader behaviour. See .claude/skills/gds for the rules this file follows.
 */
export function App({
  environments,
  activeId,
  generatedAt,
  generatedAtEpoch,
  version,
  now,
  criteria,
}) {
  const [networkId, setNetworkId] = useState(activeId)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sort, setSort] = useState(DEFAULT_SORT)

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

  function selectNetwork(id) {
    setNetworkId(id)
    const url = new URL(window.location.href)
    url.searchParams.set('network', id)
    window.history.replaceState({}, '', url)
  }

  return (
    <GDSProvider persistTheme="localStorage">
      <div className="flex min-h-screen flex-col bg-canvas text-default">
        <Button
          href="#roster-heading"
          size="small"
          className="sr-only focus:not-sr-only focus:absolute focus:inset-s-4 focus:top-4 focus:z-50"
        >
          Skip to indexer list
        </Button>
        <Masthead environments={environments} active={active} onSelect={selectNetwork} />
        <main className="mx-auto flex w-full max-w-288 flex-1 flex-col gap-12 px-4 py-12 md:px-8">
          <SelfLookup env={active} query={query} onQuery={setQuery} now={now} />
          {/* Two reference surfaces of similar weight, so they sit side by side
              on wide screens rather than pushing the roster below the fold. */}
          <div className="grid items-start gap-6 lg:grid-cols-2">
            <EligibilityCriteria criteria={criteria} />
            <OracleStatus env={active} now={now} />
          </div>
          <Roster
            env={active}
            now={now}
            query={query}
            statusFilter={statusFilter}
            onStatusFilter={setStatusFilter}
            sort={sort}
            onSort={(next) => setSort(next ?? DEFAULT_SORT)}
            onReset={() => {
              setStatusFilter('all')
              setQuery('')
            }}
          />
        </main>
        <SiteFooter
          generatedAt={generatedAt}
          generatedAtEpoch={generatedAtEpoch}
          version={version}
        />
      </div>
    </GDSProvider>
  )
}

function Masthead({ environments, active, onSelect }) {
  return (
    <header className="border-b border-subtle">
      <div className="mx-auto flex max-w-288 flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 md:px-8">
        {/* ButtonOrLink rather than <a>: semantics and router integration with
            no visual opinions, which is what a brand lockup wants. */}
        <ButtonOrLink
          href="https://thegraph.com"
          className="flex items-center gap-3 text-16 font-medium"
        >
          <TheGraphLogoIcon alt="" size={7} className="text-brand-500" />
          The Graph
        </ButtonOrLink>

        <div className="ms-auto flex items-center gap-2">
          <NetworkSwitch environments={environments} active={active} onSelect={onSelect} />
          <ThemeSwitcher />
        </div>
      </div>
    </header>
  )
}

/**
 * A binary network switch is a segmented control. The network changes the
 * meaning of every number on the page, so it stays a loud, persistent state
 * marker rather than collapsing into a dropdown.
 */
function NetworkSwitch({ environments, active, onSelect }) {
  return (
    <SegmentedControl
      aria-label="Network"
      size="small"
      value={active.id}
      onValueChange={onSelect}
    >
      {environments.map((env) => (
        <SegmentedControl.Option
          key={env.id}
          value={env.id}
          addonAfter={env.available ? undefined : <Status variant="warning" />}
          tooltip={env.available ? undefined : 'The oracle has never posted an update here'}
        >
          {env.label}
        </SegmentedControl.Option>
      ))}
    </SegmentedControl>
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
    <section aria-labelledby="lookup-heading" className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 id="lookup-heading" className="text-32 font-medium">
          Rewards Eligibility Oracle
        </h1>
        <p className="max-w-160 text-16 text-muted">
          Indexer eligibility for indexing rewards on The Graph Network. Look up any indexer on{' '}
          {env.label} to see where it stands.
        </p>
      </div>

      <Input
        type="search"
        label="Indexer address or ENS name"
        description={
          <>
            Share a direct link with <CodeInline>?indexer=0x…</CodeInline>
          </>
        }
        placeholder="0x… or yourname.eth"
        value={query}
        onValueChange={onQuery}
        addon={MagnifyingGlassIcon}
        autoComplete="off"
        spellCheck="false"
        className="max-w-160"
      />

      <div aria-live="polite">
        {query.trim().length >= 3 &&
          (match ? (
            <IndexerVerdict indexer={match} env={env} now={now} />
          ) : (
            <p className="text-14 text-muted">
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
  const href = explorerUrl(indexer, env)

  // Card pads itself (24px). Anything that adds `p-6` in here is doubling it.
  return (
    <Card className="max-w-160">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Status variant={meta.variant} size="large">
            {meta.label}
          </Status>
          {detail && <span className="text-14 text-muted">{detail}</span>}
        </div>

        <div className="flex flex-col gap-1">
          {indexer.ens_name && <span className="text-20 font-medium">{indexer.ens_name}</span>}
          <Address address={indexer.address} href={href} />
        </div>

        <p className="text-14">{meta.summary}</p>

        <DescriptionList size="small">
          <DescriptionList.Item label="Last renewed">
            {indexer.eligibility_renewal_time_readable || 'Never'}
          </DescriptionList.Item>
          <DescriptionList.Item label="Eligible until">
            {indexer.eligible_until_readable || 'Not set'}
          </DescriptionList.Item>
        </DescriptionList>

        <ButtonGroup size="small">
          <Button href={href}>View on Explorer</Button>
          {/* Points at the criteria already on this page, not off-site: the
              answer to "why am I in this state" is a few hundred pixels below. */}
          <Button variant="tertiary" href="#criteria-heading">
            How eligibility is decided
          </Button>
        </ButtonGroup>
      </div>
    </Card>
  )
}

/** Surface 2 — the foundation's question. */
function Roster({ env, now, query, statusFilter, onStatusFilter, sort, onSort, onReset }) {
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
    return list
  }, [env, query, statusFilter])

  if (!env.available) return <NoNetworkData env={env} />

  return (
    <section aria-labelledby="roster-heading" className="flex flex-col gap-4">
      <h2 id="roster-heading" className="text-20 font-medium">
        All indexers on {env.label}
      </h2>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <StatusFilter counts={counts} value={statusFilter} onChange={onStatusFilter} />
        <p aria-live="polite" className="text-14 text-muted">
          Showing {rows.length} of {env.indexers.length} indexers
        </p>
      </div>

      {rows.length === 0 ? (
        <NoMatches onReset={onReset} />
      ) : (
        /*
         * Sorting is the Table's, not ours: `sortable` on a header cell renders
         * the button, the aria-sort and the caret, and Table.Body applies the
         * comparator. On small screens the Table scrolls horizontally on its
         * own — it does not need a second, duplicate card rendering of every
         * row, which is what used to double the size of this page.
         */
        <Table sort={sort} onSortChange={onSort}>
          <Table.Header>
            {/* `fr` absorbs the slack on desktop; its `auto` minimum keeps the
                name legible on a phone, where the table scrolls rather than
                squeezing the one column people scan by. */}
            <Table.HeaderCell name="indexer" width="fr" sortable={{ comparator: byName }}>
              Indexer
            </Table.HeaderCell>
            <Table.HeaderCell name="status" sortable={{ comparator: byStatus }}>
              Status
            </Table.HeaderCell>
            <Table.HeaderCell
              name="renewed"
              align="end"
              sortable={{ comparator: byRenewed, defaultOrder: 'desc' }}
            >
              Last renewed
            </Table.HeaderCell>
            <Table.HeaderCell
              name="until"
              align="end"
              sortable={{ comparator: byUntil, defaultOrder: 'desc' }}
            >
              Eligible until
            </Table.HeaderCell>
          </Table.Header>
          <Table.Body rows={rows} getRowKey={(indexer) => indexer.address}>
            {(indexer) => <IndexerRow indexer={indexer} env={env} now={now} />}
          </Table.Body>
        </Table>
      )}
    </section>
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
    <Chip.Group
      type="radio"
      aria-label="Filter by status"
      value={value}
      onValueChange={onChange}
    >
      {options.map((option) => (
        <Chip
          key={option.id}
          value={option.id}
          // Stringified: Chip drops a falsy count, and a Grace filter showing
          // no number reads as "unknown" rather than "nobody is in grace".
          count={String(option.count)}
          addonBefore={
            option.id === 'all' ? undefined : <Status variant={statusMeta(option.id).variant} />
          }
        >
          {option.label}
        </Chip>
      ))}
    </Chip.Group>
  )
}

function IndexerRow({ indexer, env, now }) {
  const meta = statusMeta(indexer.status)
  const detail = statusDetail(indexer, env.eligibilityPeriod, now)

  return (
    <Table.Row>
      <Table.Cell>
        {/* Address handles truncation, the identicon and the friendly name.
            `copy={false}` because the row already links to the Explorer and a
            copy button inside a link is a nested interactive element. */}
        <Address address={indexer.address} href={explorerUrl(indexer, env)} copy={false}>
          {indexer.ens_name || undefined}
        </Address>
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

/**
 * When the oracle last posted, and whether that is longer ago than the
 * eligibility period. Without this the page cannot report on the health of the
 * thing it exists to monitor: a stalled oracle looks identical to a healthy one.
 */
function OracleStatus({ env, now }) {
  const oracleRan = env.oracleUpdatedAt
  const dataRead = env.indexersRetrievedAt
  const period = env.eligibilityPeriod

  // Two different clocks, and conflating them hides real failures: the indexer
  // list can be two minutes old while the oracle itself has not run for days.
  const stale = oracleRan > 0 && period > 0 && now - oracleRan * 1000 > period * 1000

  return (
    <section aria-labelledby="oracle-heading" className="flex flex-col gap-4">
      <h2 id="oracle-heading" className="text-20 font-medium">
        Oracle status
      </h2>

      {stale && (
        <Card>
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Status variant="warning" size="large">
                Stalled
              </Status>
              <span className="text-14 font-medium">
                No update for {daysSince(oracleRan, now)} days
              </span>
            </div>
            <p className="text-14 text-muted">
              The last update is older than the {Math.round(period / 86400)}-day eligibility
              period. Statuses below are the last ones the oracle recorded and may no longer
              reflect current service quality.
            </p>
          </div>
        </Card>
      )}

      <Card>
        <DescriptionList size="small">
          <DescriptionList.Item
            label="Oracle last ran"
            addon={oracleRan ? <Status variant={stale ? 'warning' : 'success'} /> : undefined}
          >
            {formatUTC(oracleRan) ?? 'Never'}
          </DescriptionList.Item>
          {oracleRan > 0 && (
            <DescriptionList.Item label="That was">
              {relativeAge(oracleRan, now)}
            </DescriptionList.Item>
          )}
          <DescriptionList.Item label="Indexer data refreshed">
            {dataRead ? `${formatUTC(dataRead)} (${relativeAge(dataRead, now)})` : 'Unknown'}
          </DescriptionList.Item>
          <DescriptionList.Item label="Eligibility period">
            {period > 0 ? `${Math.round(period / 86400)} days` : 'Unknown'}
          </DescriptionList.Item>
          {env.contractAddress && (
            <DescriptionList.Item label="Oracle contract">
              <Address
                address={env.contractAddress}
                href={`${arbiscanBase(env.networkId)}/address/${env.contractAddress}`}
              />
            </DescriptionList.Item>
          )}
        </DescriptionList>
      </Card>
    </section>
  )
}

function NoMatches({ onReset }) {
  return (
    <div className="flex flex-col items-start gap-4 py-12">
      <p className="text-14 text-muted">No indexers match the current filter and search.</p>
      <Button size="small" onClick={onReset}>
        Clear filter
      </Button>
    </div>
  )
}

function NoNetworkData({ env }) {
  return (
    <section aria-labelledby="roster-heading">
      <Card>
        <div className="flex flex-col gap-2">
          <h2 id="roster-heading" className="text-20 font-medium">
            The oracle has not run on {env.label} yet
          </h2>
          <p className="text-14 text-muted">
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
 * The rules the oracle applies, placed alongside the oracle's own status so an
 * indexer meets them before the roster rather than after it.
 *
 * A DescriptionList would be the obvious choice, but its values are
 * single-line and horizontally scrolling by design — these are sentences, so
 * this stays a plain semantic <dl> with GDS tokens.
 *
 * Fetched from the oracle's own ELIGIBILITY_CRITERIA.md at generation time
 * rather than hardcoded, because the criteria change.
 */
function EligibilityCriteria({ criteria }) {
  if (!criteria?.items?.length) return null

  return (
    <section aria-labelledby="criteria-heading" className="flex flex-col gap-4">
      <h2 id="criteria-heading" className="text-20 font-medium">
        How eligibility is decided
      </h2>

      <Card>
        <dl className="flex flex-col *:not-first:border-t *:not-first:border-subtle">
          {criteria.items.map((item) => (
            <div key={item.detail} className="flex flex-col gap-1 py-4 first:pt-0 last:pb-0">
              <dt className="text-14 font-medium">{item.label || 'Requirement'}</dt>
              <dd className="text-14 text-muted">
                {item.detail}
                {item.children.length > 0 && (
                  <span className="mt-1 block text-12">{item.children.join(' · ')}</span>
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
        Established by <Link href={GIP_0079_URL}>GIP-0079</Link>,{' '}
        <Link href={COUNCIL_VOTE_URL}>ratified by The Graph Council</Link>. The requirements above
        are maintained in the oracle's{' '}
        <Link href={criteria.source_url}>eligibility criteria document</Link>, which this page
        reads directly.
      </p>
    </section>
  )
}

function SiteFooter({ generatedAt, generatedAtEpoch, version }) {
  return (
    <footer className="border-t border-subtle">
      <div className="mx-auto flex max-w-288 flex-wrap items-center gap-x-6 gap-y-2 px-4 py-6 text-14 text-muted md:px-8">
        <Link variant="secondary" href={GIP_0079_URL}>
          GIP-0079
        </Link>
        <Link variant="secondary" href={COUNCIL_VOTE_URL}>
          Council vote
        </Link>
        <Link variant="secondary" href={GIP_0079_FORUM_URL}>
          Discussion
        </Link>
        <span className="ms-auto">
          Page generated {formatUTC(generatedAtEpoch) ?? generatedAt} · refreshes every 5 minutes ·{' '}
          {version}
        </span>
      </div>
    </footer>
  )
}

/*
 * Comparators handed to Table.HeaderCell. The Table owns the sort state and the
 * ordering; these only say what "greater" means for a column.
 */
function byName(a, b) {
  return (a.ens_name || a.address).toLowerCase().localeCompare((b.ens_name || b.address).toLowerCase())
}

function byStatus(a, b) {
  return statusRank(a.status) - statusRank(b.status)
}

function byRenewed(a, b) {
  return (Number(a.eligibility_renewal_time) || 0) - (Number(b.eligibility_renewal_time) || 0)
}

function byUntil(a, b) {
  return (Number(a.eligible_until) || 0) - (Number(b.eligible_until) || 0)
}
