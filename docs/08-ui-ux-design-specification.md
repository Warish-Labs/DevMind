# 08 · UI/UX Design Specification

**Purpose.** Specifies the visual identity, design system, motion language, homepage, website screens and the extension's UI so the interface can be built in Next.js without guessing. This is a **design specification only**; no components are implemented by this document.

**Status.** Implemented (Design Review Gate passed). Dark code-native UI, typography tokens, custom cursor, keyboard navigation, a11y focus rings, and public homepage sections are implemented and verified. Decisions: ADR-035, ADR-048.

---

## 1. Design goal in one paragraph

DevMind should look like a tool built by people who live in editors and pull requests, not like a template. The interface borrows the furniture of code itself (the line-number gutter, margin annotations, diff hunks, the blame column, the status bar) and uses it as the layout language. Color is information, not decoration. Nothing on the page exists unless it explains what DevMind does or helps the user act.

## 2. Anti-template rules (read before designing anything)

The most common failure of AI-generated interfaces is that they all look alike. These rules exist to prevent that. A screen that breaks more than two of them fails review.

| Do not | Do instead |
|---|---|
| Purple-to-blue gradient backgrounds, glowing orbs, mesh blobs | Flat near-black surfaces with 1px hairlines; one accent used sparingly |
| Centered headline + subtitle + two buttons + three icon cards | Asymmetric, editor-shaped hero built around a real artifact ([§8](#8-homepage-hero)) |
| Every surface a rounded, translucent, glowing card | Opaque panels, square-ish corners; glass in three places only ([§5.4](#54-glass-allowed-in-exactly-three-places)) |
| Inter/Roboto everywhere, one weight | Three deliberate families with distinct jobs ([§4](#4-typography)) |
| Sparkle/magic-wand "AI" iconography, robot mascots | Code-native marks: gutter ticks, carets, diff markers, symbol glyphs |
| Fake stats, invented logos, testimonials, "10x faster" claims | Only facts about the product; example data labeled as example |
| Feature grids of identical cards | Index tables, annotated diagrams, a pinned walkthrough |
| Unmodified shadcn/ui or component-kit defaults | Accessible primitives (for behavior) styled entirely from DevMind tokens |
| Neon on everything | Color budget: accents cover a small share of any screen ([§3.3](#33-color-budget)) |
| Decorative motion on loop | Motion that explains cause and effect, plays once, respects reduced motion |

Review checklist items derived from this table are in [§18](#18-design-review-gate).

## 3. Visual identity

### 3.1 Concept: "Gutter and margin"

- **Gutter:** a narrow, always-present left rail that carries section numbers, line numbers or step numbers depending on the page. It anchors navigation and gives every screen the same spine.
- **Margin notes:** findings, explanations and cross-references attach to content with hairline connectors, the way a reviewer annotates a diff.
- **Hunks:** grouped content uses diff-hunk headers (`@@ section @@`) in monospace as quiet section labels.
- **Status bar:** a thin strip at the bottom of the app shell reports live state (scan, job, sync mode), echoing the editor.

### 3.2 Color tokens

Starting values from the brief (`#0B0F12`, `#20E3A2`, `#4EA1FF`) are kept and refined. Contrast ratios below were computed with the WCAG relative-luminance formula for this document; recompute in tooling whenever a value changes.

| Token | Hex | Role | Contrast on `bg-0` / `bg-1` / `bg-2` |
|---|---|---|---|
| `--bg-0` | `#0B0F12` | Page | n/a |
| `--bg-1` | `#10151A` | Panels, sidebars | n/a |
| `--bg-2` | `#161C22` | Raised, inputs, code | n/a |
| `--line-1` | `#232B33` | Decorative hairlines | 1.34 / 1.28 / 1.20 (decorative only) |
| `--line-2` | `#2F3944` | Panel borders | 1.64 / 1.56 / 1.46 (decorative only) |
| `--line-3` | `#5F6C78` | **Control boundaries** (inputs, buttons, focus-adjacent) | 3.58 / 3.41 / 3.19 (meets 3:1) |
| `--fg-0` | `#E8E6E1` | Primary text (warm off-white, not pure white) | 15.43 / 14.72 / 13.76 |
| `--fg-1` | `#A9B0B6` | Secondary text | 8.77 / 8.37 / 7.83 |
| `--fg-2` | `#7C858D` | Tertiary text, metadata | 5.13 / 4.89 / 4.57 |
| `--signal` | `#20E3A2` | Active, verified, pass, progress | 11.52 / 10.99 / 10.28 |
| `--ref` | `#4EA1FF` | References, links, relations, focus ring | 7.21 / 6.87 / 6.43 |
| `--warn` | `#F0B44C` | Medium severity, caution | 10.39 / 9.91 / 9.27 |
| `--danger` | `#FF6B5E` | Critical/high severity, destructive | 6.89 / 6.57 / 6.14 |

Rules: text never uses `--line-*`; `--fg-2` is the lowest text tone allowed (all pairs ≥ 4.5:1); text on a filled `--signal` or `--ref` background uses `--bg-0` (11.52 and 7.21).

A light theme is `[DEFERRED]`. The tokens are defined as CSS variables so a second palette can be added without touching components.

### 3.3 Color budget

- Accent colors (`signal`, `ref`, `warn`, `danger`) together cover a small fraction of any screen; most pixels are `bg-*`, `line-*`, `fg-*`.
- `signal` means *good or active*: verified, passing, in-progress, current selection. It is not a brand fill.
- `ref` means *connection*: links, code references, relationships, focus.
- Severity colors appear only on severity and status elements, never on decoration.

### 3.4 Semantic encoding (never color alone)

| Meaning | Color | Glyph | Text label | Shape cue |
|---|---|---|---|---|
| Critical | `--danger` | solid diamond | "Critical" | filled chip |
| High | `--danger` | hollow diamond | "High" | outlined chip |
| Medium | `--warn` | triangle | "Medium" | outlined chip |
| Low | `--fg-1` | circle | "Low" | plain chip |
| Info | `--ref` | square | "Info" | plain chip |
| Passing / verified | `--signal` | check | "Pass" / "Verified" | filled |
| Failing / missing | `--danger` | cross | "Missing" | outlined |
| Not assessed | `--fg-2` | dash | "Not assessed" | dashed outline |

**Evidence level** (E0 to E3, [13](13-glossary-and-domain-terminology.md)) is shown as a four-segment bar (filled segments = level + 1 of 4) plus text, always together: `E1 · Possible`, `E2 · Verified (static)`. The UI never uses the word "vulnerable" for E0 or E1; it says "possible". E3 is reserved for a post-MVP capability.

## 4. Typography

Candidates; confirm licenses and self-host (OQ-16). Each family has one job.

| Role | Family (candidate) | Use |
|---|---|---|
| Display | Instrument Serif | Homepage headline, section titles, report titles. **Marketing and report headers only.** Italic used sparingly for one emphasized phrase |
| UI | IBM Plex Sans | Navigation, body, forms, tables |
| Code and metadata | JetBrains Mono | Code, file paths, symbol keys, rule IDs, evidence levels, counts, timestamps, diff hunk labels |

Fallback stacks are system fonts; load with `font-display: swap`; subset to Latin for the first release; self-host. Use tabular figures for all numeric columns.

| Style | Size / line height | Weight | Notes |
|---|---|---|---|
| Display XL | 56 / 60 (desktop), 36 / 40 (mobile) | 400 | Display family, tight tracking |
| Display L | 40 / 44 | 400 | Section titles |
| Title | 22 / 28 | 600 | UI family |
| Body | 15 / 24 | 400 | UI family |
| Small | 13 / 20 | 400 | Metadata |
| Code | 13 / 20 | 400 | Mono, ligatures off |
| Label (mono caps) | 11 / 16, letter-spacing 0.06em | 500 | Hunk labels, gutter captions |

## 5. Layout, surfaces and shape

### 5.1 Spacing and grid

Base unit 4 px. Scale: 4, 8, 12, 16, 24, 32, 48, 64, 96. App shell: 12-column grid on ≥1024 px, 4-column on mobile; content max width 1280 px; reading width for prose 68ch; the left gutter rail is 56 px (desktop) and collapses to a top bar on mobile.

### 5.2 Elevation

Depth comes from layering `bg-0 → bg-1 → bg-2` and hairlines, not drop shadows. Shadows are allowed only on overlays (dialogs, popovers) as a single soft shadow plus a 1px `--line-2` border.

### 5.3 Shape

Corner radius: 2 px for chips and table cells, 4 px for inputs and buttons, 6 px for panels and dialogs. No pills except status chips that are single-line. No fully rounded cards.

### 5.4 Glass allowed in exactly three places

1. Command palette overlay.
2. Floating job tray (when open over content).
3. Hover/peek cards that float over code.

Everywhere else surfaces are opaque. Rationale: translucency over text hurts legibility and `backdrop-filter` costs performance on low-end devices. `[OPEN]` whether to keep glass at all after the first usability review; the product works without it.

## 6. Component specifications

| Component | Specification |
|---|---|
| Buttons | Primary: `--signal` fill, `--bg-0` text, 4 px radius, no glow. Secondary: transparent, `--line-3` border. Tertiary: text with `--ref` underline on hover. Destructive: `--danger` outline, fill on confirm step only. Min target 44 × 44 px on touch, 32 px height on dense desktop (≥ 24 × 24 CSS px always) |
| Inputs | `--bg-2`, `--line-3` border, 4 px radius, visible label above (never placeholder-only), inline error text with glyph |
| Navigation | Left gutter rail with icon + number; project sub-navigation as a vertical list with active marker (a 2 px `--signal` bar); top bar holds workspace/project switcher and command palette trigger |
| Tables and findings lists | Dense rows (36 px), sticky header, mono for paths/IDs, severity glyph + text, evidence-level bar, status chip, keyboard row navigation, column sort, saved filters. No zebra stripes; hover = `bg-2` |
| Code snippets | `--bg-2`, gutter with line numbers in `--fg-2`, highlighted lines with a 2 px left bar in `--ref`, diagnostic squiggle under flagged ranges, copy button, horizontal scroll inside the block |
| Inline diagnostics | Underline style: wavy, color by severity, plus a margin glyph in the gutter (non-color cue) |
| Status indicators | Glyph + label + color ([§3.4](#34-semantic-encoding-never-color-alone)) |
| Tooltips | 160 ms delay, dismissible with Esc, shown on focus as well as hover, never the only place information lives |
| Dialogs | Focus trap, Esc to close, return focus to trigger, destructive actions require typing the project name |
| Toasts | Bottom-right (desktop) / bottom (mobile), polite live region, 6 s default, persistent for errors until dismissed, never the only record (events also appear in job center) |
| Progress | Determinate bar when total is known (files scanned/total); otherwise a labeled step list; never an indefinite spinner longer than 2 s without text |
| Skeleton loaders | Match final layout; static (no shimmer) under reduced motion; used when data is expected within about a second, otherwise show a progress step list |
| Charts | See [§14](#14-data-visualization-principles) |
| Chips/badges | 2 px radius, mono text for IDs, sentence case for labels |
| Empty states | One sentence of what belongs here, one primary action, optional link to docs; no illustrations |
| Hunk header | `@@ Findings · 12 open @@` style label above grouped content, mono caps, `--fg-2` |

Implementation note: use accessible unstyled primitives for dialogs, menus, popovers, tabs and tooltips (for example Radix UI primitives `[VERIFY: choose at implementation]`) and style them only from tokens. Do not ship a component kit's default look.

## 7. Motion language

Principle: **motion explains cause and effect or gives feedback; it never decorates and never blocks.** Only `transform` and `opacity` are animated (plus `clip-path` for the hero connectors). Nothing animates layout properties.

### 7.1 Tokens

| Token | Value | Use |
|---|---|---|
| `--dur-1` | 90 ms | Hover, press, toggle |
| `--dur-2` | 160 ms | Menus, tooltips, chip changes |
| `--dur-3` | 240 ms | Panels, dialogs, drawers, toasts |
| `--dur-4` | 400 ms | Section reveals on the homepage |
| `--dur-story` | 600–1200 ms | Hero sequence and homepage walkthrough only |
| `--ease-out` | `cubic-bezier(0.2, 0, 0, 1)` | Entrances |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Exits |
| `--ease-move` | `cubic-bezier(0.4, 0, 0.2, 1)` | Repositioning |

No bounce or overshoot. Exits are faster than entrances (about 70%).

### 7.2 Behaviors

| Moment | Behavior |
|---|---|
| Hero entrance | Scripted once, about 7 s total, final frame static ([§8.3](#83-hero-sequence)) |
| Agent activity | In the conversation, an "activity" line per agent step (`Searching Brain`, `Checking guards`) appears with a 90 ms fade; the active step has a 2 px `--signal` caret; completed steps get a check. No pulsing |
| Scan progress | Determinate bar advances by data; file counts are mono and tabular so digits do not jitter |
| Scan completion | Bar settles to `--signal`, label changes to "Scan complete", one 240 ms highlight on the summary; no confetti |
| New finding | Row inserts with a 240 ms height-neutral fade (reserve space; no layout shift) and a 2 px left marker that fades after 4 s; an `aria-live="polite"` announcement |
| Warning/critical | Glyph + text only; no shaking or flashing |
| Dashboard update | Changed numbers cross-fade 160 ms; unchanged content does not animate |
| Card/row hover and focus | Background step `bg-1 → bg-2` in `--dur-1`; focus ring appears instantly (no animation) |
| Menus, dialogs, tooltips | Fade + 4 px translate, `--dur-2` / `--dur-3` |
| Page transitions | None between app routes (instant, with skeletons). Homepage in-page scroll only |
| Section reveals (homepage) | Content is visible by default; a 400 ms fade/translate (8 px) applies once when a section enters the viewport, and only if JavaScript is available and reduced motion is off |
| Interactive diagrams | State changes (select a stratum, hover a tag) cross-fade 160 ms; connectors draw with `stroke-dashoffset` over 400 ms |

### 7.3 Reduced motion and performance

- `prefers-reduced-motion: reduce` removes all transitions longer than 90 ms, shows hero and walkthrough final states immediately, replaces drawing connectors with static lines, and disables scroll-linked effects. A visible in-app toggle mirrors the OS setting.
- No scroll-jacking. The pinned walkthrough uses `position: sticky` and normal scrolling; users can click steps to jump.
- Budgets (targets to measure, not promises): animations run on the compositor; no more than a handful of simultaneous animated elements; total hero script small and loaded after first paint; Core Web Vitals "good" thresholds (LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1) are the targets; verify with lab and field data during [11](11-mvp-and-implementation-roadmap.md) M10 and M13.
- Mobile: hero shortens to three steps, no `backdrop-filter`, no scroll-linked animation.

## 8. Homepage hero

**Goal.** Within a few seconds a developer understands what DevMind does and sees it done on real-looking code. The hero is built around one artifact: **the Trace**.

### 8.1 Message

| Element | Specification |
|---|---|
| Headline (recommended) | **Know what your code actually allows.** |
| Supporting line | DevMind keeps one evidence-backed model of your project (code, security, bugs, docs, reviews, deploys) and shows its work down to the line. |
| Primary CTA | **Open DevMind** (sign in, then create a project) |
| Secondary CTA | **See how a finding is made** (scrolls to the walkthrough, [§9](#9-homepage-sections)) |
| Tertiary link | "VS Code extension" appears as a link only once published; before that it reads "Extension in development" without a link |
| Alternates (copy test needed, `[OPEN]`) | "Logged in is not the same as allowed." · "One shared understanding of your project, with receipts." |

Headline rationale: it is concrete (authorization), it comes from the product's own thesis ("authentication is not authorization"), and it leads into the hero artifact. Whether it undersells the other capabilities is decided in the copy test.

### 8.2 Composition (desktop, ≥1024 px)

Asymmetric two-zone layout aligned to the gutter rail:

- **Left (about 5/12):** eyebrow label in mono (`@@ DevMind @@`), headline (Display XL), supporting line, CTAs, and below them a one-line **status strip** in mono: `local-first · nothing leaves your machine without consent preview`. This is a true statement of design (ADR-021), not a metric.
- **Right (about 7/12), bleeding off the right edge:** the **Trace**, an editor pane (`--bg-2`, hairline border, square corners) showing real, selectable text:

```
 1  import { Router } from "express";
 2  import { requireAuth } from "../auth";
 3  import { listUsers, deleteUser } from "./users";
 4
 5  const router = Router();
 6
 7  router.get("/admin/users", requireAuth, listUsers);
 8  router.delete("/admin/users/:id", requireAuth, requireRole("admin"), deleteUser);
```

Line 7 is the subject. The example is intentionally small, fictional and labeled `example` in a corner tab; it mirrors the source vision's `/admin/users` illustration.

- **Margin note** (attached to line 7 by a hairline connector, set in the right margin of the pane):

```
@@ /admin/users @@
Authentication   ✓ required     requireAuth · auth.ts:12
Authorization    ✗ missing      no role check on route or handler
Evidence         ▮▮▯▯  E1 · Possible        rule devmind.authz.missing_role_check
```

- **Ripple tags:** three small tags hang from the note on thin connectors: `Review · add finding`, `Docs · no entry for /admin/users`, `Pull request · risk: high`. They show the shared-Brain idea (one finding, several consumers) without a diagram lecture.

Below the Trace, the page continues into [§9 section 2](#9-homepage-sections) with the gutter numbering continuing seamlessly (line 9, 10, … become the next section's line numbers), so the hero flows into the page instead of ending in a hard edge.

### 8.3 Hero sequence

Plays once on load (about 7 s), starts after first paint, and never loops.

| t | Step | Purpose |
|---|---|---|
| 0.0 s | Gutter and code lines fade in line by line (40 ms stagger) | Establishes "this is code" |
| 1.2 s | A 2 px `--signal` scan line travels down the gutter, 600 ms | Shows scanning |
| 2.2 s | Wavy underline appears under `requireAuth, listUsers` on line 7; gutter glyph appears | Local diagnostic ("Possible") |
| 3.2 s | Margin note draws in; evidence bar fills to E1 | Finding with evidence |
| 4.4 s | Evidence bar advances to E2 `Verified (static)` only if the structural check step is part of the demo copy | Shows E1 to E2 distinction; optional, `[OPEN]` |
| 5.0 s | Connectors draw to the three ripple tags, 400 ms each, staggered 120 ms | Shared Brain |
| 7.0 s | Idle. Final state remains fully readable and interactive | |

Interactions after the sequence: hovering or focusing a ripple tag highlights the related text in the note and shows a one-sentence peek card (glass allowed here); `Tab` reaches each tag; `Esc` dismisses. A "Replay" text button restarts the sequence. With reduced motion the final frame renders immediately and Replay is hidden.

### 8.4 Responsive behavior

| Breakpoint | Behavior |
|---|---|
| ≥1280 | As specified |
| 1024–1279 | Trace narrows; ripple tags stack under the note |
| 768–1023 (tablet) | Single column: text, then Trace; margin note moves **below** the highlighted line as an inline annotation |
| <768 (mobile) | Headline 36/40; CTAs stack; Trace code scrolls horizontally inside its own container; three-step sequence (code, diagnostic, note); ripple tags become a vertical list |

### 8.5 Implementation constraints (Next.js)

- Static rendering; the Trace is semantic HTML and SVG with real text (screen readers read it as a code region with an accessible description).
- The sequence is a small client component using the Web Animations API or CSS transitions toggled by a data attribute; no canvas, no WebGL, no video.
- The page works with JavaScript disabled (final state shown).
- Content (code, note text) lives in a typed constant so the hero cannot drift from real rule names; the rule ID and message must exist in the scanner rule catalog ([06](06-vscode-extension-and-local-scanning.md) §8), enforced by a test.

## 9. Homepage sections

The sections run as one continuous argument down the gutter. Each has a purpose; none repeats the hero's job.

| # | Section | Purpose | Content and form | Interaction |
|---|---|---|---|---|
| 1 | Hero: the Trace | State what DevMind does, show it | [§8](#8-homepage-hero) | Described above |
| 2 | **One change, many consequences** | Make the problem concrete: connected problems, separate tools | A single diff hunk on the left (adding the `/admin/users` route); a vertical list of consequences on the right (security, review, documentation, PR blast radius, project health) each with one sentence from the source vision | Hover a consequence to highlight the affected lines. Static otherwise |
| 3 | **The Project Brain** | Explain the central idea | A layered cross-section (SVG) of the ten concepts in [04](04-project-brain-and-rag.md) §2: local manifest, cloud project model, code index, embeddings, relationships, bug history, agent state, findings and evidence, documentation and history, snapshots. Left labels, right "where it lives". A highlighted path traces how the hero finding touches four layers | Select a stratum to see its definition and example; keyboard accessible |
| 4 | **Nine capabilities, one question each** | Map questions to capabilities honestly | An index table (not cards): question a developer asks (from vision section 1), capability, and release status (`MVP`, `1.1` and so on) | Row expands to a short example output (one real shape from the vision, labeled example) |
| 5 | **Follow one feature** | Show the lifecycle end to end | Pinned, scroll-driven timeline of the 14 steps of the vision's walkthrough. Left: step list on the gutter; right: the Brain state and the active agent. Steps for capabilities not yet released are marked `planned` | Click a step to jump; normal scrolling; no scroll hijack |
| 6 | **Local first** | Explain extension and website relationship | Diptych: an editor panel (diagnostics, status bar) and a browser panel (conversation, report), with a labeled "Review what will be sent" preview between them reflecting [06](06-vscode-extension-and-local-scanning.md) §12 | Toggle `metadata_only` / `indexed` to see which rows in the preview change |
| 7 | **Privacy ledger** | Make privacy auditable | A table: data category vs stays local / stored in DevMind / embedded / may reach an LLM provider, per sync mode. **Rendered from the same data source as [06](06-vscode-extension-and-local-scanning.md) §11.1**, with a test that fails if they diverge | Mode toggle; link to the security document |
| 8 | Call to action and footer | Convert | Short statement, **Open DevMind**, link to documentation; footer with product, docs, security, privacy and status links | None |

Rules: no testimonials, no customer logos, no benchmark numbers, no "trusted by". Example data is labeled `example`. Release labels (`MVP`, `1.1`) must be generated from a single status file so the page cannot claim an unshipped capability as available.

## 10. Website information architecture

```mermaid
flowchart TB
  Home[Public homepage] --> SignIn[Sign in / sign up]
  SignIn --> Onb[Onboarding]
  Onb --> WS[Workspace and project selector]
  WS --> Proj[Project]
  Proj --> Ov[Overview]
  Proj --> Brain[Project Brain]
  Proj --> Chat[Conversation]
  Proj --> Find[Findings]
  Proj --> Jobs[Job center]
  Proj --> Set[Project settings]
  Proj -.1.1.-> PR[Pull requests and change impact]
  Proj -.1.2.-> Bugs[Bug history]
  Proj -.1.2.-> Docs[Documentation analysis]
  Proj -.1.3.-> Health[Health and release readiness]
  Proj -.1.3.-> Tasks[Next-task recommendations]
  Proj -.1.4.-> Deploy[Deployment diagnosis]
  WS --> WSset[Workspace settings: members, usage, audit, integrations]
  WS --> Acct[Account and privacy: extension devices, data]
```

App shell: left gutter rail (workspace/project switcher at top, project sections, account at bottom), top bar (breadcrumb, command palette, job tray), bottom status bar (scan, job, sync mode).

## 11. Screen specifications (MVP)

Common to all: loading uses skeletons that match layout; errors use the problem `title` and `detail` from the API with `request_id` copyable; every list is paginated by cursor ([03](03-data-model-and-api.md) §10).

### S-02 Authentication and onboarding

| | |
|---|---|
| Purpose | Sign in, create/choose a workspace, connect the first project |
| Layout | Clerk components themed with tokens; a 3-step onboarding rail in the gutter: workspace, project source (extension or GitHub when available), consent |
| Primary actions | Create project; "Connect VS Code extension" (opens the extension flow, [06](06-vscode-extension-and-local-scanning.md) §3); choose sync mode with plain-language explanation |
| Data | `GET /me`, `POST /workspaces/{wid}/projects`, `PATCH /projects/{pid}/sync-mode`, `POST /projects/{pid}/consents` |
| Empty | First-run: single next step visible |
| Error | Auth failure returns to sign-in; project-creation validation inline |
| Responsive | Single column; steps become a top progress list |

### S-03 Workspace and project selection

Purpose: switch context. Layout: switcher popover plus a project index (table: name, source, sync mode, last scan, open findings by severity). Actions: new project, open. Empty: "Create your first project". Responsive: table becomes stacked rows.

### S-04 Project overview (answers five questions)

| Question (vision section 7) | MVP content |
|---|---|
| What is happening? | Recent scans and jobs with status; last sync; sync mode |
| What is broken? | Open findings by severity; bug counts when Bug Memory ships (1.2) |
| What is risky? | Top findings with evidence level and file reference |
| What should I do next? | "Highest-priority finding to fix", derived by deterministic ordering (severity, then evidence level) and labeled *rule-based until Project Mentor ships (1.3)* |
| Is the project healthy? | **Security** score and **analysis coverage** (files analyzed at which language tier) from real data; other categories shown as `Not assessed` |

Layout: coverage and health strip on top (numbers in mono), two columns (findings, activity), full-width next-action band. Loading: skeleton per panel. Error: per-panel error with retry; panels fail independently. Responsive: panels stack, next-action band first.

### S-05 Project Brain explorer

Purpose: let users see what DevMind knows (FR-BRN-06). Layout: three panes, file tree (left), file/symbol detail with code (center), relationships and findings for the selection (right); a snapshot selector in the header with "current" clearly marked and stale items badged. Actions: search (`POST /brain/search`), open symbol, expand relationships (`GET /brain/graph`), open finding. States: `metadata_only` projects show structure and symbols but **no source text**, with a clear banner and an "Enable indexed mode" action requiring consent; unindexed files show tier and reason. Responsive: panes become tabs.

### S-06 AI project conversation

Purpose: ask the project (CAP-01 and, when relevant, CAP-02). Layout: message column (center), citations panel (right, collapsible), composer bottom. Each answer streams; agent activity lines appear above the answer; citations render as numbered references that open the cited lines in the panel; an **insufficient evidence** answer has a distinct style with suggested next steps. Actions: ask, retry, copy, open citation, stop (cancels job). Data: `POST /conversations/{id}/messages`, SSE `GET /jobs/{id}/events`. States: no indexed context (explains how to enable), quota exceeded (shows usage link), provider unavailable (reason and retry). Responsive: citations panel becomes a bottom sheet.

### S-07 Findings list

Dense table ([§6](#6-component-specifications)); filters: status, severity, category, evidence level, file; saved views; row actions: acknowledge, in progress; dismiss and accept-risk require a reason (maintainer permission; button disabled with explanation otherwise). Empty: distinguishes "no findings" from "not analyzed" (shows coverage). Responsive: rows collapse to two-line items.

### S-08 Finding detail

Purpose: evidence-first explanation. Layout hierarchy: title and status; severity/confidence/evidence-level strip; **what** and **where** (code excerpt with highlighted lines, resolvable to the snapshot); **why it matters**; **evidence** (each evidence item with its source: rule hit, structural check, retrieved context); **suggested remediation** (proposal only; "Review and apply yourself", no auto-apply); status history; related findings. Actions: transitions per [03](03-data-model-and-api.md) §5.1. A stale finding shows a banner and a "Re-verify" action.

### S-09 Job center

List and detail of jobs (type, status, attempt, timestamps, error code); live progress via SSE with polling fallback; cancel; approval prompts when status is `awaiting_approval` (the approval card states exactly what will happen). A floating tray summarizes running jobs from any page.

### S-10 Project settings

Sections: general; **sync mode and consent** (current mode, active consents with provider and data category, revoke); retention; members (1.1); integrations (1.1); danger zone (data deletion with typed confirmation; shows per-store deletion result afterward). Every change that affects data flow shows a plain-language before/after.

### S-11 Account and privacy

Extension devices (list, last seen, revoke), data export/deletion requests, session info.

### S-12 Workspace usage and quotas

Usage by project, job type and task (counts and token totals, no content), quota bars with thresholds, link to audit events (workspace admins).

## 12. Conceptual screens (post-MVP)

| Screen | Release | Notes |
|---|---|---|
| PR list and PR analysis (summary, impact graph, risks) | 1.1 | Impact shown as an annotated relationship diagram plus a table of affected modules |
| Review and change-impact view | 1.1 | Checklist matrix per route (validation, error handling, authorization, tests, docs) |
| Members and integrations | 1.1 | Invitations, GitHub connection and permissions shown explicitly |
| Bug history and similarity | 1.2 | Records with cause/fix/files; match view shows why two bugs are similar |
| Documentation analysis | 1.2 | Drift items showing code reference beside doc reference |
| Health and release readiness | 1.3 | Category scores with inputs displayed; verdict with blockers listed |
| Next-task recommendations | 1.3 | Ranked list with dependency explanation |
| Deployment diagnosis | 1.4 | Log input (redaction preview), ranked causes with cited log lines |
| Audit log viewer | 1.1 | Filter by actor/action/time |

## 13. VS Code extension UI

The extension inherits the user's VS Code theme. Brand appears only in the activity-bar icon, the status-bar item, and webview panels.

| Surface | Specification |
|---|---|
| Activity bar container "DevMind" | Views from [06](06-vscode-extension-and-local-scanning.md) §9: Findings, Project structure, Database (from files), Sync, Scan. Use VS Code codicons and theme colors; severity uses the platform's error/warning/info conventions |
| Diagnostics | Source `DevMind`; E1 findings prefixed `Possible:`; code links to the web finding when synced |
| Status bar | `idle`, `scanning`, `offline`, `sync paused`, `sign-in required`, with text, not color alone |
| Consent preview webview | Uses DevMind tokens inside a webview: a table of exactly what will be sent (files, ranges, byte counts, redactions with types), provider name, purpose, and **Send** / **Cancel**. Default focus on **Cancel**. Redacted values are never rendered in clear |
| Deep links | "Open in DevMind" actions on findings and projects |

No chat UI in the extension (FR-EXT-11).

## 14. Data visualization principles

- Prefer tables and small multiples over decorative charts; use a chart only when shape matters (trend over scans, coverage by language tier, severity distribution).
- Every chart has a text equivalent (table or summary) and an accessible name; color encodes meaning from [§3.4](#34-semantic-encoding-never-color-alone) and never carries meaning alone (patterns or direct labels).
- Axes start at zero for bars; no 3D; no gradients in data marks; direct labels over legends.
- Scores always display their inputs on demand; `Not assessed` renders as a dashed empty bar, never as zero.
- Relationship graphs: limited depth (default 2), node labels in mono, edge kinds distinguished by line style and label (`calls`, `guarded_by`, `defines_route`), keyboard-navigable list alternative.
- Numbers are mono and tabular.

## 15. Voice and content rules

Plain, direct, specific. Say "possible" until a finding is E2. Say what DevMind did and what it could not do ("12 of 40 files analyzed at tier 1"). No exclamation marks, no "supercharge/unlock/revolutionize", no anthropomorphic claims ("I think"); agent steps are described by action ("Checked route guards in 6 files"). Error messages state cause, effect and next step, and include the `request_id`.

## 16. Accessibility and responsiveness

Target: **WCAG 2.2 AA** (NFR-ACC-01). Conformance is claimed only after audit.

| Area | Requirement |
|---|---|
| Keyboard | Every function reachable and operable by keyboard; logical focus order; skip-to-content link; command palette (`Ctrl/Cmd+K`); row navigation in tables with arrow keys; shortcuts are discoverable and can be disabled |
| Focus | 2 px `--ref` ring with 2 px offset, always visible, not clipped or hidden by sticky headers (WCAG 2.2 focus appearance/not obscured) |
| Contrast | Text ≥ 4.5:1 (large ≥ 3:1); control boundaries and focus ≥ 3:1 (`--line-3`); verified in CI with a token contrast test |
| Names and labels | Every control has an accessible name; icon-only buttons have labels; form fields have programmatic labels and described-by errors; code regions have names ("Code excerpt, auth.ts lines 5 to 8") |
| Screen readers | Semantic landmarks; real tables with headers; job progress and new findings announced via polite live regions with throttling; streamed answers announce completion, not each token; the hero Trace has a text description |
| Non-color cues | Severity, status, evidence level and pass/fail always include glyph/shape and text |
| Motion | [§7.3](#73-reduced-motion-and-performance) |
| Targets | At least 24 × 24 CSS px everywhere (WCAG 2.2), 44 × 44 px for touch layouts |
| Drag and gestures | No function requires dragging; single-pointer alternatives exist |
| Zoom and reflow | Usable at 200% zoom and 320 px width without two-dimensional scrolling except inside code, tables and diagrams, which scroll within their own containers |
| Breakpoints | 640 / 768 / 1024 / 1280 px; mobile-first CSS |
| Density | Compact and comfortable density options for tables; default comfortable |
| Time | No auto-dismissing content that carries required information; toasts for errors persist |

## 17. Implementation notes for Next.js

| Topic | Guidance |
|---|---|
| Rendering | Per ADR-003: homepage static; authenticated shell with Server Components; live surfaces as client components with TanStack Query; SSE for streams |
| Tokens | CSS variables in a single `tokens.css`; Tailwind theme extended to read them; no hard-coded hex in components (lint rule) |
| Components | Behavior from accessible primitives; visuals from tokens; each component has a keyboard and a11y test ([09](09-testing-and-quality-strategy.md) §5) |
| Fonts | Self-hosted, subset, preloaded for the display and UI faces; mono loaded lazily |
| Images | None required for the homepage; inline SVG for diagrams |
| Content sources | Release status, hero code/rule IDs and the privacy ledger are generated from typed single sources of truth |
| Types | Generated API client ([02](02-system-architecture.md) §6); no hand-written API types |
| Visual regression | Snapshot the hero final frame, a findings table, a finding detail and an empty state at three breakpoints ([09](09-testing-and-quality-strategy.md) §5) |
| Prototype first | `[RECOMMENDED]` Produce high-fidelity frames of the hero, the Brain cross-section and the finding detail (for example in Figma) and review against §18 before building |

## 18. Design review gate

A screen is accepted only if:

1. It passes the anti-template table in [§2](#2-anti-template-rules-read-before-designing-anything) (no more than zero hard violations: gradients/orbs, fake metrics, identical card grids).
2. **Remove-the-logo test:** with the logo hidden, the screen is still recognizably DevMind (gutter, hunk labels, mono metadata, restrained accents).
3. **Squint test:** the primary action and the most important data are the two strongest elements.
4. Accent colors occupy a small share of the screen and each use has the meaning in [§3.3](#33-color-budget).
5. Every status uses glyph + text + color.
6. Keyboard-only pass and a screen-reader spot check are recorded.
7. Reduced-motion render is checked.
8. No claim on the page is unverifiable from the repository (metrics, availability, security guarantees).

Open design questions: glass retention (§5.4), hero E1 to E2 step (§8.3), headline copy test (§8.1), font licensing (OQ-16).

## 19. Brand identity and logo

**Status.** Proposed; assets are in [`brand/`](../brand/BRAND-GUIDE.md). Review against [§18](#18-design-review-gate) before freezing. No trademark search has been done.

| Item | Specification |
|---|---|
| Concept | A **D containing an M**: Dev holding Mind. The D's stem is the line-number gutter ([§3.1](#31-concept-gutter-and-margin)); the M is a graph of connected nodes (the Project Brain); the centre node is the evidence, repeated as the dot of the *i* in the wordmark |
| Colors | D `--fg-0` (`#E8E6E1`), M `--ref` (`#4EA1FF`), node `--signal` (`#20E3A2`) on dark; deeper `#1863C4` and `#087F59` on light so contrast holds (5.8:1 and 5.01:1 on white) |
| Wordmark | IBM Plex Sans SemiBold, outlined in the SVGs; never retyped |
| Versions | Mark, horizontal and stacked lockups, app icon, favicon mark (16 to 48 px, simplified), mono, animated mark |
| Use in the app shell | Mark in the gutter rail ([§6](#6-component-specifications)); horizontal lockup in the top-left of the public header; favicon mark in the browser tab |
| Motion | The animated mark plays once (about 1.4 s) and respects reduced motion; no looping logo |
| Tokens | `brand/tokens/devmind-tokens.css` is the source for `client/app/tokens.css`; values equal [§3.2](#32-color-tokens) |
| Social and extension | Open Graph image mirrors the hero Trace; the VS Code icon is a 128 px PNG and the activity-bar icon is monochrome SVG that follows the theme ([§13](#13-vs-code-extension-ui)) |
| Rules | No gradients, glows or shadows on the logo; clear space is a quarter of the mark's height; minimum mark size 24 px |
