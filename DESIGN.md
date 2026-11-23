---
name: AILSA run viewer
description: A run of the structure-elucidation agents, laid out as a herbarium specimen sheet with determination slips.
colors:
  pressed-leaf-olive: "oklch(42% 0.072 128)"
  olive-deep: "oklch(32% 0.055 131)"
  olive-line: "oklch(46% 0.085 130)"
  olive-tint: "oklch(92.5% 0.035 125)"
  olive-ink: "oklch(97% 0.016 115)"
  olive-ink-2: "oklch(86% 0.04 120)"
  stamp-red: "oklch(49% 0.17 28)"
  stamp-tint: "oklch(94% 0.03 28)"
  iron-ochre: "oklch(48% 0.1 68)"
  ochre-tint: "oklch(94% 0.035 80)"
  rag-paper: "oklch(97.6% 0.005 155)"
  paper-sunk: "oklch(94.4% 0.009 150)"
  slip: "oklch(99.4% 0.003 150)"
  archival-ink: "oklch(24% 0.035 258)"
  ink-2: "oklch(41% 0.03 255)"
  ink-3: "oklch(54% 0.025 250)"
  sepia-rule: "oklch(84% 0.025 78)"
  sepia-rule-strong: "oklch(66% 0.04 72)"
  contour-positive: "oklch(30% 0.035 258)"
  contour-negative: "oklch(55% 0.07 62)"
  neutral-mark: "oklch(60% 0.01 250)"
typography:
  display:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.95rem"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.62rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title-sm:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 650
    lineHeight: 1.2
  lede:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.45
  body:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\" 1"
  small:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Libre Franklin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    letterSpacing: "0.07em"
    fontFeature: "\"c2sc\" 1, \"smcp\" 1"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "0.86em"
    fontWeight: 500
    letterSpacing: "0em"
  attribution:
    fontFamily: "JetBrains Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.45
rounded:
  hairline: "1px"
  mark: "2px"
  sheet: "3px"
  field: "4px"
  control: "5px"
  switch: "6px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "10px"
  lg: "14px"
  xl: "18px"
  2xl: "24px"
  3xl: "36px"
  gutter: "clamp(16px, 3vw, 32px)"
components:
  button:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.archival-ink}"
    rounded: "{rounded.control}"
    padding: "7px 14px"
    height: "38px"
  button-hover:
    backgroundColor: "{colors.olive-tint}"
  button-primary:
    backgroundColor: "{colors.pressed-leaf-olive}"
    textColor: "{colors.olive-ink}"
    rounded: "{rounded.control}"
    padding: "7px 14px"
    height: "38px"
  button-primary-hover:
    backgroundColor: "{colors.olive-deep}"
  chip-ok:
    textColor: "{colors.olive-line}"
    rounded: "{rounded.sheet}"
    padding: "2px 8px"
    typography: "{typography.small}"
  chip-warn:
    textColor: "{colors.iron-ochre}"
    rounded: "{rounded.sheet}"
    padding: "2px 8px"
  chip-crit:
    textColor: "{colors.stamp-red}"
    rounded: "{rounded.sheet}"
    padding: "2px 8px"
  chip-na:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.sheet}"
    padding: "2px 8px"
  determination-slip:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.archival-ink}"
    rounded: "{rounded.sheet}"
    padding: "22px 24px 18px"
  accession-label:
    textColor: "{colors.archival-ink}"
    rounded: "{rounded.sheet}"
    padding: "7px 14px"
    typography: "{typography.small}"
  topbar:
    backgroundColor: "{colors.pressed-leaf-olive}"
    textColor: "{colors.olive-ink}"
    padding: "10px 32px"
  view-switch-active:
    backgroundColor: "{colors.olive-ink}"
    textColor: "{colors.olive-deep}"
    rounded: "{rounded.field}"
    padding: "6px 14px"
    height: "34px"
  rail:
    backgroundColor: "{colors.olive-deep}"
    textColor: "{colors.olive-ink-2}"
    rounded: "{rounded.sheet}"
    width: "220px"
  rail-item-current:
    backgroundColor: "{colors.olive-ink}"
    textColor: "{colors.olive-deep}"
    rounded: "{rounded.field}"
    padding: "9px 12px"
    height: "40px"
  register-head:
    backgroundColor: "{colors.paper-sunk}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    padding: "7px 10px"
  register-row-selected:
    backgroundColor: "{colors.olive-tint}"
  segmented-active:
    backgroundColor: "{colors.pressed-leaf-olive}"
    textColor: "{colors.olive-ink}"
    padding: "6px 12px"
    height: "34px"
  field:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.archival-ink}"
    rounded: "{rounded.field}"
    padding: "5px 8px"
    height: "32px"
