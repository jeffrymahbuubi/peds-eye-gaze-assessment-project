# What "AI-ish" UI means, and design systems that fit this app

Research of 2026-10-07 (parallel web search). Sources are cited inline. This file records findings
only; it makes no design decision. Fable proposes a direction (`fable-brief.md`).

## 1. "AI-ish" (AI slop) — a working definition

Designers call it **AI slop** or **distributional convergence**: an AI tool picks the
statistically most common pattern in its training data, so every product converges on the same
look, and the design says nothing about the product, its users or its context
([925studios 2026](https://www.925studios.co/blog/ai-slop-web-design-guide);
[GlowUp UI](https://glowupui.io/blog/generate-beautiful-ui-vibe-coded-projects)).
Adrian Krebs scored 1,590 Show HN pages against 16 patterns: 22 % had 4 or more (heavy), 32 % had
2-3 (mild) ([developersdigest](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it)).
A Reddit-mined study (3.2 M posts) ranked the tells people actually name
([vibecoded-design-tells](https://github.com/JCarterJohnson/vibecoded-design-tells)).

### The tells

| # | Tell | Why the model does it |
|---|---|---|
| T1 | Inter / system font everywhere; no type scale (sizes chosen ad hoc) | Tailwind/shadcn defaults dominate training data |
| T2 | Purple-blue (or teal) **gradients** on buttons, headings, backgrounds | Most common gradient in tech marketing |
| T3 | **Cards on cards**: every section boxed, one radius (8-16 px) and one padding everywhere | Card grids are the default "dashboard" pattern |
| T4 | Identical feature cards: icon + heading + two lines, in a row | Template landing pages |
| T5 | **Colored left border** (3-4 px stripe) on callouts/banners — "as reliable a sign as em-dashes are for AI text" | Blockquote/alert defaults |
| T6 | Pastel tint for every state (soft blue info, soft amber warning, soft green success), little contrast | Component-library alert variants |
| T7 | Glow, soft shadows, glassmorphism, radial "aurora" backgrounds | "Premium dark mode" examples |
| T8 | Emoji or generic line icons as the only iconography | Chat/marketing copy habits |
| T9 | All-caps small section labels; centered hero + badge above the title | Landing-page templates |
| T10 | Bounce/hover animation on everything; no motion with a purpose | Demo-site polish |
| T11 | Layout that ignores the real workflow (generic dashboard shell, equal-weight everything, no visual anchor per screen) | No product knowledge, so no hierarchy |

Fix direction named by every source: make **deliberate** choices (type scale, palette with
meaning, spacing system, a single visual anchor per screen, motion only where it earns its place)
instead of accepting defaults
([Fountain Institute](https://pages.thefountaininstitute.com/posts/7-tells-that-a-ui-is-ai-generated);
[SmoothUI](https://smoothui.dev/blog/ai-design-slop);
[wmedia on Anthropic's frontend-design skill](https://wmedia.es/en/tips/claude-code-frontend-design-skill)).

### How this app scores today (hub's reading, see `current-design-inventory.md`)

| Tell | Present? | Where |
|---|---|---|
| T1 | Partly | Segoe UI (Windows default); font sizes 11/15/16/22 px chosen per widget, no scale |
| T2 | **Yes** | `wtmhPrimary` buttons use a horizontal teal `qlineargradient`; canvas targets use a radial gradient |
| T3 | **Yes** | Setup = 4 stacked cards; configuration page = 3 columns of uniform rounded cards; report sections in boxes |
| T5 | **Yes** | Info/warning/success banners have a colored left border (`BANNER_BORDER`, `WARNING_BORDER`) |
| T6 | **Yes** | `SOFT_ACCENT` tinted table headers, pastel green/amber/blue banners, tinted legend box, amber run bar |
| T7 | Mild | Card shadows; radial gradient targets with white ring |
| T11 | Partly | Config page gives every setting equal weight; Test List is a full-width table with a detached button column |
Not present: T4, T8, T9, T10 (no emoji, no animation-heavy UI).

## 2. Design systems that fit clinical / medical desktop software

| System | Character | Fit for this app | Use from PySide6 |
|---|---|---|---|
| **IBM Carbon** (Apache-2.0) [site](https://carbondesignsystem.com/), [a11y](https://v10.carbondesignsystem.com/guidelines/accessibility/overview) | Enterprise, data-dense, flat, near-square corners, IBM Plex type, strict 2x grid and spacing tokens, accessibility built in | Strong: reads as an instrument/lab tool; good for tables, forms, reports | Port tokens (color, type, spacing) into our QSS; no Qt library |
| **Microsoft Fluent 2** [Windows design](https://learn.microsoft.com/windows/apps/design/) | Native Windows 11 look, familiar to clinic staff | Good on Windows clinic PCs | **PySide6-Fluent-Widgets** (`qfluentwidgets`, GPLv3 for non-commercial, paid commercial licence) [repo](https://github.com/zhiyiYo/PyQt-Fluent-Widgets); **Fluent-Qt** (MIT, young, C++ with PySide6 bindings) [repo](https://github.com/calvinhxx/Fluent-QT). Replaces widgets, not just styles |
| **NHS design system** (OGL v3) [service manual](https://service-manual.nhs.uk/design-system), [principles](https://service-manual.nhs.uk/design-system/design-principles) | Plain, high contrast, generous spacing, content-first; healthcare research behind it | Best source for **principles, content and accessibility rules** (plain language, error messages, staff vs public); web-first and less dense | Principles + content guide; visual tokens portable to QSS |
| Material 3 / shadcn-style | Rounded, tinted, card-based | Weak: the source of most AI-ish defaults | — |

Medical-software practice (independent of the system chosen): IEC 62366 / FDA human-factors
guidance — colour only for meaning (status/alerts), unmistakable feedback for every action, test
with real clinical users, design for the workflow
([Fuselab](https://fuselabcreative.com/the-crucial-role-of-medical-device-ui-ux-design/),
[Embien](https://www.embien.com/blog/ui-ux-guidelines-for-medical-devices),
[Eleken](https://www.eleken.co/blog-posts/medical-device-ux-design)).

Constraints from this project that any choice must respect:
- PySide6 Qt Widgets on Windows, 1920x1080 @ 100 % standard (SPEC-display-standard-check.md).
- Licence: research / non-commercial use (user, 2026-10-07), so GPL libraries are allowed.
- Two audiences: the **clinician** (operator UI: Setup, Test List, configuration, Start, run bar,
  dialogs, report + PDF) and the **child with CP** (task canvas: targets, cues, feedback, themes).
  The canvas has its own constraints: large high-contrast targets, low clutter, no distracting
  motion, visual-angle sizing (SPEC-target-size-and-motion-paths.md).
