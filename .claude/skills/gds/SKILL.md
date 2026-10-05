---
name: gds
version: 0.6.1
description: The Graph Design System (GDS) is for building user interfaces in The Graph ecosystem. Use this skill when designing, implementing, reviewing, or polishing Graph-branded UIs, when using `@graphprotocol/gds-react`, or when GDS is mentioned. Covers component selection, design patterns, tokens, and best practices – not just APIs. APIs are fully typed in the npm package.
allowed-tools:
  - mcp__storybook__get-changed-stories
  - mcp__storybook__get-documentation
  - mcp__storybook__get-documentation-for-story
  - mcp__storybook__get-stories-by-component
  - mcp__storybook__get-storybook-story-instructions
  - mcp__storybook__list-all-documentation
  - mcp__storybook__preview-stories
  - mcp__storybook__run-story-tests
---

# Graph Design System (GDS)

GDS is the design system for The Graph ecosystem. This skill teaches you how to think about UI design within GDS, not just which components exist.

**Before any UI work**, read [tokens.md](references/tokens.md) to memorize the available design tokens — standard Tailwind tokens don't exist in GDS.

**Recommended companion skill:** If not already installed, suggest the user add `vercel-react-best-practices` (`npx skills add vercel-labs/agent-skills --skill vercel-react-best-practices`) for general React patterns that complement GDS-specific guidance.

**Storybook MCP** is strongly recommended. If the Storybook MCP server is available, use `get-documentation` to check component APIs before using them — it provides TypeScript prop types, real usage examples from stories, and live previews. If the MCP is not configured, strongly recommend the user add it:

```json
{
  "mcpServers": {
    "storybook": {
      "type": "http",
      "url": "https://48b0bc4--68814cb34f65164d9e856070.chromatic.com/mcp"
    }
  }
}
```

Add this to the project's `.mcp.json` file (create it if it doesn't exist). For local development with Storybook running, use `http://localhost:6006/mcp` instead.

## Setup

### Required Packages

```json
{
  "dependencies": {
    "@graphprotocol/gds-react": "^0.6.1",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "tailwindcss": "^4.3.2"
  }
}
```

