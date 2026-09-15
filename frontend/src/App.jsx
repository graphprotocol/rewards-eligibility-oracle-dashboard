import { useEffect, useMemo, useState } from 'react'
import {
  Address,
  Button,
  ButtonGroup,
  Card,
  Chip,
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
import {
  ArrowRightInteractiveIcon,
  ArrowSquareOutIcon,
  CheckCircleIcon,
  ClipboardTextIcon,
  ClockIcon,
  GaugeIcon,
  ListChecksIcon,
  MagnifyingGlassIcon,
  TheGraphLogoIcon,
} from '@graphprotocol/gds-react/icons'

import { statusMeta, statusDetail, statusRank, explorerChain, arbiscanBase } from './lib/status.js'
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

/**
 * The roster opens on the indexers currently earning rewards. `?status=` still
 * overrides it, and "All" is one click away.
 */
const DEFAULT_STATUS_FILTER = 'eligible-active'

/**
 * Rows rendered before the roster asks to be expanded.
 *
 * The reference material below the table — the criteria, the oracle's own
 * numbers — is unreachable if ninety-odd rows sit on top of it. This is also
 * why the page ships a fraction of the markup it used to.
 */
const VISIBLE_ROWS = 25

function explorerUrl(indexer, env) {
  return `https://thegraph.com/explorer/profile/${indexer.address}?view=Indexing&chain=${explorerChain(env.networkId)}`
}

/**
 * The page answers three questions, in the order someone actually asks them:
 *
 *   1. "Can I trust what this page says right now?" — the oracle freshness
 *      banner, beside the title, because a stalled oracle invalidates every
 *      verdict underneath it.
 *   2. "Where do I stand?"                          — the lookup and its verdict.
 *   3. "Where does everyone stand, and why?"        — the roster, then the rules
 *      and the oracle's own numbers as reference material.
 *
 * The same component tree renders on the server and hydrates on the client, so
 * there is one implementation of the UI rather than a static version plus a
 * separate pile of DOM-poking JavaScript.
 *
 * Every control here is a GDS component. See .claude/skills/gds for the rules
 * this file follows.
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
  const [statusFilter, setStatusFilter] = useState(DEFAULT_STATUS_FILTER)
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

        <main className="mx-auto flex w-full max-w-288 flex-1 flex-col gap-8 px-4 py-10 md:px-8">
          <div className="grid items-center gap-6 lg:grid-cols-2">
            <div className="flex flex-col gap-2">
              <h1 className="text-32 font-medium">Rewards Eligibility Oracle</h1>
              <p className="text-14 text-muted">
                Indexer eligibility for indexing rewards on The Graph Network. Look up any indexer
                on {active.label} to see where it stands.
              </p>
            </div>
            <OracleFreshness env={active} now={now} />
          </div>

          <IndexerLookup env={active} query={query} onQuery={setQuery} now={now} />

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

          {/* Reference material, below the thing it explains. Two thirds to the
              criteria: it carries two columns of prose, while Oracle details
              is five short label/value rows and was running half empty.

              No `items-start`: the grid's default stretch, plus `h-full` on
              each Card, squares the two panels off against each other. Which
              one is taller depends on the criteria document, so this has to
              work in either direction rather than pinning a height. */}
          <div className="grid gap-6 lg:grid-cols-3">
            <EligibilityCriteria
              criteria={criteria}
              eligibilityPeriod={active.eligibilityPeriod}
              className="lg:col-span-2"
            />
            <OracleDetails env={active} now={now} />
          </div>
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
    <SegmentedControl aria-label="Network" size="small" value={active.id} onValueChange={onSelect}>
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

/**
 * Whether the page can be trusted, stated beside the title rather than buried.
 *
 * A stalled oracle and a healthy one used to look identical, and the difference
 * governs every verdict below: if the oracle has not run in longer than the
 * eligibility period, the statuses on this page are history, not fact.
 *
 * GDS has no banner component, so this is a plain element built from tokens.
 * The `data-stale` attribute drives the colour rather than a computed
 * className.
 *
 * The amber fill is one of the few justified uses of a raw colour scale: the
 * semantic `status-warning-*` tokens are dot-and-border strengths (solar-300 in
 * light mode) and fill a panel far too loudly, and GDS ships no subtle status
 * *surface*. Both themes are therefore stated explicitly.
 */
