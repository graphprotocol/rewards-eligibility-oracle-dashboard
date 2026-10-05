/**
 * The visual vocabulary for daily metrics, shared by the roster and the
 * indexer page. The unit everything is built from is the day cell.
 */
import { Status, Tooltip } from '@graphprotocol/gds-react'
import { ButtonOrLink } from '@graphprotocol/gds-react/base'

import { longDay, shortDay } from '../lib/metrics.js'

export const DAY_STATE = {
  qualified: { label: 'Online day', variant: 'success' },
  failed: { label: 'Did not qualify', variant: 'error' },
  'not-routed': { label: 'Not routed', variant: 'default' },
  unpublished: { label: 'No data published', variant: 'default' },
}

/**
 * State lives in `data-state`, never in a computed className. Online and failed
 * are told apart by the status colours; not-routed and unpublished by fill
 * versus dashed outline, so neither depends on colour alone.
 *
 * Applied to the *container* and reaching its children, because a strip is 29
 * cells and the roster renders dozens of strips: per-cell classes made up most
 * of the page's weight.
 */
export const CELLS = `
  *:rounded-2
  *:data-[state=qualified]:bg-status-success-default
  *:data-[state=failed]:bg-status-error-default
  *:data-[state=not-routed]:bg-elevated
  *:data-[state=unpublished]:border *:data-[state=unpublished]:border-dashed *:data-[state=unpublished]:border-default
`

export function dayLabel(d) {
  if (d.state === 'unpublished') return `${longDay(d.day)} · no data published`
  const head = `${longDay(d.day)}${d.isFinal ? '' : ' (partial)'}`
  if (d.state === 'qualified') return `${head} · online · ${d.qualifyingSubgraphs} subgraphs`
  return `${head} · ${d.reason.label}`
}

/** The window at a glance, for a table cell. Decorative: the row says the rest. */
export function MiniStrip({ days }) {
  return (
    <div aria-hidden className={`flex h-4 gap-0.5 *:w-1 ${CELLS}`}>
      {days.map((d) => (
        <span key={d.day} data-state={d.state} />
      ))}
    </div>
  )
}

/** Online days against the requirement, with a tick where the minimum sits. */
export function OnlineMeter({ a, windowDays, minOnlineDays, pending }) {
  const pct = (n) => `${(n / windowDays) * 100}%`
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline gap-1 text-14">
        <span className="font-medium">{a.online}</span>
        <span className="text-muted">/ {windowDays}</span>
        {a.affected && (
          <span className="text-12 text-status-error-strong">
            → {a.onlinePending} from {shortDay(pending.effectiveDay)}
          </span>
        )}
      </div>
      <div className="h-1.5 w-24 rounded-full bg-elevated">
        <div
          data-short={a.online < minOnlineDays || undefined}
          className="h-full rounded-full bg-status-success-default data-short:bg-status-error-default"
          style={{ width: pct(a.online) }}
        />
        <span
          className="absolute -top-0.5 h-2.5 w-0.5 rounded-full bg-strong"
          style={{ insetInlineStart: pct(minOnlineDays) }}
        />
      </div>
    </div>
  )
}

export function StripLegend({ minOnlineDays }) {
  return (
    <ul className="flex flex-wrap gap-x-6 gap-y-2 text-12 text-muted">
      {Object.entries(DAY_STATE).map(([state, meta]) => (
        <li key={state} className={`flex items-center gap-2 *:first:size-3 ${CELLS}`}>
          <span data-state={state} />
          <span>{meta.label}</span>
        </li>
      ))}
      {minOnlineDays != null && (
        <li className="flex items-center gap-2">
          <span className="h-3 w-0.5 rounded-full bg-strong" />
          {minOnlineDays} online days required
        </li>
      )}
    </ul>
  )
}

/** The window as selectable day cells, oldest on the left. */
export function DayStrip({ days, leavingThisWeek, selected, onSelect }) {
  const columns = { gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }
  return (
    <div className="flex flex-col gap-2">
      <div className="grid gap-0.5 text-10 text-muted sm:gap-1" style={columns}>
        {leavingThisWeek > 0 && (
          <div className="col-span-7 flex flex-col gap-1">
            <span className="truncate">Leaving the window this week</span>
            <span className="h-1 rounded-full border-x border-t border-default" />
          </div>
        )}
      </div>
      <div
        className={`grid gap-0.5 sm:gap-1 *:h-10 *:outline-offset-2 *:hover:outline-2 *:hover:outline-brand-300 *:data-selected:outline-2 *:data-selected:outline-brand-500 ${CELLS}`}
        style={columns}
      >
        {days.map((d) => (
          <Tooltip key={d.day} content={dayLabel(d)}>
            <ButtonOrLink
              aria-label={dayLabel(d)}
              aria-pressed={d.day === selected}
              data-state={d.state}
              data-selected={d.day === selected || undefined}
              onClick={() => onSelect(d.day)}
            />
          </Tooltip>
        ))}
      </div>
      <div className="flex justify-between text-12 text-muted">
        <span>{shortDay(days[0].day)}</span>
        <span>
          {shortDay(days.at(-1).day)}
          {days.at(-1).isFinal ? '' : ' (partial until the next run)'}
        </span>
      </div>
    </div>
  )
}

/**
 * A page-level notice. GDS has no banner component, so this follows the
 * OracleFreshness treatment: tokens on a plain element, tone via data-tone.
 * The amber fill is the one raw colour scale, for the reason given there.
 */
export function Notice({ tone = 'default', title, children, action }) {
  return (
    <div
      data-tone={tone}
      className="
        flex flex-wrap items-center gap-4 rounded-8 border border-muted bg-subtle p-4
        data-[tone=warning]:border-status-warning-muted data-[tone=warning]:bg-solar-1000
        light:data-[tone=warning]:bg-solar-100
        data-[tone=info]:border-status-info-muted
      "
    >
      <div className="flex flex-1 basis-80 flex-col gap-1">
        <div className="flex items-center gap-2">
          <Status variant={tone} />
          <span className="text-14 font-medium">{title}</span>
        </div>
        <div className="text-14 text-muted">{children}</div>
      </div>
      {action}
    </div>
  )
}