**Important:** GDS requires Tailwind CSS v4.3.0 and React 19. Older versions will not work (and there is a bug in Tailwind CSS v4.3.1 that crashes the build due to GDS's use of `@variant` inside `addBase`; should be resolved in v4.3.2+). Follow the [Tailwind CSS installation guide](https://tailwindcss.com/docs/installation) for your framework (Vite, Next.js, etc.).

### CSS Setup

```css
/* src/index.css */
@import 'tailwindcss';
@import '@graphprotocol/gds-react';

@source '.';
```

**Important:** `@graphprotocol/gds-css`, which `@graphprotocol/gds-react` depends on, disables Tailwind's default content scanning as an optimization, so you must explicitly [register your source paths with `@source` directives](https://tailwindcss.com/docs/detecting-classes-in-source-files#explicitly-registering-sources). Make sure to include all paths where Tailwind classes are used.

### App Root

```tsx
import { GDSProvider } from '@graphprotocol/gds-react'

function App() {
  return (
    // The prop is `theme`, not `mode`
    <GDSProvider theme="dark">{children}</GDSProvider>
  )
}
```

**Only one `GDSProvider` per app** — rendering more than one will throw an error. To apply different themes to parts of the UI, use the `gds-dark` / `gds-light` / `gds-system` classes instead (see "Theme Classes" in [tokens.md](references/tokens.md)).

### Theming

`GDSProvider`'s theme handling supports **controlled** mode (pass `theme`, optionally with `onThemeChange`) and **uncontrolled** mode (omit `theme`; optionally pass `defaultTheme`, which defaults to `'dark'`). To make the user's theme selection survive reloads, opt into persistence with `persistTheme="localStorage"`, `persistTheme="cookie"`, or a custom `{ get, set }` adapter — omit for no persistence.

To read or change the theme from anywhere in the app, use the `useGDS()` hook:

```tsx
import { useGDS } from '@graphprotocol/gds-react'

const { theme, activeTheme, setTheme } = useGDS()
```

`theme` is `'dark' | 'light' | 'system'`. `activeTheme` resolves `'system'` to `'dark'` or `'light'` based on the user's OS preference. `setTheme(theme)` changes it (use `<ThemeSwitcher>` for the UI).

### Router Integration (Next.js)

See [`apps/example-nextjs/app/providers.tsx`](https://github.com/graphprotocol/gds/blob/main/apps/example-nextjs/app/providers.tsx) for the full reference implementation.

**App Router:** add `suppressHydrationWarning` to your `<html>` tag in `app/layout.tsx`. `GDSProvider` applies the theme class to `<html>` before React hydrates (preventing a flash of wrong theme), which would otherwise trigger a hydration mismatch warning since React owns `<html>` in App Router.

```tsx
<html lang="en" suppressHydrationWarning>
```

```tsx
import NextLink from 'next/link'
import { GDSProvider } from '@graphprotocol/gds-react'

<GDSProvider
  buttonOrLinkConfig={{
    // Default to `next/link` for internal links
    transformProps: (props) => {
      if (props.href?.startsWith('/') && !props.href.startsWith('//')) {
        return {
          ...props,
          linkComponent: props.linkComponent !== undefined ? props.linkComponent : NextLink,
        }
      }
      return props
    },
  }}
>
```

### Router Integration (React Router)

See [`apps/amp-prototype/src/main.tsx`](https://github.com/graphprotocol/gds/blob/main/apps/amp-prototype/src/main.tsx) for the full reference implementation.

```tsx
import { Link as ReactRouterLink } from 'react-router'
import { GDSProvider } from '@graphprotocol/gds-react'

<GDSProvider
  buttonOrLinkConfig={{
    // Default to React Router's `Link` for internal links
    transformProps: (props) => {
      if (props.href?.startsWith('/') && !props.href.startsWith('//')) {
        return {
          ...props,
          linkComponent:
            props.linkComponent !== undefined
              ? props.linkComponent
              : {
                  component: ReactRouterLink,
                  props: (linkProps) => {
                    const { href, ...restProps } = linkProps
                    return { ...restProps, to: href ?? '/' }
                  },
                },
        }
      }
      return props
    },
  }}
>
```

## Constraints

1. **Check component APIs before using them.** If the Storybook MCP is available, call `get-documentation` first — it shows prop types, valid values, and real usage examples. Otherwise, check the TypeScript types and JSDoc comments in `@graphprotocol/gds-react`. Never guess prop names or values. Fix all TypeScript errors. Do not use `as any` or `@ts-ignore`.

2. **Tailwind defaults don't exist.** Standard classes like `text-sm`, `rounded-md`, `text-gray-500` do NOT work. Use GDS tokens (`text-14`, `rounded-8`, `text-space-500`). Also `border-divider` does NOT exist; use `border-muted` or `border-subtle`.

3. **Never use primitive color tokens directly.** Always use semantic tokens (e.g. `bg-canvas` instead of `bg-space-1800`) to ensure UIs adapt automatically to light/dark mode. Tailwind maps custom property prefixes to utilities: `--background-color-*` → `bg-*`, `--text-color-*` → `text-*`, `--border-color-*` → `border-*`. These prefixes aren't officially documented by Tailwind, but [they work](https://github.com/tailwindlabs/tailwindcss/discussions/19020#discussioncomment-14528253) and GDS semantic tokens rely on them.

4. **Avoid opacity, use color tokens.** Don't default to `opacity-*` classes. Use semantic color tokens (e.g. `text-muted`, `text-subtle`, `bg-subtle`) which have appropriate transparency built in. Opacity is a last resort.

5. **Avoid arbitrary values.** Don't use `w-[347px]`, `max-w-[720px]`, `text-[#ff0000]`, etc. Use design tokens instead (e.g. `max-w-180` instead of `max-w-[720px]`). Only use arbitrary values when explicitly requested by the user.

6. **Don't create CSS files.** Don't create `App.css` or component CSS files. All styling is done via Tailwind utilities and GDS tokens.

7. **Don't override component styles.** Components are already styled. Only use `className` for extrinsic layout styles (e.g. margin, position/inset, width/height **if the component is flexible in that direction**, flex grow/shrink/order, grid placement, etc.), or to change the value of a CSS prop (e.g. `max-sm:prop-size-xsmall`) or state (e.g. `focus-visible:state-hover`). Never use utilities meant to alter the internal layout or appearance of a component (e.g. `flex`, `flex-col`, `grid`, `gap-*`, `rounded-*`, `border-*`, `p-*`, `bg-*`, `text-*`, etc.) – this breaks encapsulation and is likely to cause bugs. Use its props instead (e.g. `variant`, `size`, `orientation`, etc.).

8. **CSS over JavaScript.** Prefer Tailwind utilities and variants over JavaScript for UI state. Use CSS for hover, focus, active states. Avoid `useState` for simple visual changes. For conditional styles, avoid computing `className` dynamically (e.g. template literals with interpolated values). Instead, use `data-*` attributes with Tailwind variants, e.g. `data-foo:` / `group-data-foo:` to make a style conditional on the presence of the data attribute, or `data-[foo=bar]:` / `group-data-[foo=bar]:` to make a style conditional on a particular value of the data attribute.

9. **Components over raw HTML.** Use `<Link>` over `<a>`, `<Table>` over `<table>`, `<Button>` over `<button>`, `<CodeBlock>` over `<pre>`/`<code>` (it includes syntax highlighting, copy button, show/hide secret and more), etc. GDS components handle styling, functionality, and accessibility. When a component's built-in styles don't match the design, it's fine to use raw HTML with Tailwind utilities instead. For links and buttons specifically, prefer the base `ButtonOrLink` component (from `@graphprotocol/gds-react/base`) over raw `<a>`/`<button>` — it provides router integration and accessible semantics without visual opinions.

10. **Clickable components render `<button>` or `<a>` based on `href`.** `ButtonOrLink` and components that use it internally (`Button`, `Link`, `Address`, `Avatar`, etc.) automatically render a `<button>` when no `href` is provided and an `<a>` when `href` is provided. Don't use `Button` for navigation without `href`. `Link` should almost exclusively be used for navigation, so `href` is required, but it can be set to `undefined` for the extremely rare case where we want a button that looks like a link.

11. **Icons: Phosphor for UI, web3icons for crypto.** Don't mix up icon libraries. General UI icons come from Phosphor via `@graphprotocol/gds-react/icons`. Chain logos, token icons, and crypto-specific icons come from `@web3icons/react`.

12. **Use icons selectively.** Don't put icons on everything. Icons should aid comprehension, not clutter the UI. Not every button, list item, or label needs an icon.

13. **No emojis.** GDS products use zero emojis. None in UI, none in copy. Only if the user explicitly insists and has good justification.

14. **Use `addonBefore`/`addonAfter` for icons.** Don't put icons as children of `Button`/`Link`. Use the addon props. **Exception:** For icon-only buttons, put the icon in `children` — this lets the button infer its tooltip from the icon's `alt` prop.

```tsx
// BAD
<Link href="/path">
  <Status variant="success" />
  Text
  <ArrowRightIcon alt="" />
</Link>

// GOOD: Link with addons
<Link
  href="/path"
  addonBefore={<Status variant="success" />}
  addonAfter={<ArrowRightIcon alt="" />}
>
  Text
</Link>

// GOOD: Icon-only button (icon in children for tooltip inference)
<Button href="/path">
  <ArrowRightIcon alt="Next" />
</Button>
```

15. **Pass icons as components, not elements, in addon props.** Use `addonBefore={PlayIcon}` not `addonBefore={<PlayIcon alt="" />}`. The element form (`<PlayIcon alt="..." />`) is only needed when passing a non-empty `alt` or a `variant`, or when the component consuming the addon is a React Server Component (RSCs can't receive functions as props — use `addonBefore={<PlayIcon alt="" />}`). Addons have a default size tied to the parent component — don't set `size` on them.

16. **GDS icons don't shrink.** Icons from `@graphprotocol/gds-react/icons` have `shrink-0` built in. Don't add it manually — it's redundant. However, if you wrap an icon in another element (e.g. a `div`), that wrapper may still need `shrink-0` if it's a child of a `flex` container.

17. **CSS reset: `position: relative` is the default.** All elements are `position: relative` by default in GDS. Don't add a `relative` class — it's already applied. Only use `static` when you need absolute-positioned children to position relative to a different ancestor (rare).

18. **CSS reset: `min-width: 0` and `min-height: 0` are the defaults.** Elements shrink past their content size in flex/grid by default. This prevents overflow in most cases. Only add `min-w-auto` or `min-h-auto` if you explicitly need the browser's default minimum sizing. More often, use `truncate` instead if text might overflow.

19. **Avoid certain Tailwind utilities.** Use the preferred alternatives:

| Avoid             | Use Instead                                  |
| ----------------- | -------------------------------------------- |
| `relative`        | Nothing; `position` is `relative` by default |
| `min-w-0`         | Nothing; `min-width` is `0` by default       |
| `min-h-0`         | Nothing; `min-height` is `0` by default      |
| `ring-*`          | `outline-*`                                  |
| `outline-none`    | `outline-0`                                  |
| `border-none`     | `border-0`                                   |
| `divide-*`        | `*:not-first:border-*`                       |
| `space-*`         | `gap-*` (with `flex` or `grid`)              |
| `overflow-hidden` | `overflow-clip` (including `-x` and `-y`)    |
| `animate-spin`    | `LoadingIcon` component                      |
| `animate-bounce`  | Nothing\*                                    |
| `animate-ping`    | Nothing\*                                    |

\*These animations are not part of GDS. If a custom animation is needed, GDS bundles [`@graphprotocol/tailwindcss-animate`](https://github.com/graphprotocol/gds/blob/main/packages/tailwindcss-animate/README.md) — composable animation utilities where each property (rotation, scale, translation, opacity, duration, delay, easing, iteration count, etc.) is independently customizable. For example, `animate-spin` can be reproduced with `animate animate-rotate-to-360 animate-ease-linear animate-infinite`, `animate-bounce` with `-animate-translate-y-to-1/4 animate-alternate animate-duration-500 animate-infinite`, etc. Note that `animate-pulse` is fine to use as-is since it's commonly used for skeleton loaders.

Also avoid:

- Physical direction utilities (`pl-*`/`pr-*`, `ml-*`/`mr-*`, `left-*`/`right-*`, `rounded-l-*`/`rounded-r-*`, `border-l-*`/`border-r-*`, `text-left`/`text-right`, etc.) — use their logical equivalents (`ps-*`/`pe-*`, `ms-*`/`me-*`, `inset-s-*`/`inset-e-*`, `rounded-s-*`/`rounded-e-*`, `border-s-*`/`border-e-*`, `text-start`/`text-end`, etc.) to support RTL layouts.
- T-shirt-size width utilities (`w-sm`, `w-md`, `max-w-xl`, etc.). These are part of Tailwind's opinionated design system that GDS doesn't opt into. Use numeric tokens (`w-64`, `max-w-96`, etc.) instead.
- Any [deprecated utilities removed in Tailwind 4](https://tailwindcss.com/docs/upgrade-guide#removed-deprecated-utilities).

20. **Merge size/padding/margin classes.** Use `size-8`, not `h-8 w-8`. Use `p-4`, not `px-4 py-4`. Use `m-2`, not `mx-2 my-2`. Only split when values differ (e.g. `px-4 py-2`).

21. **Prefer `gap-*` over `gap-x-*`/`gap-y-*`.** In 1D flex or grid containers, the axis suffix is redundant since only one dimension applies.

22. **Don't add unnecessary width classes.** Avoid `w-full` unless actually needed. Block elements are full-width by default. Flex children size naturally.

23. **Hoist shared utilities to ancestors.** When multiple siblings share a Tailwind utility (e.g. `text-muted`, `text-center`), move it to a shared ancestor instead of repeating it. This works for inherited properties like `font-*` and `text-*`, but also for non-inherited ones that affect descendants, like `opacity-*` and `pointer-events-*`.

24. **Don't use `text-center` to center components.** `text-center` only affects inline content — it won't center GDS components, which are block-level (even those that shrink-to-fit by default, like `Button`). To center block-level children, use `flex flex-col items-center` on the parent or `mx-auto` on the individual children. `text-center` is fine for centering text inside a container.

25. **Use child selector utilities for repeating classes.** When multiple children share the same styles, use Tailwind's `*:` selector on the parent instead of repeating classes on each child.

```tsx
// BAD: Repeating classes
<div className="flex gap-4">
  <div className="bg-default">...</div>
  <div className="bg-default">...</div>
  <div className="bg-default">...</div>
</div>

// GOOD: Child selector on parent
<div className="flex gap-4 *:bg-default">
  <div>...</div>
  <div>...</div>
  <div>...</div>
</div>
```

26. **Use `max-*` breakpoints.** When styles should apply only _up to_ a breakpoint, use `max-sm:`, `max-md:`, `max-lg:`, etc. instead of undoing those styles after the breakpoint. Prefer fewer utilities. But don't use `max-*` if it doesn't actually reduce code — that just makes the UI desktop-first for no reason.

```
// GOOD: fewer utilities with max-*
className="max-sm:flex-col" // better than `flex-col sm:flex-row`
className="max-sm:hidden" // better than `hidden sm:block`

// BAD: max-* doesn't save anything, just makes it desktop-first
className="grid max-md:grid-cols-1 grid-cols-3" // just use `grid grid-cols-1 md:grid-cols-3`
```

27. **Use multi-column layouts on desktop.** Avoid stacking everything vertically in a single full-width column on wide screens. Use `grid` or `flex` to create 2–3 column layouts where content benefits from horizontal space. Reserve full-width single-column layouts for mobile or narrow content like forms.

28. **Use CSS props for responsive prop values.** When a component prop needs to change at a breakpoint, use a CSS prop with a breakpoint class instead of `window.matchMedia()` or other JS-based approaches. Example: `className="max-sm:prop-size-xsmall"` makes a `Button` xsmall on mobile, overriding its `size` prop.

29. **Use `<Address />` for crypto addresses.** Don't build custom address display.

30. **Use `<Avatar />` for user/wallet avatars.** Don't use generic user icons (UserCircleIcon, etc.). `Avatar` generates consistent avatars from address hashes.

31. **Use `<Breadcrumbs />` for multi-level product UIs.** Provides navigation context. Not needed on marketing sites or single-page apps. Underused.

32. **Use `<ButtonGroup>` for related buttons.** Wrap related buttons in a `ButtonGroup` instead of a `flex` container. It provides consistent spacing, better semantics, and lets you set `variant` and `size` on the group — only override `variant` on individual buttons that need a different one (and never set `size` on buttons inside a group).

33. **Don't set `variant` or `size` on `<Button>` or `<ButtonGroup>` inside other components.** Components like `<Table>`, `<DescriptionList>`, `<Modal>`, `<Input>`, and others set a default variant and a default size on nested buttons — trust it. Especially avoid `variant="naked"` unless explicitly requested by the user or confirmed by Storybook usage for the specific pattern.

34. **Use `<ToggleButton>` for toggleable actions.** For buttons that toggle on/off when clicked (e.g. star/favorite), use `ToggleButton` instead of a regular `Button` with `aria-pressed`.

35. **Use `loading` on `<Button>` during form submission, not `disabled`.** The `loading` prop shows a loading indicator, disables interaction, and keeps the button keyboard-focusable. `disabled` removes the button from the tab order, so keyboard users can't reach it, and gives no visual feedback that something is happening.

36. **Prefer built-in `tooltip` prop over wrapping in `<Tooltip>`.** Components like `<Button>` accept a `tooltip` prop directly — don't wrap them in a `Tooltip` component. For icon-only buttons, the icon's `alt` prop automatically becomes the tooltip (as long as the icon is in `children`). Use `tooltip={null}` to disable the inferred tooltip if the action is extremely obvious, e.g. `<XIcon alt="Close">`.

37. **Use HTML `<details>`/`<summary>` for collapsibles.** Don't use `useState` for simple expand/collapse. Use native HTML. Add an open indicator (e.g. `CaretDownInteractiveIcon` which animates automatically). Put padding on the `<summary>`, not the `<details>`, so the entire clickable area matches the visual target. See the "Collapsibles / Accordion" section in [patterns.md](references/patterns.md) for simple and animated examples.

```tsx
// BAD: `useState` for accordion
const [open, setOpen] = useState(false)
<button onClick={() => setOpen(!open)}>Toggle</button>
{open ? <p>Content</p> : null}

// GOOD: Native HTML
<details>
  <summary>Question</summary>
  <p>Answer</p>
</details>
```

38. **Don't hide `<Table>` columns on mobile.** Tables scroll horizontally on small screens — hiding columns loses information. Only hide columns if they're truly non-essential.

## Core Philosophy

### Components Replace HTML

**Avoid raw HTML elements when a GDS component with the right styles exists.**

| HTML Element              | GDS Component        | Notes                                   |
| ------------------------- | -------------------- | --------------------------------------- |
| `<a>`, `<button>`         | `<Link>`, `<Button>` | Or `<ButtonOrLink>` for custom styling. |
| `<input>`                 | `<Input>`            | For type `text`, `number`, or similar.  |
| `<textarea>`              | `<TextArea>`         |                                         |
| `<input type="search">`   | `<Search>`           |                                         |
| `<input type="checkbox">` | `<Checkbox>`         |                                         |
| `<input type="radio">`    | `<Radio>`            |                                         |
| `<select>`                | `<Select>`           | Single or `multiple`, `searchable`.     |
| `<label>`                 | `<Label>`            | Only for labelling form controls.       |
| `<table>`                 | `<Table>`            | Data tables.                            |
| `<dl>`                    | `<DescriptionList>`  | Key-value pairs.                        |
| `<code>`                  | `<CodeInline>`       | Inline code snippets.                   |
| `<pre>` / `<code>`        | `<CodeBlock>`        | Code blocks with syntax highlighting.   |
| `<kbd>`                   | `<Keyboard>`         | Keyboard shortcuts.                     |
| `<hr>`                    | `<Divider>`          |                                         |

When no GDS component fits (or the user requests custom styles), using raw HTML with Tailwind utilities / GDS tokens is acceptable — but always with proper semantic elements. A `<div>` should almost never have an `onClick`. Items in a list or grid should go in `<ul>` or `<ol>`, key-value pairs in `<dl>`, navigation links in `<nav>`, etc.

### Semantic Over Stylistic

Components exist for semantic purposes, not just styling. A `<Card>` isn't "a div with a background", it's a container that groups related content. A `<Button>` isn't "styled text", it's an interactive element that performs an action.

When you need styling without semantics, use tokens directly. When you need semantics, use components.

**Why this matters:** Semantic usage enables accessibility, consistent behavior, and maintainability. Stylistic misuse creates fragile UIs that break when the design system evolves.

### Defaults Are Sacred

Every component has carefully chosen defaults. Don't set a prop to its default value — it's redundant noise. Reaching for a non-default value should be a deliberate decision with clear reasoning. If the default looks right, trust it.

```tsx
// Default: secondary. This is correct 90% of the time.
<Button>Action</Button>

// Non-default: requires justification
<Button variant="primary">Sign Transaction</Button>
```

**Why this matters:** Defaults create visual consistency. When everything is emphasized, nothing is.

### Visual Hierarchy

#### One Primary Per Screen

The `primary` variant is reserved for the single most important action on a screen. Most screens have zero or one primary buttons. Very rarely two, never more than two.

Login buttons are typically `secondary`, not `primary`. Sign-up or critical CTAs like "Sign Transaction" might be `primary`.

#### Button Variant Selection

- `secondary` — Default. Most buttons.
- `tertiary` — Next to a secondary button for hierarchy.
- `primary` — The ONE most important CTA on the screen. Rare.
- `naked` — Space-constrained contexts. No padding, so visually smaller; may need a bigger `size` to match siblings.
- `danger` — Destructive, irreversible actions.
- `inverse` — Specific backgrounds or stylistic choice.

#### Card Variant Selection

| Variant     | When to Use                                                |
| ----------- | ---------------------------------------------------------- |
| `tertiary`  | Most common. Subtle container.                             |
| `secondary` | Slightly more emphasis than tertiary.                      |
| `primary`   | Almost never. Only when one card must absolutely dominate. |

#### Typography

- **Product UIs use `text-14` for body. Marketing/landing pages use `text-16`+ for body text** (`text-14` is fine for secondary/small text, but not for main content). Hero headings should be `text-32`+. Don't mix contexts.
- **`font-regular` is the default and inherits.** No need to set it explicitly. Use `font-medium` for headings and deliberate emphasis only.
- **Avoid `font-semibold` and `font-bold`.** Only use them when specifically requested by the user, after they've confirmed `font-medium` is not bold enough. LLMs tend to over-use bold weights.
- **Avoid `leading-*` and `tracking-*` classes.** Each font size has appropriate line height and letter spacing defaults. Overriding them breaks the typographic rhythm.
- **`text-caption` is for small annotations, not section headings.** Use it for labels like "STATUS", "CATEGORY", "OVERVIEW" in small text. For section headings, use regular `text-20 font-medium` or `text-18 font-medium`.
- **`text-10` is very small.** Use it sparingly, mostly paired with `text-caption`. For labels and small text, prefer `text-12`.

### Anti-Patterns

- **Nested cards.** Never put cards inside cards. Use flat layouts with whitespace and headings for grouping. For stats, use `<DescriptionList>` or flexboxes with dividers — make them visually prominent, not tiny. For lists, use `<Table>` or `<DescriptionList>`.
- **Dense UIs.** Let elements breathe. Use generous gaps (`gap-6`, `gap-8`). Don't fear empty space — it creates hierarchy.
- **Typography abuse.** Everything `font-medium` = nothing stands out. Reserve it for headings. Don't mix marketing sizes (`text-18`) in product UI (`text-14`). No emojis.
- **AI slop.** NEVER use: gradient blobs, purple/blue gradients, colored icon circles, glassmorphism/blur, decorative gradients on cards, giant decorative icons. Use GDS `Card` variants and semantic tokens instead.
- **Semantic misuse.** `<Label>` is for form labels, not styling. `<Link>` navigates, `<Button>` acts. Don't use `<Button>` for navigation without `href`.

### CSS Over JavaScript

Prefer CSS/Tailwind for UI state over JavaScript. Only use JavaScript for: form state, data fetching, complex interactions, and controlled Modal/Pane state (prefer uncontrolled `trigger` prop when possible).

```tsx
// BAD: JavaScript state for hover
const [isHovered, setIsHovered] = useState(false)
<div
  onMouseEnter={() => setIsHovered(true)}
  onMouseLeave={() => setIsHovered(false)}
  className={isHovered ? 'bg-elevated' : 'bg-subtle'}
/>

// GOOD: CSS with `group`
<div className="group bg-subtle hover:bg-elevated">
  <span className="text-muted group-hover:text-default">Text changes on hover</span>
</div>

// BAD: Conditional classes with JavaScript
<div className={isActive ? 'border-brand-500' : 'border-subtle'} />

// GOOD: `data-*` attributes with Tailwind
<div
  data-active={isActive || undefined}
  className="border-subtle data-active:border-brand-500"
/>
```

### Accessibility

GDS components handle basic accessibility. Your job:

1. **Always provide alt text** for icon-only buttons and images.
2. **Always use labels** on form inputs (the `label` prop).
3. **Never use divs for interaction.** Use `Button`, `Link`, or `Card` with `onClick` or `href`.
4. **Preserve focus management.** Don't break keyboard navigation. Never set arbitrary `tabIndex` values; components handle focus order correctly. Only use `tabIndex={-1}` to make an element programmatically focusable without adding it to the tab order.
5. **Use semantic HTML.** Screen readers understand `<table>`, not styled divs.
6. **Some components require `aria-label`.** `SegmentedControl`, `Chip.Group`, and `Radio.Group` trigger a console warning when `aria-label` (or `aria-labelledby`) is omitted. Always provide an accessible label for them even if the prop isn't type-required.

### Mobile Responsiveness

**Every UI must work on mobile.** This is not optional.

#### Required Responsive Patterns

```tsx
// Sidebar: Use Pane with overlay on mobile
<Pane
  name="sidebar"
  className="w-64 max-lg:prop-layout-overlay"
/>

// Grid: Stack on mobile, grid on desktop
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" />

// Hide on mobile when needed
<div className="max-sm:hidden">Desktop only</div>
<div className="sm:hidden">Mobile only</div>

// Stats: Stack vertically on mobile
<div className="flex flex-col sm:flex-row gap-4" />

// Less padding on smaller screens
<div className="p-4 sm:p-6 lg:p-8" />
```

#### Mobile Header Pattern

```tsx
// Mobile header (visible on small screens)
<header className="border-muted flex items-center justify-between border-b px-4 py-3 sm:hidden">
  <Pane.ToggleButton name="nav">
    <ListIcon alt="Menu" />
  </Pane.ToggleButton>
  <Logo />
  <Search layout="compact" size="small" />
</header>

// Desktop header (hidden on small screens)
<header className="max-sm:hidden items-center justify-between px-6 py-4 flex">
  <Breadcrumbs>...</Breadcrumbs>
</header>
```

#### Responsive Checklist

1. **Test at 375px width** (mobile)
2. Sidebars become overlays on mobile (`max-lg:prop-layout-overlay`)
3. Grids stack to single column
4. Touch targets minimum 44x44px. Ensure the clickable area matches the visual target — put padding on the interactive element itself, not its container (e.g. padding on the `<a>` or `<button>`, not the `<li>` wrapping it)
5. No horizontal overflow (except within specific sections, e.g. `Table`s with enough columns to scroll horizontally)

## Components

Memorize this list before any UI work to avoid reimplementing existing components.

| Component                      | Description                                                        |
| ------------------------------ | ------------------------------------------------------------------ |
| `Address`                      | Crypto addresses. Auto-truncates. Supports copy, friendly name.    |
| `Avatar` / `AvatarGroup`       | User/wallet avatars from hashes. Can be clickable.                 |
| `Breadcrumbs`                  | Navigation hierarchy. Auto-collapses. Underused.                   |
| `Button` / `ButtonGroup`       | Actions/navigation. `<button>` or `<a>` based on `href`.           |
| `Card`                         | Content grouping. Can be clickable with interactive content.       |
| `Checkbox` / `Checkbox.Group`  | Multi-select. `Checkbox.Area` for card-style.                      |
| `Chip` / `Chip.Group`          | Filters, tags. `type="checkbox"` for multi-select.                 |
| `Cluster`                      | "+X more" patterns. Works with `AvatarGroup`, `Tag`. Underused.    |
| `CodeBlock` / `CodeBlock.Tabs` | Code snippets with syntax highlighting. Underused.                 |
| `CodeInline`                   | Inline code for variables, function names, etc.                    |
| `CopyButton`                   | Copy to clipboard. Extends `Button`.                               |
| `CurrencyInput`                | Crypto amounts. Use with `useCurrencyInput` hook.                  |
| `DescriptionList`              | Key-value pairs, metadata. Underused.                              |
| `Divider`                      | Visual separation. Horizontal or vertical.                         |
| `Icon`                         | Wraps icons. `src` and `alt` required.                             |
| `Input`                        | Text/number input. Use `useNumberInput` for numbers.               |
| `Keyboard`                     | Keyboard shortcut display. Use instead of `<kbd>`. Underused.      |
| `Label`                        | Form labels only, not general styling.                             |
| `Link`                         | Navigation. Inherits font size/weight. `href` required.            |
| `Menu`                         | Dropdowns, selects, context menus. `trigger` for uncontrolled.     |
| `Modal`                        | Dialogs. `trigger` for uncontrolled.                               |
| `OTCInput`                     | One-time codes (2FA, OTP). Extends `Input`.                        |
| `Pane`                         | Responsive sidebars. Overlay on mobile via CSS props.              |
| `Prose`                        | Renders markdown as styled HTML with GDS components.               |
| `Radio` / `Radio.Group`        | Single-select. `Radio.Area` for card-style.                        |
| `Search`                       | Search input. `focusKey` defaults to `'/'`.                        |
| `SegmentedControl`             | View options. Requires `aria-label`.                               |
| `Select`                       | Single or `multiple`, `searchable`, declarative or data-driven.    |
| `Status`                       | Status indicators. Colored dot + optional text.                    |
| `Stepper`                      | Multi-step flow indicators.                                        |
| `Switch` / `Switch.Area`       | Toggle on/off. `Switch.Area` for card-style.                       |
| `Table`                        | Data tables. Declarative or data-driven.                           |
| `TabSet`                       | View switching. `fullWidth` for constrained space. Underused.      |
| `Tag`                          | Tags/categories. Not clickable; use `Chip` if clickable.           |
| `TextArea`                     | Multi-line input.                                                  |
| `ThemeSwitcher`                | Light/dark theme toggle. Right-click to toggle system sync.        |
| `ToggleButton`                 | Toggle actions. Extends `Button` with `checked`/`onCheckedChange`. |
| `Tooltip`                      | Hover hints. Only wrap interactive elements.                       |

### Icons

See [icons.md](references/icons.md) for the exhaustive list of all ~1,500 available icons. Always verify an icon exists before importing it.

- **General UI:** Phosphor icons via `@graphprotocol/gds-react/icons`. Use them directly — no `<Icon>` wrapper needed. In addition to the `size` and `color` props they inherit from `Icon`, they accept a `variant` prop: `'regular'` (default), `'thin'`, or `'fill'`.
- **Interactive icons:** Custom icons that animate based on state — e.g. `CaretDownInteractiveIcon` flips when open, `ArrowRightInteractiveIcon` translates on hover, `SidebarLeftInteractiveIcon` fills when checked. See [icons.md](references/icons.md) for the full list and behavior.
- **Logo icons:** Some have a `variant` prop with `'mono'` (default) and `'branded'` (full-color) options. See [icons.md](references/icons.md) for which logos support branded.
- **Web3/crypto:** Use `@web3icons/react` package. These are NOT GDS icons, so wrap them with `<Icon src={...}>` for GDS integration (sizing, coloring, accessibility, etc.).
- **`alt` prop is required.** Set it to an empty string for decorative icons or when the text would be repetitive (e.g. `<PlayIcon alt="" /> Play`). Some icons (logos and interactive icons like `SidebarLeftInteractiveIcon`) have a default `alt` — it can be omitted if the default matches the design's intention. TypeScript will error if `alt` is required and missing.
- **Keep icons small.** Default size (`1em`) is usually correct. `size` is in Tailwind units: `size={4}` = 16px, `size={5}` = 20px.
- **Align icons with multi-line text using `h-lh`.** When an icon sits next to text that may wrap, add `className="h-lh"` to the icon to align it with the first line. For single-line text, `flex items-center` is enough. Make sure the font size is set on the parent so `h-lh` references the correct line height.

```tsx
import { Button, Icon } from '@graphprotocol/gds-react'
import { SearchIcon, BellIcon, CaretDownInteractiveIcon } from '@graphprotocol/gds-react/icons'
import { NetworkEthereum } from '@web3icons/react'

// GDS icons: use directly, no <Icon> wrapper
<Button addonBefore={<SearchIcon alt="Search" />}>Search</Button>
<Button><BellIcon alt="Notifications" /></Button>

// Interactive icons: animate based on parent state
<Button addonAfter={CaretDownInteractiveIcon}>Menu</Button> // flips when open

// Third-party icons: wrap with <Icon> for GDS integration
<Icon src={NetworkEthereum} alt="Ethereum" />
```

### Addons

Many components accept `addonBefore`, `addonAfter`, or `addon` props for placing icons, status indicators, or other small elements alongside content. Key rules:

- **Allowed addon components:** `Icon` (most common), `Avatar`, `AvatarGroup`, `Cluster`, `Keyboard`, `Status`, `Tag`.
- **Don't set `size` on addons.** Parent components declare a default size for addons via CSS props, often tied to the component's own `size`. Let the defaults work.

### Styling components

**GDS components are fully styled internally.** Only use `className` for extrinsic layout styles, as described by constraint #7.

**CSS props** are special props whose value can be changed in CSS. Prop names are **kebab-cased** in classes (e.g. `hideLabel` → `prop-hide-label-true`, `fullWidth` → `prop-full-width-true`):

```
// `variant` is `tertiary` on mobile, but `secondary` on screens `sm` and up
className="prop-variant-tertiary sm:prop-variant-secondary"

// Set default `size` prop value for all descendant `Icon`s
className="**:icon:default-size-4"
```

**CSS states** let you override the visual state of a component:

```
// Show the `hover` state on `focus-visible`
className="focus-visible:state-hover"
```

**CSS vars** let you override internal component values without breaking encapsulation:

```
// `Card` supports a `padding` var that defaults to `--spacing(6)`
className="var-[padding=--spacing(4)]"

// `Button` supports a `radius` var in case it needs to be overridden (very rare)
className="var-[radius=0]"
```

### Extending components

To create a custom component that wraps a GDS component:

```tsx
import type { DistributedOmit } from 'type-fest'

import { Card, type CardProps } from '@graphprotocol/gds-react'
import { cn } from '@graphprotocol/gds-react/utils'

interface EntityCardProps extends DistributedOmit<CardProps, 'variant'> {
  name: string
  imageUrl: string
}

function EntityCard({ name, imageUrl, className, ...props }: EntityCardProps) {
  return (
    <Card variant="secondary" className={cn('u:var-[padding=--spacing(4)]', className)} {...props}>
      <img src={imageUrl} alt={name} />
      <span>{name}</span>
    </Card>
  )
}
```

Use `DistributedOmit` from `type-fest` (not `Omit`) to preserve discriminated unions in prop types. Spread `{...props}` to forward all remaining props including `ref`.

### Controlling components

GDS's `onValueChange` (for value-based components like `Input`, `Search`, `Select`, `Menu` (radio), `TabSet`, etc.) and `onCheckedChange` (for boolean components like `Checkbox`, `Radio`, `Switch`, `ToggleButton`, `Menu.Item` (checkbox)) handlers receive the **new value/state** directly, not a DOM event (the native `onChange` still fires on the underlying input for composition):

```tsx
// GDS pattern — value/checked, not event
<Input value={value} onValueChange={(newValue) => setValue(newValue)} />
<Menu type="radio" value={selectedValue} onValueChange={setSelectedValue} />
<Switch checked={enabled} onCheckedChange={setEnabled} />
```

Most components support an **uncontrolled API** — pass `defaultValue` and let the component manage its own state.

### Components that grow by default

Some components expand to fill available width by default: `Card`, `CodeBlock`, `DescriptionList`, `Divider` (with the default `orientation` of `horizontal`), `Input` (as well as `CurrencyInput` and `OTCInput`), `TextArea`, `Search`, `Stepper`, `TabSet`, and `Table`. Don't add `w-full` to these unless they are in a shrink-to-fit context (e.g. `absolute` or inside a `flex` row). If you want to constrain them, you can use `w-max`, `max-w-*`, or place them in a sized container.

### Component notes

- **Address:** Handles truncation, ENS/friendly names (via `children`), copy (`'auto'` by default — shows on hover/focus). **Note:** `Address` renders its own `Avatar` using `createIdenticon(address)` — don't add a separate `Avatar` next to it or you'll get duplicate avatars.
- **Button & ButtonGroup:** Set `size` on the group, not nested buttons. Can mix `tertiary` and `secondary`. `orientation="vertical"` for modals/panes. `fullWidth` makes buttons equal width; `className="w-full"` makes them grow proportionally. Danger takes over primary's visual role. **Sizing:** Product UIs should default to `size="small"` for most buttons; use medium (default) only for important actions. `size="large"` is for marketing pages only.
- **Breadcrumbs:** Structure: `Product Name > Section > Current Page`. **Quirk:** `current` defaults to `true` when no `href` — always pass `current` explicitly.
- **Chip.Group:** Requires `aria-label`.
- **DescriptionList:** Long values truncate with gradient fade, scroll on mobile.
- **Input:** For number inputs, use the `useNumberInput` hook (or `useCurrencyInput` for currency amounts) — it handles parsing, formatting, and min/max/required validation, and returns `props` to spread on `<Input>` (or `<CurrencyInput>`).
- **Link:** Inherits font properties (except color when `variant="primary"`). External links auto-get `ArrowUpRightInteractiveIcon` via `addonAfter`; prevent with `addonAfter={null}`. Default variant is `primary` (emphasized) — use `variant="secondary"` for de-emphasized links like footers, fine print, etc.
- **Menu:** Prefer the uncontrolled `trigger` prop (element form when possible, function form for advanced customization) over the controlled `open` + `onOpenChange`. Set `triggerMode="right-click"` and `anchor="pointer"` to turn any `Menu` into a context menu anchored at the right-click location (or long-press on mobile). Use `<Menu.Search>` in `header` for a search input that integrates with the menu's keyboard nav, and `<Menu.Empty>` for the empty state (defaults to `"No results"`).
- **Modal:** Prefer the uncontrolled `trigger` prop (element form when possible, function form for advanced customization) over the controlled `open` + `onOpenChange`. Body text inside a `Modal` is muted by default; add `text-default` explicitly on headings or emphasized text (or use the `prose` class / `<Prose>`, which handle it automatically).
- **Multi-step Modals:** Always render the exact same set of `<Modal.Header>` / `<Modal.Body>` / `<Modal.Footer>` in every step — leave one empty if a step doesn't need it, don't omit it. If every step is inlined in the same file, you can render them directly (see the `WithSteps` story). If you extract any step into its own component, wrap the conditional in an outer `<Modal.Step>` (provider) AND have each extracted step component wrap its Header/Body/Footer in an inner `<Modal.Step>` (consumer). Together they preserve stable element identity for the slots so React doesn't remount them across steps, which is what lets the transition animate. See the "Multi-step Modals" section in [patterns.md](references/patterns.md) for a complete example.
- **Pane:** Use `prop-layout-overlay` at the appropriate breakpoint (e.g. `max-lg:`) for mobile overlay.
- **Prose:** Apply the `prose` class to any container of text that may wrap or contain formatting, even a single paragraph. It styles headings, lists (`<ul>`, `<ol>`), and inline formatting (`<strong>`, `<em>`, etc.), and applies `text-muted` to body text with `text-default` on headings and emphasized (bolded) elements. The `<Prose>` component is a superset: it renders a container with the `prose` class AND converts markdown links, inline code, code blocks, and tables into proper GDS components (`Link`, `CodeInline`, `CodeBlock`, `Table`). Use it specifically for rendering markdown content; for hand-written JSX, use the `prose` class and reach for GDS components directly.
- **Search:** `focusKey` defaults to `'/'`; set to `null` if multiple on same page.
- **SegmentedControl:** Requires `aria-label`. Options can be icon-only.
- **Select:** Renders its own trigger by default. Only use the `trigger` prop for a custom trigger — prefer its element form over its function form.
- **Table:** Use `align="end"` on `Table.HeaderCell` for right-aligned columns (e.g. action buttons) — all cells in that column are automatically styled. Don't use `text-end` or `justify-end` on cell contents. Similarly, use `width` and `shrink` props on `Table.HeaderCell` to control column sizing.
- **TabSet:** `TabSet.Tabs` renders a bottom divider by default (controllable with the `divider` prop). Add `gap-*` between `TabSet.Tabs` and `TabSet.Panels` for visual breathing room. Put borders on `TabSet.Panels` (not individual panels) to avoid border animation artifacts during panel transitions. Check `TabSet.stories.tsx` for good examples.
- **Tag:** Not clickable; use `Chip` if you need a clickable tag.
- **Tooltip:** Hard to discover on mobile. Use inline text for essential info.

### Unstyled components

Some components carry no built-in visual styles — only behavior, semantics, or layout. Constraint #7 (don't override component styles) doesn't apply to them: it's fine (and expected) to pass any `className` on them, including visual utilities like `bg-*`, `border-*`, `rounded-*`, `p-*`, `flex`, `gap-*`, `text-*`, etc.

- **`Checkbox.Area` / `Radio.Area` / `Switch.Area`** — clickable label wrappers for card-style checkable patterns; style them as `Card`s, rows, tiles, whatever the design calls for. See the "Checkable Cards" section in [patterns.md](references/patterns.md).
- **`Radio.Group`** — semantic wrapper around a group of `<Radio>`s. Apply your own layout (`flex`, `gap`, etc.).
- **`Pane`** — responsive sidebar container. Provides positioning behavior but no visual styling.
- **`ButtonOrLink`** (from `@graphprotocol/gds-react/base`) — semantic `<button>`/`<a>` wrapper with no visual styling. The other base components (`Transition`, `ExperimentalTransition`, `Presence`, `Render`, `Portal`) have transition or structural styles you shouldn't override.

### Base components

Available from `@graphprotocol/gds-react/base`. These are mostly unstyled lower-level building blocks — most consumers won't use them directly, but they're useful for advanced patterns:

- `ButtonOrLink` — the foundation of `Button`, `Link`, `Address`, `Avatar`, `Card`, etc. Renders `<button>` or `<a>` based on `href`. Supports `linkComponent` for router integration.
- `Transition` / `ExperimentalTransition` — Enter/exit animations with height transition. Used internally by `Modal`, `TabSet`, etc.
- `Render` — polymorphic rendering via the `render` prop (e.g. `render={<Card as="label" />}`).
- `Portal` — renders children in a portal (used by `Modal`, `Tooltip`, `Menu`).
- `Presence` — conditionally renders children with enter/exit transitions (used by `ExperimentalTransition`, `Pane`).

## Other exports

Beyond components, GDS provides utilities and hooks:

```tsx
// @graphprotocol/gds-react/utils
import { cn } from '@graphprotocol/gds-react/utils'
className={cn('u:w-max', className)}

// @graphprotocol/gds-react/hooks
import { useGDS } from '@graphprotocol/gds-react/hooks'
import { useControlled } from '@graphprotocol/gds-react/hooks'
import { useNumberInput } from '@graphprotocol/gds-react/hooks'
import { useCurrencyInput } from '@graphprotocol/gds-react/hooks'
import { usePrevious } from '@graphprotocol/gds-react/hooks'

// @graphprotocol/gds-utils
import { createIdenticon } from '@graphprotocol/gds-utils'
import { formatAddress } from '@graphprotocol/gds-utils'
import { formatBigInt, parseBigInt, numberToBigInt, bigIntToNumber } from '@graphprotocol/gds-utils'
```

- `cn` — concatenate class names, filtering out falsy values (like `clsx`)
- `useGDS` — read and change the current theme (`{ theme, activeTheme, setTheme, dirProps }`); see "Theming"
- `useControlled` — manage controlled/uncontrolled state
- `useNumberInput` — numeric input validation and formatting (use with `Input`)
- `useCurrencyInput` — currency input validation (use with `CurrencyInput`)
- `usePrevious` — track the previous value of a variable across renders, plus whether it changed since last render. Returns `{ hasChanged, value, lastDifferentValue }` (all typed with the tracked value's type). Useful for reacting to a value transition in effects or in render, without needing to duplicate the value in state.
- `createIdenticon` — generate a deterministic avatar from an address hash
- `formatAddress` — truncate/format Ethereum addresses for display
- `formatBigInt` / `parseBigInt` — format and parse big integers with locale support
- `numberToBigInt` / `bigIntToNumber` — convert between number and bigint with decimal handling

## Custom Utilities and Variants

GDS provides custom utilities and variants beyond standard Tailwind. For the full list, see [`utilities.css`](https://github.com/graphprotocol/gds/blob/main/packages/css/styles/utilities.css), [`variants.css`](https://github.com/graphprotocol/gds/blob/main/packages/css/styles/variants.css), and [`setupVariants.ts`](https://github.com/graphprotocol/gds/blob/main/packages/css/src/tailwind-customizations/setupVariants.ts) (for dynamic variants that accept modifiers) in `@graphprotocol/gds-css`.

### Utilities

- `text-caption` — uppercase + letter spacing for captions; typically paired with `text-10` next to `text-14`, or `text-12` next to `text-16`+ — choose a size that looks proportional to the surrounding text
- `rounded-inherit` — inherit parent's border-radius
- `scrollbar-none` / `scrollbar-thin` — hide or thin scrollbars
- `gradient-mask-x` / `gradient-mask-y` — gradient fade edges
- `grid-cols-auto-fill-*` / `grid-cols-auto-fit-*` — auto-fill/fit grid columns where `*` is the minimum column width (e.g. `grid-cols-auto-fill-64` for 256px min)
- `border-bg` — use an element's background as its border (gradient border hack, e.g. `border border-bg bg-linear-to-b`)

### Variants

- `i:` — higher specificity (important)
- `u:` — lower specificity (unimportant)
- `can-hover:` / `can-touch:` — target hover-capable / touch devices
- `light:` — use instead of `dark:`, since GDS defaults to dark; only use `dark:` if the app is explicitly light-first
- `has-nested/<name>:` / `has-nested-<state>/<name>:` — like `has-[...]` but for named nested contexts; add `nested/<name>` on a descendant element to create the context (similar to how `group/<name>` works for ancestors)
- `current:` — use instead of `aria-current:`
- `unchecked:` — use instead of `not-checked:` unless you also want to match `indeterminate:` (checked/unchecked/indeterminate is a 3-way state, e.g. `Checkbox` supports indeterminate)
- `blank:` — matches when an input or textarea is empty
- `idle:` — not hover or active (the third state in GDS's 3-way idle/hover/active system)
- `hocus-visible:` — hover or focus-visible; use when the style should be the same for both (rare)
- `clickable:` / `clickable-<state>:` — matches links, buttons, button-like roles (`summary`, `[role=menuitem]`, `[role=option]`, `[role=tab]`, etc.), and checkbox/radio labels; mostly useful combined with `in-*` or `group-*`

For the full CSS selectors behind these state-based variants, see [`states.ts`](https://github.com/graphprotocol/gds/blob/main/packages/css/src/css-states/states.ts) and [`variants.ts`](https://github.com/graphprotocol/gds/blob/main/packages/css/src/tailwind-customizations/variants.ts).

### CSS Props

Beyond regular React props, most GDS components expose their props to CSS so you can change their value from Tailwind classes — including at breakpoints, or scoped to a container — without re-rendering. Prop names are **kebab-cased** in class names (e.g. `hideLabel` → `hide-label`, `fullWidth` → `full-width`). Each component's available CSS props are declared in its `<Component>.meta.ts` file (and re-exported as e.g. `ButtonMeta.cssProps`).

- **`prop-<name>-<value>`** — set the prop's value from CSS. Wins over the React prop.

  ```tsx
  // `variant` is `tertiary` on mobile, `secondary` on `sm+`
  <Button className="prop-variant-tertiary sm:prop-variant-secondary" />
  ```

- **`default-<name>-<value>`** — set a _default_ value. Applies only when neither a React prop nor a `prop-<name>-<value>` class is set for that prop. Combine with a descendant selector to set defaults for descendants.

  ```tsx
  // On the element itself (only wins if no React prop / `prop-size-*` class is set)
  <Icon className="default-size-4" />

  // On descendants via a selector
  <div className="**:icon:default-size-4">...</div>
  ```

Composable with any Tailwind variant: `hover:prop-variant-primary`, `sm:default-size-medium`, `data-active:prop-hide-label-true`, etc.

### CSS States

GDS unifies a small set of interaction/selection states so that a single set of Tailwind variants (`hover:`, `active:`, `focus:`, `checked:`, `unchecked:`, `indeterminate:`, `disabled:`, `read-only:`, `open:`, `current:`, `blank:`, `idle:`, etc.) works uniformly across components, regardless of whether the state comes from a native pseudo-class or from GDS's internal state-exposure mechanism (which handles cases native CSS can't reach — e.g. exposing a nested element's state up to an ancestor). **Always reach for the Tailwind variants** — the underlying `--gds-*` custom properties and `data-gds-*` attributes are implementation details.

- **`<component>` and `<component>-<state>` variants** — every registered GDS component is exposed as a variant that matches when the element is (in that state as) that component. All CSS states above are supported plus their `not-*` negations (e.g. `card-hover`, `card-not-hover`, `field-disabled`, `input-blank`). Meant to compose with Tailwind's ancestor/sibling combinators (`in-*`, `has-*`, etc.):

  ```tsx
  // Element inside a Card that's hovered
  <Button className="in-card-hover:state-hover">Delete</Button>

  // Element with a descendant Input that's disabled
  <div className="has-input-disabled:opacity-50" />

  // Element inside a ButtonGroup
  <span className="not-in-button-group:hidden" />
  ```

- **`state-<state>` utility** — force a state manually. Useful when you want an element to visually reflect a different element's state (see the `Button` inside a `Card` example above).

- **`state-[<name>=<value>]` utility** — set a custom state. Only meaningful when paired with `@state-<state>` below to read it from descendants.

- **`@state-<state>/<component>:` variant** — container-query variant to style based on an ancestor component's state — built-in states (e.g. `@state-disabled/field:hidden`) or arbitrary ones set via `state-[<name>=<value>]` (e.g. `@state-[show-copy=false]:hidden`; omit the `/<component>` name to match the nearest ancestor).

## Code style

- **Use a formatter with Tailwind class sorting** (e.g. Oxfmt, Prettier with `prettier-plugin-tailwindcss`, or Biome) to auto-sort Tailwind classes.
- **Rely on default values.** Don't explicitly set every prop — omit props that match the default. Cleaner code that's easier to read.
- **Consistent prop order:** `key`, `ref`, `id` first → component-specific props → `aria-*`, `data-*` → `className` → `style` → `children` → `{...props}` spread.
- **Prefer TypeScript interfaces over types** for component props (e.g. `interface Props extends CardProps` over `type Props = CardProps & {}`).

## Reference

For detailed guidance on specific topics:

- [icons.md](references/icons.md) - Exhaustive icon list: Phosphor, interactive, dynamic, logo icons
- [patterns.md](references/patterns.md) - Common UI compositions and layouts
- [tokens.md](references/tokens.md) - Design tokens: semantic colors, font sizes, border radii, spacing
- [theme.css](https://github.com/graphprotocol/gds/blob/main/packages/css/styles/theme.css) - Complete theme definition (all design tokens)
- [typography.css](https://github.com/graphprotocol/gds/blob/main/packages/css/styles/typography.css) - Typography styles and scales