function OracleFreshness({ env, now }) {
  const oracleRan = env.oracleUpdatedAt
  const period = env.eligibilityPeriod
  const stale = oracleRan > 0 && period > 0 && now - oracleRan * 1000 > period * 1000
  const days = daysSince(oracleRan, now)

  return (
    <div
      data-stale={stale || undefined}
      className="
        flex flex-wrap items-center gap-4 rounded-8 border border-muted bg-subtle p-4
        data-stale:border-status-warning-muted data-stale:bg-solar-1000
        light:data-stale:bg-solar-100
      "
    >
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex items-center gap-2">
          <Status variant={stale ? 'warning' : oracleRan ? 'success' : 'default'} />
          <span className="text-14 font-medium">
            {stale
              ? 'Oracle data is stale'
              : oracleRan
                ? 'Oracle data is current'
                : 'The oracle has not run here yet'}
          </span>
        </div>
        <p className="text-14 text-muted">
          {stale
            ? `Last updated ${days} days ago. Statuses may not reflect current service quality.`
            : oracleRan
              ? `Last updated ${relativeAge(oracleRan, now)}.`
              : 'No eligibility verdict exists for this network.'}
        </p>
      </div>
      <Button size="small" href="#oracle-heading" addonAfter={ArrowRightInteractiveIcon}>
        View details
      </Button>
    </div>
  )
}

