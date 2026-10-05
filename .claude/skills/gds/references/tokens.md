# GDS Tokens

Memorize these tokens before any UI work. **Built-in Tailwind tokens do not exist** — GDS overrides them entirely. If a utility isn't listed here, verify it exists in the app's theme customizations (search for `@theme`) before using it.

## Semantic Color Tokens (Preferred)

Always use semantic tokens over raw color scales. They adapt to light/dark mode automatically.

### Text Colors

| Utility          | Use For                      |
| ---------------- | ---------------------------- |
| `text-default`   | Primary text                 |
| `text-muted`     | Secondary text               |
| `text-subtle`    | Tertiary / disabled text     |
| `text-elevated`  | Slightly emphasized text     |
| `text-strong`    | Strongly emphasized text     |
| `text-inverse-*` | Text on inverted backgrounds |
| `text-link-idle` | Link default color           |
| `text-code`      | Inline code text             |

`text-inverse-*` scale: `default`, `muted`, `subtle`, `elevated`, `strong`.

### Background Colors

| Utility        | Use For                      |
| -------------- | ---------------------------- |
| `bg-canvas`    | Page background              |
| `bg-subtle`    | Slightly elevated (sections) |
| `bg-muted`     | Cards, inputs                |
| `bg-default`   | Active/selected state        |
| `bg-elevated`  | Hover states                 |
| `bg-strong`    | Strongly emphasized          |
| `bg-brand-*`   | Brand purple                 |
| `bg-inverse-*` | Inverted backgrounds         |
| `bg-code`      | Inline code background       |
| `bg-backdrop`  | Modal/overlay backdrop       |

`bg-brand-*` scale: `subtlest`, `subtler`, `subtle`, `muted`, `default`, `elevated`, `strong`.
`bg-inverse-*` scale: `canvas`, `subtle`, `muted`, `default`, `elevated`, `strong`.

### Border Colors

| Utility           | Use For                                    |
| ----------------- | ------------------------------------------ |
| `border-focus`    | Focus rings (brand purple)                 |
| `border-subtle`   | Faint borders                              |
| `border-muted`    | Standard borders                           |
| `border-default`  | Emphasized borders                         |
| `border-elevated` | Strong borders                             |
| `border-strong`   | Maximum emphasis borders                   |
| `border-brand-*`  | Brand borders (same scale as `bg-brand-*`) |

### Status Colors

Available as `text-status-*`, `bg-status-*`, `border-status-*`:

| Status    | Color             | Use For              |
| --------- | ----------------- | -------------------- |
| `info`    | Blue (galactic)   | Informational states |
| `warning` | Yellow (solar)    | Warning states       |
| `error`   | Red (sonja)       | Error/danger states  |
| `success` | Green (starfield) | Success states       |

Each has intensities: `subtle`, `muted`, `default`, `elevated`, `strong`.

Example: `bg-status-success-subtle`, `text-status-error-default`, `border-status-warning-muted`.

## Raw Color Scales

Use sparingly — only for custom illustrations, brand treatments, or cases where semantic tokens don't apply. **These do NOT adapt to light/dark mode.**

| Scale       | Purpose                  | Range    |
| ----------- | ------------------------ | -------- |
| `space`     | Dark grays               | 100–1800 |
| `foam`      | Light grays              | 100–1000 |
| `brand`     | Purple (primary brand)   | 100–1200 |
| `galactic`  | Blue (info, links)       | 100–1100 |
| `starfield` | Green (success)          | 100–1100 |
| `solar`     | Yellow/orange (warning)  | 100–1100 |
| `sonja`     | Red/pink (error, danger) | 100–1100 |

```tsx
<div className="bg-brand-500">Brand purple (fixed, won't adapt to theme)</div>
```

## Typography

### Font Sizes

Standard Tailwind sizes (`text-sm`, `text-lg`, `text-base`) **do not exist**. Use numeric pixel values:

| Utility    | Size  | Use For                           |
| ---------- | ----- | --------------------------------- |
| `text-10`  | 10px  | Captions, fine print (rare)       |
| `text-12`  | 12px  | Small text, labels                |
| `text-14`  | 14px  | **Body text (product UI)**        |
| `text-16`  | 16px  | Body text (marketing)             |
| `text-18`  | 18px  | Large body text or small headings |
| `text-20`  | 20px  | Headings                          |
| `text-24`  | 24px  | Large headings                    |
| `text-32`  | 32px  | Extra large headings              |
| `text-40`  | 40px  | Huge headings                     |
| `text-48`  | 48px  | Display text (marketing)          |
| `text-56`  | 56px  | Large display text                |
| `text-64`  | 64px  | Extra large display text          |
| `text-96`  | 96px  | Huge display text (rare)          |
| `text-128` | 128px | Maximum display text (very rare)  |

### Font Weights

| Utility         | Weight | Use For                                               |
| --------------- | ------ | ----------------------------------------------------- |
| `font-light`    | 300    | Rarely used                                           |
| `font-regular`  | 400    | **Default** — almost never needs to be set (inherits) |
| `font-medium`   | 500    | Headings and deliberate emphasis                      |
| `font-semibold` | 600    | Only when user explicitly requests                    |
| `font-bold`     | 700    | Only when user explicitly requests                    |

LLMs over-use bold weights. Default to `font-regular`. Use `font-medium` for headings. Only use `font-semibold` or `font-bold` after the user confirms `font-medium` is not bold enough.

### Special Typography Utilities

- `text-caption` — applies `uppercase` + `tracking-caption` (0.15em letter spacing). Use for small annotations and labels (e.g. "STATUS", "CATEGORY"), not section headings.
- `prose` — applies sensible typographic defaults (heading sizes, paragraph spacing, list styles, etc.) to rich/formatted content. Preferred for static HTML/JSX that just needs pretty typography. For dynamic markdown that needs code blocks, links, etc. transformed into GDS components (`CodeBlock`, `CodeInline`, `Link`), use the `Prose` component instead.

## Border Radius

Standard Tailwind radius utilities (`rounded-sm`, `rounded-md`, `rounded-lg`) **do not exist**. Use numeric pixel values:

| Utility           | Size                |
| ----------------- | ------------------- |
| `rounded-none`    | 0px                 |
| `rounded-2`       | 2px                 |
| `rounded-4`       | 4px                 |
| `rounded-6`       | 6px                 |
| `rounded-8`       | 8px                 |
| `rounded-10`      | 10px                |
| `rounded-12`      | 12px                |
| `rounded-16`      | 16px                |
| `rounded-full`    | Pill/circle         |
| `rounded-inherit` | Inherit from parent |

## Spacing

Standard Tailwind spacing works (4px grid). GDS does **not** override spacing tokens.

| Context               | Recommended         |
| --------------------- | ------------------- |
| Between sections      | `gap-8` to `gap-12` |
| Inside sections       | `p-4` to `p-6`      |
| Between related items | `gap-4` to `gap-6`  |
| Tight lists           | `gap-2` to `gap-3`  |

When in doubt, add more space. Dense UIs look cheap.

## Theme Classes

| Class        | Effect                                                     |
| ------------ | ---------------------------------------------------------- |
| `gds-dark`   | Forces dark color scheme for this element and descendants  |
| `gds-light`  | Forces light color scheme for this element and descendants |
| `gds-system` | Follows the OS color scheme preference                     |

These can be applied to any element to create nested theme regions. The `GDSProvider` `theme` prop sets the root theme; these classes override it locally.

## Breakpoints

GDS adds two smaller breakpoints below Tailwind's defaults:

| Prefix | Min-width | Use For                            |
| ------ | --------- | ---------------------------------- |
| `2xs:` | 384px     | Smallest phones (e.g. iPhone mini) |
| `xs:`  | 512px     | Phones in portrait mode            |
| `sm:`  | 640px     | (Tailwind default)                 |
| `md:`  | 768px     | (Tailwind default)                 |
| `lg:`  | 1024px    | (Tailwind default)                 |
| `xl:`  | 1280px    | (Tailwind default)                 |
| `2xl:` | 1536px    | (Tailwind default)                 |

All also work as `max-*` variants (e.g. `max-xs:`, `max-2xs:`).

## Token Verification

When encountering any utility that uses an unrecognized token (e.g. `bg-brand` instead of `bg-brand-default`), verify it exists in the app's theme customizations. If it doesn't exist, **remove it** — it will have no effect and silently fail.

Avoid arbitrary values (e.g. `w-[347px]`, `text-[#ff0000]`) unless explicitly requested by the user. Use design tokens instead.
