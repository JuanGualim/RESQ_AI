---
name: RESQ AI
description: A live dispatch board for versioned flood-aid decisions.
colors:
  attention-amber: "#FFB400"
  canvas-black: "#0D0F0F"
  inset-black: "#101415"
  panel-black: "#121617"
  control-steel: "#171C1D"
  active-steel: "#202729"
  header-steel: "#252C2E"
  steel-divider: "#596265"
  warm-white: "#F2F2F2"
  secondary-text: "#CBD0D1"
  active-mint: "#70C1A5"
  blocked-red: "#D32F2F"
  escalated-wash: "#3A1717"
typography:
  display:
    fontFamily: "Dispatch Condensed, sans-serif"
    fontSize: "1.8rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.12em"
  headline:
    fontFamily: "Dispatch Condensed, sans-serif"
    fontSize: "1.15rem"
    fontWeight: 700
    letterSpacing: "0.075em"
  title:
    fontFamily: "Dispatch Condensed, sans-serif"
    fontSize: "1.7rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "0.06em"
  body:
    fontFamily: "sans-serif"
  label:
    fontFamily: "Dispatch Condensed, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    letterSpacing: "0.075em"
rounded:
  square: "0"
  control: "2px"
spacing:
  tight: "5px"
  compact: "8px"
  control: "10px"
  row: "12px"
  panel: "18px"
  header: "22px"
components:
  button-action:
    backgroundColor: "{colors.control-steel}"
    textColor: "{colors.attention-amber}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "42px"
  button-action-hover:
    backgroundColor: "{colors.attention-amber}"
    textColor: "{colors.canvas-black}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "42px"
  status-chip:
    textColor: "{colors.secondary-text}"
    typography: "{typography.label}"
    rounded: "{rounded.square}"
    padding: "7px 10px"
  decision-panel:
    backgroundColor: "{colors.panel-black}"
    textColor: "{colors.warm-white}"
    rounded: "{rounded.square}"
    padding: "18px"
  assignment-table:
    backgroundColor: "{colors.inset-black}"
    textColor: "{colors.warm-white}"
    rounded: "{rounded.square}"
  road-status-legend:
    backgroundColor: "{colors.inset-black}"
    textColor: "{colors.secondary-text}"
    rounded: "{rounded.square}"
    padding: "10px 5px 2px"
---

# Design System: RESQ AI

## Overview

**Creative North Star: "The Live Dispatch Board"**

RESQ AI is an operational surface with the urgency and legibility of a live transport dispatch board. Matte near-black planes, cool steel seams, condensed uppercase labels, and ordered rows make current state scannable without dressing the interface as a simulated control panel.

Expression comes from disciplined semantics rather than decoration. Amber identifies attention and action, mint confirms open or active state, and red is reserved for blocked or escalated conditions. Dense decision data remains readable because labels and display moments use the self-hosted Dispatch Condensed face while reports, reasons, and explanatory copy stay in a readable sans-serif.

The interface is flat, square, and ruled. One-pixel dividers organize the board, line patterns keep road status understandable without color, and a brief staggered amber signal marks assignment rows only when the plan fingerprint changes.

**Key Characteristics:**

- Matte near-black tonal layers separated by cool steel one-pixel rules.
- Condensed uppercase operational labels paired with readable long-form copy.
- Amber attention, mint open or active state, and red blocked or escalated state.
- Ordered dispatch rows and patterned route lines as the signature visual language.
- Familiar controls, compact density, and restrained motion for an Operate surface.

## Colors

The palette is a cool, low-glare night board with one warm action signal and tightly governed semantic state colors.

### Primary

- **Dispatch Amber** (`attention-amber`): Draws attention to actions, active tabs, table headers, priority values, quantities, links, and flooded or limited roads.

### Secondary

- **Clear-Route Mint** (`active-mint`): Confirms open roads and an active, dispatch-ready decision.

### Tertiary

- **Blocked Red** (`blocked-red`): Marks blocked or closed routes and the structural border of an escalation state.
- **Escalation Wash** (`escalated-wash`): Creates the alert field behind escalated incident and human-review messaging.

### Neutral

- **Canvas Black** (`canvas-black`): The page ground and the dark text color used when amber becomes a filled interactive state.
- **Inset Black** (`inset-black`): The command header and scrollable table ground.
- **Panel Black** (`panel-black`): Sidebar and decision-panel surface.
- **Control Steel** (`control-steel`): Inputs and resting action controls.
- **Active Steel** (`active-steel`): Hover rows and the default incident strip.
- **Header Steel** (`header-steel`): Sticky table-header plane.
- **Steel Divider** (`steel-divider`): Primary one-pixel borders, section rules, and sticky-column seam.
- **Warm White** (`warm-white`): Operational headings, primary values, nodes, and focus outlines.
- **Secondary Text** (`secondary-text`): Reports, labels, and supporting copy that should recede from primary values without becoming dim.

**The Signal Ownership Rule.** Amber means attention or action, mint means open or active, and red is used only for blocked or escalated conditions; never exchange these roles for decoration.

## Typography

**Display Font:** Dispatch Condensed, the locally hosted Barlow Condensed family, with sans-serif fallback  
**Body Font:** Sans-serif, inherited from the Streamlit dark theme  
**Label Font:** Dispatch Condensed with sans-serif fallback

**Character:** The pairing feels precise and time-sensitive without sacrificing reading comfort. Condensed type compresses operational identity and metadata; the body face carries reasons, reports, trace summaries, and longer risk language.