---

# Design System: AILSA run viewer

## Overview

**Creative North Star: "The Herbarium Specimen Sheet"**

A run is a specimen sheet. The structure drawing lies in a double-ruled paper field like a pressed specimen; the declared result is a determination slip pinned beside it; run facts sit on a typed accession label. Nothing is ever erased. A rejected peak or a removed constraint stays on the sheet, struck through and readable, and a later confirmation arrives as a new slip on top, never mixed into the evidence. The system refuses the category default of a dark spectrum dashboard with tiles, gauges and neon traces.

The ground is cool rag paper, never cream; text and drawings are archival blue-black ink; hairlines are iron-gall sepia. Pressed-leaf olive is the one committed colour and carries the chrome (top bar, expert rail), selection and "used" evidence. Stamp red is reserved for critical verdicts. The night theme is a specimen cabinet: green-black ground, bone ink, the same roles. Density is that of a working document, Operate mode: one grotesque at a 1.2 scale, tabular figures everywhere, monospace only for attribution and identifiers.

State is carried by line form, not hue. Every encoding of "used, held back, removed, decisive" reads correctly in greyscale, in forced colours and on paper.

Provenance: concept roll `seed:46e6919c6c91e8b3` (herbarium specimen sheet with determination slips).

**Key Characteristics:**
- Flat paper surfaces separated by sepia hairlines; one shadow in the whole system, on popovers.
- One committed colour (olive); red is a stamp, used on critical chips only.
- Line form grammar: solid used, dashed held back or open, struck removed, doubled decisive.
- Small-caps tracked field labels, only beside or inside the field they name.
- Two views, never shown together: a plain chemist view and a complete expert view.

## Colors

A near-monochrome archive palette, ink on paper, with a single pressed-leaf green and a red kept for the stamp.

### Primary
- **Pressed-Leaf Olive** (`pressed-leaf-olive`): top bar, primary button, active segment, checkbox and range accents. **Olive Deep** fills the expert rail and the top bar's lower edge. **Olive Line** is the stroke form: links of the "why?" kind, used correlations, curated peak markers, focus rings, selected atoms, the final number of the narrowing sequence. **Olive Tint** is the fill form: selected register rows, the current spectrum, text selection, hover on buttons, work bars in the timeline. **Olive Ink** and **Olive Ink 2** are the text colours on olive grounds.

### Secondary
- **Stamp Red** (`stamp-red`, with `stamp-tint`): the outline and text of a critical verdict chip. Nothing else.

### Tertiary
- **Iron Ochre** (`iron-ochre`, with `ochre-tint`): caution without alarm. Warning chips, the dashed rings that mark undetermined stereocentres, excluded 1D lines, the picker threshold line, the "illustrative" marker.

### Neutral
- **Rag Paper** (`rag-paper`): page ground and the specimen field.
- **Paper Sunk** (`paper-sunk`): register headers, the result bar, agent notes, row hover.
- **Slip** (`slip`): the brightest surface; determination slip, registers, inputs, canvases, popovers.
- **Archival Ink** (`archival-ink`): text, structure drawings, long-range correlation arrows. **Ink 2** for secondary text, labels and anything removed or struck. **Ink 3** for disabled controls, unrecorded values and the arrows between numbers.
- **Sepia Rule** (`sepia-rule`): every hairline divider. **Sepia Rule Strong**: control borders, slip and accession borders, register top and bottom rules, underline colour of links at rest.
- **Contour Positive** (`contour-positive`): positive 2D contours, an ink tone. **Contour Negative** (`contour-negative`): negative 2D contours, sepia, drawn dotted. **Neutral Mark**: impurity and solvent crosses in 2D spectra.

