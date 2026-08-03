---
target: output/index.html — REO dashboard rebuild (re-score)
total_score: 25
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
timestamp: 2026-07-31T18-27-39Z
slug: output-index-html
---
Method: dual-agent (A: rescore-A · B: rescore-B) — same method as the 14/40 baseline, so the comparison is like-for-like.

Re-score of the rebuilt dashboard (React + The Graph Design System, prerendered and hydrated) against the baseline critique of the old hand-written build.

## Design Health Score

| # | Heuristic | Base → New | Key Issue |
|---|-----------|-----------|-----------|
| 1 | Visibility of System Status | 2 → 3 | Cadence, aria-live row count and per-row countdown all landed; oracle's own last-run time was dropped (fixed after scoring) |
| 2 | Match System / Real World | 2 → 3 | Enums gone from the UI, badges self-describe; "Eligible until" reads "Not set" on all rows; `?status=` still leaks enums into URLs |
| 3 | User Control and Freedom | 2 → 2 | Deep links read but never write; sorting and filtering remain unshareable |
| 4 | Consistency and Standards | 1 → 3 | Real GDS components and numeric tokens throughout; filter chips still hand-rolled with hardcoded text-white |
| 5 | Error Prevention | 2 → 2 | Chain slug now derived; Sepolia asserted verdicts the oracle never made (fixed after scoring) |
| 6 | Recognition Rather Than Recall | 1 → 3 | Legend gone, criteria on-page above the roster; table header still not sticky |
| 7 | Flexibility and Efficiency | 1 → 2 | Self-lookup and readable deep links; no URL writing, no shortcuts, no export, single-select chips |
| 8 | Aesthetic and Minimalist | 1 → 3 | One axis, no nested shadows, clean fold; dead column, 98 unpaginated rows |
| 9 | Error Recovery | 0 → 1 | Three empty states written, all three broken at score time (fixed after scoring) |
| 10 | Help and Documentation | 2 → 3 | Live-fetched criteria above the roster; still no remediation path for Grace or Expired |
| **Total** | | **14 → 25 / 40** | Acceptable — significant improvement, real defects remain |

## Deterministic evidence (Assessment B)

| Metric | Baseline | New |
|---|---|---|
| Contrast failures, LIGHT | 15 of 43 | **0 of 433** |
| Contrast failures, DARK | 4 of 43 | **0 of 433** |
| Controls without a focus ring | 9 of 13 | 1 of 26 → **0 after fix** |
| `:focus-visible` rules in HTML | 0 | 100 |
| Sortable headers keyboard-operable | 0 of 6 | **4 of 4** (Enter and Space) |
| Landmarks | 0 | 3 |
| Heading skips | h1→h3 | none |
| aria-live / aria-sort / aria-pressed | 0 / 0 / 0 | 2 / 4 / 5 |
| Touch targets under 44px @390 | 110 | 15 (13 real) |
| Mobile header collision | 1 | 0 |
| Console / page errors | hydration mismatch | **0** |
| In-page detector (light / dark) | 11 / 10 | **3 / 3** (1 a false positive) |
| Total uncompressed | 455.7 KB | 2.83 MB (~367 KB gzipped wire) |
| DOM nodes | 892 | 2,786 |

Lowest contrast ratio anywhere on the page is now 5.06:1. The baseline's worst finding — every status-carrying element failing AA in the default theme — is fully resolved, and light theme is genuinely designed rather than inherited.

## Regressions the rebuild introduced (all fixed after scoring)

1. Zero-result state never rendered on mobile — `NoMatches` sat inside a `hidden md:block` card.
2. "Clear filter" reset the status chip but ignored the search query.
3. Arbitrum Sepolia published 98 "Unqualified · never renewed" verdicts although its oracle has never run (`last_oracle_update_time: 0`) — a judgement about named third parties that no oracle issued.
4. 200 links had neither colour nor underline distinguishing them from body text (WCAG 1.4.1).
5. Oracle staleness was swallowed: mainnet last ran 30 days ago against a 14-day period, rendered as 48 healthy "Eligible · renewed" badges.

## Remaining known issues

- Page weight up ~6.5× uncompressed (2.83 MB, ~367 KB gzipped): 98 rows are SSR'd twice (table + mobile cards) and `gds.css` ships unpurged at 918 KB, render-blocking with no preloads.
- Mobile document height 18,193px — 98 cards with no pagination.
- Deep links read but never write; sorting and filtering are unshareable.
- Table header is not sticky across ~4,800px of rows.
- One input drives both the verdict card and the roster filter, while the roster heading still says "All".
- No remediation guidance for an indexer in Grace or Expired.
- Four sort buttons are 16px tall — below WCAG 2.2 §2.5.8 target size.
