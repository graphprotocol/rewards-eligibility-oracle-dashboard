# REO Dashboard — Frontend Rebuild (Kickoff Brief)

> Orient a fresh session (model: **Fable 5 / `claude-fable-5`, default effort**) to rebuild
> the Rewards Eligibility Oracle dashboard frontend for true **The Graph** brand compliance.
> Read this first, then `/impeccable critique` the current build and proceed.

## Why a rebuild (not a re-skin)
A token swap (PR #9) re-skinned the old hand-written layout with GDS color/font tokens. The
result still "doesn't look like a native thegraph.com web app" and can't fully honor
thegraph.com/brand. The layout, components, and information design need to be rebuilt using
GDS components and Impeccable's design quality bar. **PR #9 is the scaffolding you build on** —
keep its gds.css build pipeline, token wiring, and light/dark toggle; do not redo that plumbing.

## Baseline (what exists today)
- **`origin/main`** = Tomás's PR #8 (commit `05cf6b2`): testnet + mainnet simultaneous support,
  per-network RPC (`RPC_ENDPOINT_MAINNET`/`RPC_ENDPOINT_TESTNET`), chain-id field, ENS-resolution
  fix, removal of old testnet modes. **Do not re-add the tests/files he removed** (`test_core.py`,
  `test_runner.py`, `tests/README.md`).
- **PR #9 (`feat/gds-theme-pr`)** = GDS scaffolding on top of main: Dockerfile `gds-build` stage
  (compiles `gds.css` from `@graphprotocol/gds-css` + bundles Euclid Circular fonts), `:root`
  token aliases with hex fallbacks, `<button id="theme-toggle">` + `gdsTheme` localStorage
  (default light, `.gds-light`/`.gds-dark` on `<html>`), `scripts/build_gds_tokens.sh` (local
  build) and `scripts/preview_deploy.sh` (CF Pages preview).
- **Generator**: `generate_dashboard.py` — Python that fetches on-chain data and emits a single
  static `output/index.html` via f-strings. ~1000-line `<style>` block is the thing being replaced.

## Stack & tools for this session
- **Model**: Fable 5 (`claude-fable-5`), default effort.
- **Design system**: The Graph Design System — `@graphprotocol/gds-css` (npm 0.6.0). Confirmed
  tokens: `--color-brand-500 #6f4cff`, `--color-space-1700 #0c0a1d`; semantic light/dark tokens
  via native `light-dark()`, flipped by `.gds-light`/`.gds-dark` on `<html>` (set
  `color-scheme: only light/dark`). No `--background-color-surface` token exists (only `canvas`);
  space scale starts at `--color-space-100` (no `-50`).
- **Design quality**: Impeccable skill — `/impeccable critique`, `/impeccable audit`,
  `/impeccable polish` + anti-pattern detection. Use it to drive and review the redesign.
- **Brand**: fetch and follow **thegraph.com/brand** guidelines (typography, color, components,
  voice). The Graph, not "Graph" / "The Graph Protocol".

## KEY DECISION — architecture (resolve before coding)
"Actual data from onchain" can mean two things; pick one explicitly:
1. **Static snapshot, regenerated** (current arch) — **preferred/likely**: keep a generator
   (`generate_dashboard.py` or a successor) as the data layer; rebuild only the HTML/CSS/templates
   it emits. Freshness comes from **periodic regeneration**, not client-side fetching:
   - **Prod**: `scheduler.py` regenerates every ~5 min; Caddy serves the single endpoint
     `https://hub.thegraph.foundation/reo/`. Data is ≤5 min stale — effectively "always fresh."
   - **Previews**: CI regenerates per-commit and deploys to the stable branch alias.
   - Lowest risk; reuses the proven data pipeline; no secrets in the browser. **A live-fetching
     SPA is NOT needed** unless true sub-cycle real-time is required (it isn't, for this dashboard).
2. **Live-fetching app** (only if real-time-per-load is truly required): a JS frontend querying the
   network subgraph / RPC at load time. Bigger build; needs a data/API layer + in-browser secret
   handling. Almost certainly overkill here.

Default to option 1 unless the user says otherwise.

## Data sources & env (local `.env`, gitignored)
- `GRAPH_API_KEY` — The Graph network subgraph (active indexers).
- `ARBISCAN_API_KEY` — last transaction / deployment lookups.
- `RPC_ENDPOINT_TESTNET` (Arbitrum Sepolia) — present. `RPC_ENDPOINT_MAINNET` (Arbitrum One) —
  **not set locally**, so mainnet shows an empty state until an endpoint is added.
- `USE_CACHED_ENS=N` (Tomás's setting — live ENS resolution).
- Data shape: `active_indexers_{env}.json` — per indexer: `address`, `ens_name`, `status`
  (`eligible-active` / `eligible-grace` / `ineligible-*`), `eligibility_renewal_time`,
  `eligible_until`, `last_renewed_on_tx`, continuous-eligibility streak.

## Constraints / out of scope
- Keep the `gds.css` build pipeline (Dockerfile stage + `build_gds_tokens.sh`) and the theme
  toggle; build the new UI on top.
- Do **not** re-add files removed in PR #8.
- Observability/monitoring is a **separate, later** effort (deploy-failure alerting, uptime
  monitor) — not part of this rebuild.
- CI-driven per-PR preview deploys are **tabled until after monitoring**. For now, preview via
  `scripts/preview_deploy.sh` (manual snapshot deploy to `*.pages.dev`).

## Suggested first steps for the session
1. `git fetch origin && git checkout main && git pull` (start from Tomás's `main`); optionally
   merge/checkout PR #9's `feat/gds-theme-pr` to inherit the GDS scaffolding.
2. `/impeccable critique` the current `output/index.html` against thegraph.com/brand + GDS.
3. Confirm the architecture decision (snapshot vs live) with the user.
4. Rebuild the UI with GDS components; iterate with `/impeccable audit` / `/polish`.
5. Verify locally (`build_gds_tokens.sh` → `generate_dashboard.py` → open `output/index.html`),
   then `preview_deploy.sh` for a shareable preview; open a PR on top of `main`.

## Pointers
- Current generator + `<style>`: `generate_dashboard.py` (style block ~L1657–2720).
- GDS pipeline: `Dockerfile` (`gds-build` stage), `scripts/build_gds_tokens.sh`.
- Preview/deploy: `scripts/preview_deploy.sh` (CF Pages, project `reo-dashboard`, account
  `6a482fb0103e05ebeb185a55fddf3d15` = thegraph.foundation).
- Research/decisions log: project memory `gds-token-migration-research.md`,
  `cf-pages-preview-setup.md`.