The night theme ("specimen cabinet") redefines every token under `[data-theme="dark"]` and under `prefers-color-scheme: dark` guarded by `:root:not([data-theme="light"])`; values are in the sidecar. Roles do not change between themes.

### Named Rules
**The Stamp Rule.** Stamp red appears only on critical verdict chips. Removed or struck items use Ink 2; long-range (four bonds or more) correlations use ink plus a "4J" tag. If red shows anywhere else, it is a defect.

**The One Leaf Rule.** Olive is the only committed colour. Ochre means caution, red means critical, everything else is ink on paper.

**The Greyscale Test.** Print the page in greyscale: every state must still read, because line form carries it and hue only reinforces it.

## Typography

**Display Font:** Libre Franklin (with ui-sans-serif, system-ui)
**Body Font:** Libre Franklin
**Label/Mono Font:** JetBrains Mono (with ui-monospace, SF Mono, Menlo)

**Character:** One sober grotesque does all the speaking, from the slip's determination down to register cells; a tabular mono appears only where a typewriter would, in the attribution line and in identifiers. Both are self-hosted variable woff2, inlined at build time; the page needs no network.

### Hierarchy
- **Display** (650, 1.95rem, 1.15, -0.02em): the slip's h1, which is the determination itself. Max 22ch. Drops to the headline size below 560px.
- **Headline** (650, 1.62rem, 1.2): expert section heads.
- **Title** (650, 1.35rem): chemist-view section heads such as the reasons register.
- **Title Small** (650, 1.125rem): block heads, reason heads, the narrowing numbers.
- **Lede** (400, 1.125rem, 1.45): the slip's result sentence. Max 46ch.
- **Body** (400, 0.9375rem, 1.5): running text, tabular figures on. Max 52 to 75ch.
- **Small** (400, 0.8125rem, 1.45): captions, legends, register cells, caveats, chips.
- **Label** (600, 0.8125rem, 0.07em, all-small-caps): field labels in the accession label, key-value lists and register headers.
- **Attribution** (mono 500, 0.8125rem): the "Det." line under the slip heading.

### Named Rules
**The Typed Label Rule.** Small-caps tracked labels sit only beside or inside the field they name, like typed accession labels. Never above a heading as a category tag.

**The Determination Rule.** The slip's heading is the result in plain words. Attribution follows below it as one monospace "Det." line (who determined it, scope); no label sits above the heading.

**The Small-Caps Symbol Rule.** Greek symbols inside small-caps headers opt out of case mapping, so δ never becomes Δ.

## Layout

Content sits in a 1440px column with a fluid gutter (16 to 32px). The chemist view is a two-column sheet, three fifths specimen field and two fifths slip (minimum 340px), with the accession label under the specimen; below 920px of container width it stacks specimen, slip, facts. Below it the reasons form a three-column ruled register with sepia rules top and bottom, stacking under 920px.

The expert view is a 220px olive rail beside a work area that opens on a sunk result bar. Below 760px the rail becomes a horizontal sticky strip that bleeds to the screen edges and scrolls sideways; its note is hidden. Below 900px the spectrum list likewise becomes a compact horizontal strip so the viewer comes first. Two-column blocks fall to one column under 860px. Layout responds to container queries wherever a component lives inside a view.

Rhythm is tight and document-like: 6 to 14px inside components, 18 to 24px between fields, 28 to 44px between sections. Registers scroll inside their own frame (max 70vh) with sticky headers and a sticky first column.

### Named Rules
**The Two Views Rule.** Chemist and expert views are never shown together. One switch in the top bar and "why?" links move between them.