### Hierarchy

- **Display** (700, `1.8rem`, `1`, `0.12em`): RESQ AI wordmark and the strongest board identifier.
- **Headline** (700, `1.15rem`, `0.075em`): Ruled section headings such as Road network and Dispatch assignments.
- **Title** (700, `1.7rem`, `1.1`, `0.06em`): Current decision state and escalation emphasis.
- **Body** (sans-serif): Reports, reasons, risks, and explanatory content; preserve the natural reading rhythm of the framework rather than condensing long copy.
- **Label** (700, `0.75rem`, `0.075em`, uppercase): Table headings, chips, and compact controls.

**The Condensed Role Rule.** Use Dispatch Condensed for identity, labels, statuses, headings, and controls; never use it for long reports or multi-line reasoning.

## Layout

The desktop surface is a wide board capped at `1500px`, with a slim command header followed by incident state. The primary operational split uses a `1.35:0.65` map-to-decision ratio, then a full-width assignment board and evidence tabs. Section titles sit on ruled baselines instead of inside detached cards.

Spacing is compact and purposeful: controls cluster at `5–10px`, table rows use `10–12px` insets, and primary panels use `18–22px`. Tables scroll within bounded regions while their headers remain visible.

At `760px` and below, the header stacks, metadata wraps, and the current decision precedes the road map. The assignment table remains horizontally scrollable; priority and community stay sticky at `76px` and `108px`, with a visible scroll hint explaining the behavior.

**The Decision-First Rule.** On narrow screens, show the current decision before the map and keep the first two dispatch columns anchored during horizontal inspection.

## Elevation & Depth

The system is flat by design. It uses no decorative shadows: depth comes from tonal near-black layers, one-pixel steel rules, alternating table rows, and state fills. The single `1px` sticky-column shadow is a structural seam, not an elevation effect.

**The Flat Board Rule.** Separate operational regions with tone and one-pixel rules; do not introduce floating cards, soft drop shadows, glass, or glow.

## Shapes

The form language is square and infrastructural. Panels, tabs, chips, tables, map frames, and alerts use square corners; only native action controls and selects retain a minimal `2px` radius so they remain familiar and usable. Borders are thin and cool rather than ornamental, while dashed empty-state frames signal absence without pretending to be a card.

## Components

### Buttons

- **Shape:** Almost square native control (`2px`) with a minimum height of `42px`.
- **Primary:** Dark control surface, amber text and border, bold condensed uppercase label.
- **Hover / Focus:** Hover fills amber and reverses text to canvas black; keyboard focus uses a `3px` warm-white outline with a `2px` offset.

### Chips

- **Style:** Square, transparent metadata cell with a steel border and compact `7px 10px` inset.
- **State:** Values use amber and tabular numerals; labels remain secondary warm gray.

### Cards / Containers

- **Corner Style:** Square (`0`).
- **Background:** Near-black tonal layers distinguish header, decision, map, table, and incident surfaces.
- **Shadow Strategy:** None; see Elevation & Depth.
- **Border:** One-pixel steel divider.
- **Internal Padding:** `18px` for primary decision content and `18px 22px` for the command header.

### Inputs / Fields

- **Style:** Dark steel fill, cool steel border, warm-white text, and a minimal `2px` radius.
- **Focus:** The same warm-white `3px` outline and `2px` offset used by buttons.
- **Disabled:** Preserve the framework's conventional disabled behavior; do not recolor it as an operational state.

### Navigation

Evidence tabs remain flat and square with a steel baseline. Inactive labels are subdued; the selected tab uses amber text and an amber bottom border. Keep the familiar Streamlit interaction model intact.

### Current Decision Panel

The panel leads with a bold two-line state, with ACTIVE in mint or ESCALATED in red, followed by one-pixel-separated metric rows and tabular numeric values. An escalation banner sits outside the panel as a red alert region with explicit human-review language.

### Dispatch Assignment Board

Assignments are ordered by priority in a dense ruled table. Headers stay pinned, alternating near-black rows support tracking, and priority and quantity are amber. Only a changed plan fingerprint triggers the `500ms` staggered amber row signal, offset by `35ms` per row and disabled for reduced-motion users.

### Road Status Legend

Road state is never color-only: open is a continuous mint line, flooded or limited is a long-gap amber pattern, and blocked or closed is a short-gap red pattern. Active routes become heavier on the map without changing their semantic line pattern.

**The Changed Plan Rule.** Animate dispatch rows only after the selected plan fingerprint changes; ordinary rerenders and static inspection remain still.

## Do's and Don'ts

### Do:

- **Do** keep the current plan state, route network, and ordered assignments visually primary.
- **Do** pair every road-status color with a distinct line pattern and a written label.
- **Do** reserve amber, mint, and red for their named semantic roles.
- **Do** use one-pixel rules and tonal layering to organize dense operational information.
- **Do** preserve conventional control behavior, visible keyboard focus, and reduced-motion support.

### Don't:

- **Don't** introduce rounded dashboard cards, decorative shadows, glass effects, or floating metric tiles.
- **Don't** use red for warnings that are not blocked or escalated states.
- **Don't** set reports, reasons, or other long-form copy in Dispatch Condensed.
- **Don't** animate assignment rows unless the plan fingerprint actually changes.
- **Don't** hide priority or community context while the mobile assignment table scrolls horizontally.