/** Surface 1 — the indexer's own question, answered before the roster. */
function IndexerLookup({ env, query, onQuery, now }) {
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
    <section aria-label="Indexer lookup" className="flex flex-col gap-4">
      <Input
        size="large"
        type="search"
        label="Search for an indexer"
        placeholder="Indexer address or ENS name (e.g. squid, 0x1234…)"
        addon={MagnifyingGlassIcon}
        value={query}
        onValueChange={onQuery}
        autoComplete="off"
        spellCheck="false"
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
 * The single-subject view: the high-stakes moment where an indexer discovers
 * they are days from losing rewards eligibility. The verdict and what to do
 * about it on the left, the dates it was derived from on the right.
 */
function IndexerVerdict({ indexer, env, now }) {
  const meta = statusMeta(indexer.status)
  const detail = statusDetail(indexer, env.eligibilityPeriod, now)
  const href = explorerUrl(indexer, env)

  // Card pads itself (24px). Anything that adds `p-6` in here is doubling it.
  return (
    <Card>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="flex flex-col items-start gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <Status variant={meta.variant} size="large">
              {meta.label}
            </Status>
            {detail && <span className="text-14 text-muted">{detail}</span>}
          </div>

          <div className="flex flex-col gap-1">
            {indexer.ens_name && <span className="text-20 font-medium">{indexer.ens_name}</span>}
            {/* Copy only — "View on Explorer" below is the link, and an Address
                that is both silently overlays one on the other. `copy` is left
                at its default: it is the only mode in which Address exposes its
                own text to a screen reader. */}
            <Address address={indexer.address} />
          </div>

          <p className="text-14">{meta.summary}</p>

          <ButtonGroup size="small" className="mt-auto">
            <Button href={href} addonAfter={ArrowSquareOutIcon}>
              View on Explorer
            </Button>
            {/* Points at the criteria already on this page, not off-site: the
                answer to "why am I in this state" is further down. */}
            <Button href="#criteria-heading" addonBefore={ListChecksIcon}>
              How eligibility is decided
            </Button>
          </ButtonGroup>
        </div>

        <DescriptionList size="small">
          <DescriptionList.Item label="Last renewed">
            {indexer.eligibility_renewal_time_readable || 'Never'}
          </DescriptionList.Item>
          <DescriptionList.Item label="Eligible until">
            {indexer.eligible_until_readable || 'Not set'}
          </DescriptionList.Item>
        </DescriptionList>
      </div>
    </Card>
  )
}

/*
 * Column comparators. The Table owns the sort state and renders the sort UI;
 * these only say what "greater" means per column.
 *
 * They are also applied here, before the roster is truncated — otherwise
 * "the first 25 rows" would mean "25 arbitrary rows, then sorted", which is a
 * different and much less useful table.
 */
const COMPARATORS = {
  indexer: (a, b) =>
    (a.ens_name || a.address).toLowerCase().localeCompare((b.ens_name || b.address).toLowerCase()),
  status: (a, b) => statusRank(a.status) - statusRank(b.status),
  renewed: (a, b) =>
    (Number(a.eligibility_renewal_time) || 0) - (Number(b.eligibility_renewal_time) || 0),
  until: (a, b) => (Number(a.eligible_until) || 0) - (Number(b.eligible_until) || 0),
}

/** Surface 2 — where everyone stands. */
function Roster({ env, now, query, statusFilter, onStatusFilter, sort, onSort, onReset }) {
  const [showAll, setShowAll] = useState(false)

  // Hooks must run unconditionally, so these precede the early return.
  const counts = useMemo(() => summarize(env.indexers), [env])
  const ordered = useMemo(() => {
    const q = query.trim().toLowerCase()
    let list = env.indexers
    if (statusFilter !== 'all') list = list.filter((i) => i.status === statusFilter)
    if (q.length >= 3) {
      list = list.filter(
        (i) => i.address.toLowerCase().includes(q) || (i.ens_name ?? '').toLowerCase().includes(q),
      )
    }
    const compare = COMPARATORS[sort.column] ?? COMPARATORS.status
    const direction = sort.order === 'asc' ? 1 : -1
    return [...list].sort((a, b) => direction * compare(a, b))
  }, [env, query, statusFilter, sort])

  if (!env.available) return <NoNetworkData env={env} />

  const rows = showAll ? ordered : ordered.slice(0, VISIBLE_ROWS)
  const hidden = ordered.length - rows.length

  return (
    <section aria-labelledby="roster-heading" className="flex flex-col gap-4">
      <h2 id="roster-heading" className="text-20 font-medium">
        All indexers on {env.label}
      </h2>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <StatusFilter counts={counts} value={statusFilter} onChange={onStatusFilter} />
        {/* Both numbers move: the first is what is on screen, the second is
            what the filter matched. Saying "of 97" while a filter is active
            would describe a roster the reader is not looking at. */}
        <p id="roster-count" aria-live="polite" className="text-14 text-muted">
          Showing {rows.length} of {ordered.length} indexers
        </p>
      </div>

      {ordered.length === 0 ? (
        <NoMatches onReset={onReset} />
      ) : (
        <>
          {/*
           * Sorting is the Table's: `sortable` on a header cell renders the
           * button, the aria-sort and the caret. On small screens the Table
           * scrolls horizontally on its own — it does not need a second,
           * duplicate card rendering of every row.
           */}
          <Table sort={sort} onSortChange={onSort}>
            <Table.Header>
              {/* `fr` absorbs the slack on desktop; its `auto` minimum keeps
                  the name legible on a phone, where the table scrolls rather
                  than squeezing the one column people scan by. */}
              <Table.HeaderCell name="indexer" width="fr" sortable={{ comparator: COMPARATORS.indexer }}>
                Indexer
              </Table.HeaderCell>
              <Table.HeaderCell name="status" sortable={{ comparator: COMPARATORS.status }}>
                Status
              </Table.HeaderCell>
              <Table.HeaderCell
                name="renewed"
                align="end"
                sortable={{ comparator: COMPARATORS.renewed, defaultOrder: 'desc' }}
              >
                Last renewed
              </Table.HeaderCell>
              <Table.HeaderCell
                name="until"
                align="end"
                sortable={{ comparator: COMPARATORS.until, defaultOrder: 'desc' }}
              >
                Eligible until
              </Table.HeaderCell>
            </Table.Header>
            <Table.Body rows={rows} getRowKey={(indexer) => indexer.address}>
              {(indexer) => <IndexerRow indexer={indexer} env={env} now={now} />}
            </Table.Body>
          </Table>

          {hidden > 0 && (
            // The rare sanctioned case for a Link without an href: an action
            // that reads as navigation into the rest of the list.
            <Link
              href={undefined}
              onClick={() => setShowAll(true)}
              addonAfter={ArrowRightInteractiveIcon}
              className="self-start text-14"
            >
              View all {ordered.length} indexers
            </Link>
          )}
        </>
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
    <Chip.Group type="radio" aria-label="Filter by status" value={value} onValueChange={onChange}>
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
            copy button inside a link is a nested interactive element.

            The explicit `aria-label` is not redundant: Address marks its own
            text `aria-hidden` and display:nones the duplicate unless
            `copy="auto"`, so without this every row is an unnamed link and the
            one column that identifies the row is invisible to a screen reader. */}
        <Address
          address={indexer.address}
          href={explorerUrl(indexer, env)}
          copy={false}
          aria-label={`${indexer.ens_name || indexer.address} — view on Explorer`}
        >
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
 * Criteria labels come from the oracle's own ELIGIBILITY_CRITERIA.md and change
 * without warning, so the icon is chosen from the label's meaning rather than
 * its position. An unrecognised requirement still gets a sensible mark instead
 * of a wrong one.
 */
function criteriaIcon(label = '') {
  const text = label.toLowerCase()
  if (/qualit|latenc|freshness|status/.test(text)) return GaugeIcon
  if (/quer/.test(text)) return ClipboardTextIcon
  if (/online|uptime|day|time|period/.test(text)) return ClockIcon
  return CheckCircleIcon
}

/**
 * Splits the requirements into the panel's two columns.
 *
 * A requirement that carries sub-conditions is several times taller than a
 * one-sentence one, so giving every requirement an equal column left most of
 * them empty. The detailed ones get a column to themselves and the brief ones
 * stack beside them, which is both better balanced and wider per column.
 *
 * Falls back to even halves if the criteria document ever stops having one of
 * each kind — the split is a layout heuristic, not a promise about the data.
 */
function splitCriteria(items) {
  const brief = items.filter((item) => item.children.length === 0)
  const detailed = items.filter((item) => item.children.length > 0)
  if (brief.length > 0 && detailed.length > 0) return [brief, detailed]

  const half = Math.ceil(items.length / 2)
  return [items.slice(0, half), items.slice(half)]
}

/** One requirement: mark, name, rule, and any sub-conditions. */
function Criterion({ item }) {
  const RequirementIcon = criteriaIcon(item.label)

  return (
    <div className="flex flex-col gap-2">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-10 bg-brand-subtlest">
        <RequirementIcon alt="" size={5} className="text-brand-500" />
      </span>
      <dt className="text-14 font-medium">{item.label || 'Requirement'}</dt>
      <dd className="flex flex-col gap-2 text-14 text-muted">
        <span>{item.detail}</span>
        {item.children.length > 0 && (
          // A list of conditions is a list, not a run-on sentence.
          <ul className="flex flex-col gap-1">
            {item.children.map((condition) => (
              <li key={condition} className="flex items-start gap-2">
                {/* h-lh aligns the mark with the first line when it wraps. */}
                <CheckCircleIcon alt="" variant="fill" className="h-lh text-brand-500" />
                <span>{condition}</span>
              </li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  )
}

/**
 * The rules the oracle applies.
 *
 * A DescriptionList would be the obvious choice, but its values are single-line
 * and horizontally scrolling by design — these are sentences, so these stay
 * plain semantic <dl>s with GDS tokens.
 */
function EligibilityCriteria({ criteria, eligibilityPeriod, className }) {
  if (!criteria?.items?.length) return null

  const periodDays = eligibilityPeriod > 0 ? Math.round(eligibilityPeriod / 86400) : null

  return (
    <section aria-labelledby="criteria-heading" className={className}>
      <Card className="h-full">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <h2 id="criteria-heading" className="text-18 font-medium">
              How eligibility is decided
            </h2>
            <p className="text-14 text-muted">
              Qualifying keeps you earning for the full qualification period
              {periodDays ? ` (${periodDays} days by default)` : ''}, even if the criteria change
              afterwards.{' '}
              {/* Points at the living document the oracle actually reads.
                  GIP-0079 is named because it is the instrument that
                  established these rules, and is linked on its own in the
                  footer. Link inherits the surrounding type. */}
              <Link href={criteria.source_url}>Read the full criteria (GIP-0079)</Link>
            </p>
          </div>

          {/*
           * Two columns, not three. The border is start-edge on the second
           * column only, and only once they are actually side by side —
           * stacked on a phone it would be a stray vertical line.
           */}
          <div className="grid gap-x-5 gap-y-6 sm:grid-cols-2 sm:*:not-first:border-s sm:*:not-first:border-muted sm:*:not-first:ps-5">
            {splitCriteria(criteria.items).map((column, index) => (
              <dl key={index} className="flex flex-col gap-6">
                {column.map((item) => (
                  <Criterion key={item.detail} item={item} />
                ))}
              </dl>
            ))}
          </div>

          {criteria.is_fallback && (
            <p className="text-14 text-muted">
              Showing last-known values — the live criteria could not be read.
            </p>
          )}

        </div>
      </Card>
    </section>
  )
}

/** The oracle's own numbers — the target of "View details" in the banner. */
function OracleDetails({ env, now, className }) {
  const oracleRan = env.oracleUpdatedAt
  const dataRead = env.indexersRetrievedAt
  const period = env.eligibilityPeriod

  const stale = oracleRan > 0 && period > 0 && now - oracleRan * 1000 > period * 1000

  return (
    <section aria-labelledby="oracle-heading" className={className}>
      <Card className="h-full">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <h2 id="oracle-heading" className="text-18 font-medium">
              Oracle details
            </h2>
            {/* "above", not "below": this card sits under the roster it is
                qualifying. Only say it when it is true. */}
            <p className="text-14 text-muted">
              {stale
                ? 'Statuses above are the last ones the oracle recorded and may no longer reflect current service quality.'
                : 'When the oracle last ran, and where the numbers on this page come from.'}
            </p>
          </div>

          <DescriptionList size="small">
            <DescriptionList.Item label="Oracle last ran">
              {formatUTC(oracleRan) ?? 'Never'}
            </DescriptionList.Item>
            {oracleRan > 0 && (
              <DescriptionList.Item label="That was">
                {relativeAge(oracleRan, now)}
              </DescriptionList.Item>
            )}
            {/* Two different clocks, and conflating them hides real failures:
                the indexer list can be two minutes old while the oracle itself
                has not run for days. */}
            <DescriptionList.Item label="Indexer data refreshed">
              {dataRead ? `${formatUTC(dataRead)} (${relativeAge(dataRead, now)})` : 'Unknown'}
            </DescriptionList.Item>
            <DescriptionList.Item label="Eligibility period">
              {period > 0 ? `${Math.round(period / 86400)} days` : 'Unknown'}
            </DescriptionList.Item>
            {env.contractAddress && (
              /*
               * Two affordances, kept apart. Address's copy button floats over
               * the end of the address — put a link underneath it and the same
               * pixels do two different things depending on where you land. So
               * the Address here only copies, and Arbiscan is its own action.
               */
              <DescriptionList.Item
                label="Oracle contract"
                action={
                  <Button
                    href={`${arbiscanBase(env.networkId)}/address/${env.contractAddress}`}
                  >
                    <ArrowSquareOutIcon alt="View on Arbiscan" />
                  </Button>
                }
              >
                <Address address={env.contractAddress} />
              </DescriptionList.Item>
            )}
          </DescriptionList>
        </div>
      </Card>
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
          Page generated {formatUTC(generatedAtEpoch) ?? generatedAt} · refreshes every hour ·{' '}
          {version}
        </span>
      </div>
    </footer>
  )
}