## Elevation & Depth

Flat. Depth comes from paper tones (sunk, paper, slip) and hairlines, not shadows. The specimen field has a double rule: a sepia border plus an inset outline 7px inside it. The only shadow is the popover's two-layer ambient shadow; the toast inverts ink and paper instead of lifting.

### Shadow Vocabulary
- **Popover** (`box-shadow: 0 2px 4px var(--shadow), 0 12px 30px -12px var(--shadow)`): glossary popovers only.

### Named Rules
**The Paper Stack Rule.** A surface is lighter the closer it is to the reader: sunk, then paper, then slip. Nothing floats except the popover.

## Shapes

Nearly square. Sheets, chips and registers take a 3px corner; buttons and segmented controls 5px; fields 4px; the view switch 6px around 4px buttons. Error bands take 2px, data marks (strip cells, timeline bars) 1px. Borders are always 1px hairlines; a dashed border means "not available or held back", a dotted one "unrecorded". Icons are 20-unit outline SVGs, 1.6 stroke, round caps.

## Components

### Buttons
Quiet and paper-like; olive is earned by the primary action.
- **Shape:** gently squared (5px), min height 38px; small variant 30px.
- **Default:** slip background, ink text, Sepia Rule Strong border, 600 weight.
- **Primary:** olive fill, olive-ink text; hover darkens to Olive Deep.
- **Hover / Focus:** default hover takes olive tint and an olive-line border (160ms ease-out); focus is a 2px olive-line outline offset 2px.
- **Disabled:** Ink 3 text and a dashed border, so the state is line form too.
- **"Why?" link:** small, 600, olive-line, underlined in Sepia Rule Strong, the underline darkening on hover.

### Chips
- **Style:** outline only, 3px corner, small 600 text, colour shared by text and border.
- **State:** ok olive-line solid; warn ochre solid; critical stamp red solid; not applicable Ink 2 dashed; unrecorded Ink 3 dotted italic.

### Cards / Containers
- **Determination slip:** slip background, Sepia Rule Strong border, 3px corner; fields separated by sepia hairlines; a caveat foot in small Ink 2. A dashed "ghost" slip above it announces where later confirmations will appear.
- **Accession label:** a ruled two-column key-value table, labels in small caps; one column under 560px.
- **Agent note:** paper-sunk box with a "who" line, so agent judgement is visibly attributed.
- **Internal padding:** 22 to 24px on slips, 7 to 14px in ruled rows.

### Inputs / Fields
- **Style:** slip background, Sepia Rule Strong border, 4px corner, min height 32px; checkboxes and ranges take the olive accent.
- **Focus:** the global olive-line outline.

### Navigation
- **Top bar:** olive, sticky (static below 560px), brand mark in tracked small caps, run line in olive-ink-2, the Chemist/Expert switch on the right with the active option inverted to olive-ink on olive.
- **Expert rail:** Olive Deep panel, items 40px high; the current item inverts to olive-ink with Olive Deep text. Horizontal sticky strip at phone width.
- **Segmented control:** ruled segments on slip; the pressed one is olive.

### Registers (signature)
Tables are ledgers. Small text, sepia row rules, sticky small-caps headers on paper-sunk, numbers right-aligned and tabular. Selected rows take olive tint. Removed rows are struck through in Ink 2 but stay fully readable; the status cell is never struck.

### Line-form glyph (signature)
A 26 by 10 inline glyph before a state word, drawn in currentColor at 1.6 stroke: a solid line (used), a dashed line (held back), a line with a cross (removed), a doubled line (decisive). The same grammar runs through the whole system:
- **Correlation arrows on the structure:** solid olive used, dashed held back, doubled (olive outer with a paper core) decisive, ink with a "4J" tag for long range; every arrow has a paper underlay.
- **2D markers:** HMBC used filled olive, held back a dashed open ink circle, decisive a ring around the mark, removed an Ink 2 cross; HSQC curated circles for CH/CH₃ and squares for CH₂, olive with a paper halo.
- **Error bands:** plain within tolerance, underlined above it, double-underlined plus bold far above it.
- **Timeline:** work bars filled olive tint, review bars open outlines, bars over an hour print their duration; segments drawn to exact duration.

