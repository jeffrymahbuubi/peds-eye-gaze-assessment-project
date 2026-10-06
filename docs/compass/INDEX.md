---
title: "Compass 3.0 User Guide Corpus — Index"
subject: Compass 3.0 — Software for Computer Access Assessment (Koester Performance Research)
built: 2026-10-05
parser: NetMind parse_pro (netmind-parse-pdf-mcp 0.1.7), 8 x 20-page chunks merged
---

# Compass 3.0 User Guide Corpus

Knowledge corpus whose objective is to serve as a **reference on how the UI/UX of the Compass
app is created** — its screens, workflow, per-test configuration patterns, and accessibility
affordances. Built from the single PDF `Compass-User-Guide.pdf` (146 pages), which lives in
`resources/compass/` of the parent workspace (outside this repo; the Compass installer
`Compass_windows-x64_3_0_1.exe` sits beside it and is not part of the corpus).

The corpus has two layers:

- **`sources/`** — one file per source PDF, verbatim apart from the itemised corrections below.
  Use it when you need the exact wording.
- **`synthesis/`** — derived topic files. Hand-written; every statement cites a heading in
  `sources/`, nothing is added from outside, and contradictions inside the guide are surfaced
  rather than resolved.

## Synthesis (start here)

| File | Covers |
|---|---|
| [synthesis/ui-ux-patterns.md](synthesis/ui-ux-patterns.md) | Screen/navigation map, reusable interaction patterns, the common configuration-screen anatomy, the eight tests' defaults side by side, results-screen design, feedback, accessibility and localisation, platform facts, UI version history, **traps and inconsistencies in the guide**, and what the guide does *not* say |
| [synthesis/ui-ux-screen-walkthrough.md](synthesis/ui-ux-screen-walkthrough.md) | Screen-by-screen walkthrough of the Aim path, joining the 12 screenshots in [`screenshots/`](screenshots/) (captured from the installed 3.0.1) with the guide. Covers the visual language, real on-screen labels vs the guide's, guide-only screens, UX principles, and a factual mapping to the current peds-eye-gaze-assessment UI |

Note for its objective ("how the UI/UX is created"): the guide documents the product's
**behaviour**, not how it was built. The synthesis states this up front and collects the few
construction facts that exist.

## Sources (verbatim)

| File | Source PDF | Pages | Revision |
|---|---|---|---|
| [sources/compass-user-guide.md](sources/compass-user-guide.md) | Compass-User-Guide.pdf | 146 | Compass 3.0, copyright 2019 — no revision date stated |

## Orientation

The guide runs from product overview to per-test reference. Section names below are the
guide's own top-level headings, so they can be used to cite by section (page numbers are not
preserved):

- **General and interface** — *Welcome to Compass!*, *Tips for Using Compass*, *Getting Help*,
  *Tailoring the Compass Interface*, *International Languages and Compass*.
- **UI history** — *What's New in Version 3.0* back through *2.5 … 2.0* and *1.2*. The 2.0
  notes include an "Updated Look-and-Feel" section, so this is where UI changes are dated.
- **Accessibility and input devices** — *Compass Accessibility*, *Operating System Settings*,
  and *Using Compass with* pointing devices / alternative keyboards / word prediction /
  speech recognition.
- **Application workflow** — *Choose an Action*, *Overview of Sample Scenarios*, client
  create / open / edit, *How Compass Stores Client Information*, then *Skill Tests* →
  *Choosing Skill Tests* → *Test List* → *Configuring Tests* → *Running Tests* →
  *Viewing Results* → *Multi-Test Reports*.
- **Per-test chapters** — an Overview, Configuration and Results section for each of the
  Aim, Drag, Menu, Scan, Switch, Letter, Word and Sentence tests. The configuration sections
  are the densest description of the settings UI.
- **Back matter** — *About Koester Performance Research*, *Development Team*, *Index*.

## Provenance and caveats

- Parsed with NetMind's `parse_pro` engine, which recovered the heading structure (109
  headings), three tables (converted to markdown) and figure positions.
- **Parsed in chunks.** The 146 pages were sent as 8 requests (7 x 20 pages + 1 x 6) and merged
  in page order. A single 146-page request timed out in testing; the split was verified
  lossless (identical word multiset before and after). The chunk seams fall at section
  boundaries or between paragraphs; no table spans a seam.
- **Fabricated hyperlinks were removed.** The PDF has no link annotations and its text layer
  contains no URL except `kpronline.com`, but the parser invented **93** `[text](target)` links:
  15 external URLs (e.g. `computingkanal.de`, `computingkantha.com`, a `support.google.com`
  address, and one containing Chinese characters — the same anchor text received different
  fake URLs in different chunks), 75 `(#)` placeholders and 3 relative slugs. All were
  stripped and the anchor text kept, so the guide's in-text cross-references (blue underlined
  phrases such as "Test List") appear here as plain text. The two `https://kpronline.com`
  mentions are genuine.
- **Token corrections.** `Isecond` read as `1second`; `test_configuration` and `test_report`
  had underscores the PDF does not contain. All 96 edits (93 links + 3 tokens) are itemised in
  the file's `parser_corrections` frontmatter. This is the one respect in which `sources/` is
  not byte-verbatim.
- **What was verified, and what was not.** After repair, a word-level diff against an
  independent `pdftotext` extraction finds no word in the corpus that the PDF lacks, and 1,706
  of the PDF's 1,718 distinct words are present (the other 12 look like `pdftotext` artefacts
  such as split or run-together words). The identifier check in the skill is vacuous for this
  document — it has no `SCREAMING_SNAKE` identifiers. The corpus has **not** been proofread:
  these checks cannot detect changed numbers, single-letter errors, or reordered text.
- **Heading levels are not fully normalised** — e.g. *Sentence Test Results* is a level-2
  heading while the other test "Results" chapters are level 1. Cite by heading text, not level.
- **Figures are not extracted (text-only, by decision).** The 58 screenshots are marked
  `[FIGURE]`. For a UI/UX reference this is the main loss: every UI walkthrough and
  configuration-screen description is incomplete without its screenshot. Consult the source
  PDF for anything visual. Extracting the screenshot pages as images is possible later.
  **Partly offset (2026-10-06):** `screenshots/` holds 12 captures of the real 3.0.1 app
  (the Aim path, launch to report), described in `synthesis/ui-ux-screen-walkthrough.md`.
  They are app captures, not the guide's own figures.
- Page headers and footers were dropped (the 137 "Compass Help - …" footers do not appear).
  Page numbers are gone; the guide's own table of contents still lists them.
- **Version drift:** this is the guide for Compass **3.0** (copyright 2019); the installer
  alongside it is **3.0.1**, so the guide may lag the shipping app by one patch release.
- **One file, 2,670 lines.** Kept as a single file mapping 1:1 to the PDF for traceability,
  which exceeds the repo's 500-line guideline — a deliberate exception.
- **Unresolved conflicts between sources:** none (single source).