### Structure figure (signature)
The structure drawing sits above its interactive overlay, so atom numbers stay legible over arrows; clicks fall through to the overlay. Atom numbers carry a paper stroke halo (3.5px). Undetermined stereocentres are ringed in dashed ochre; selected atoms take an olive-line ring.

### Spectrum viewers (signature)
Canvas viewers on a slip ground inside a hairline frame, crosshair cursor, a mono readout below. 2D contours: positive in the ink contour token, negative in the sepia token drawn dotted. Every canvas has an equivalent register.

### Chemist-view furniture
- **First-visit note:** one line of small Ink 2 text between two solid sepia hairlines, actions on the right.
- **Narrowing sequence:** a plain row of numbers in title-small weight joined by thin Ink 3 arrows, the last number olive. No solver notation.
- **Team curtain call:** after the run, five compact cast cards (glyph, name, one sentence of contribution) and a "Replay the run" button.

### Live and replay (signature)
One time control serves both cases: during a live run it sits on "now", for a finished run it replays. Both views then show the state at that moment.
- **Replay bar:** a paper-sunk strip under the top bar (sticky on desktop, static on phones): play/pause, previous and next event, a range track with event ticks (taller olive ticks for solver results, doubled ticks for decisive findings), the time and round, a speed choice, "Jump to the end" and "Close replay".
- **Team strip:** the five agents, each with an outline glyph (hub, spectrum, hexagon, magnifier, balance), name and one line of current activity. A working agent gets a solid olive-line frame on slip; an idle one has no frame and Ink 3 text. While the run works, the strip takes the specimen's place in the chemist view.
- **Diary (chemist view):** time plus one plain sentence per step, newest first, five shown and the rest behind a disclosure; a decisive step carries the doubled glyph and bold text. No interim structure ever appears in the chemist view.
- **Interim standings (expert view):** dashed-frame cards (dashed: held back, not a result) with the drawing, the owner and time in the "Det." line, the lead and its caveat.
- **Message score (expert Team section):** one row per message: time, five lane columns (a filled bar means that agent was working), an arrow from sender to receiver (solid; doubled olive for a decisive finding; a diamond for a decision, a filled square for start and end), then the sender, receiver, verdict chip and the condensed message. Gaps over ten minutes become a row naming what was going on.
- **Cast cards:** glyph, name, role, then stacked small-caps fields (model, worked, messages, now or key part) without an inner frame; a working agent's card takes the olive-line border.

## Do's and Don'ts

### Do:
- **Do** carry every state by line form first: solid used, dashed held back or open, struck removed, doubled decisive.
- **Do** keep struck items readable in Ink 2; nothing disappears, it cancels.
- **Do** keep stamp red (`stamp-red`) on critical verdict chips only.
- **Do** draw positive 2D contours in `contour-positive` and negative ones dotted in `contour-negative`; mark curated peaks in olive-line with a paper halo.
- **Do** make the slip heading the determination itself, with the monospace "Det." line below it.
- **Do** give atom numbers and correlation arrows a paper halo or underlay so they read over each other.
- **Do** pair every canvas with a table and every colour with a shape, line form or word.
- **Do** keep the two views separate and link them with "why?".

### Don't:
- **Don't** use red for removed, struck or long-range items; use Ink 2, or ink with a "4J" tag.
- **Don't** put a small-caps label or category tag above a heading; field labels live beside their fields.
- **Don't** write solver notation in the chemist view; the narrowing is plain numbers.
- **Don't** add shadows to cards, slips or registers; depth is paper tone and hairline.
- **Don't** introduce a second committed colour, gradients, neon traces, gauges or tiles.
- **Don't** use cream or warm grounds; the paper is cool grey-white.
- **Don't** show the chemist and expert views side by side.
