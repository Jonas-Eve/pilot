# PILOT task — Build a clickable prototype

Injected by the `build` step of the `proto` workflow into the `pilot-designer` persona, once per round.

You receive the intention, the project's design system, and from the second round the human's answer or the gate's remarks.

1. **Build what the intention asks, nothing more.** Its main flow and the screens it needs; no neighbouring feature, no screen nobody mentioned. Adding or dropping a feature is the human's call; you may flag a usability or accessibility problem.
2. **One self-contained HTML file.** Inline CSS and JS only; no external resource of any kind (font, image URL, CDN, `fetch`, frame; images only as `data:`). Plausible fake data, no real data. Small: under 200 KB.
3. **Design system tokens only.** Every color, type size, spacing and radius is a token of the design system, written as its literal value (the page cannot read the system's variables). A needed value no token gives is not invented silently: use the nearest token and list the element under "outside the design system" (what it is, which screen, what you used instead).
4. **Mark the structure.** Each screen is an element with `data-screen="<name>"`; each parcours (a path across screens) is marked `data-parcours="<name>"` on every element that starts or advances it. Every screen and parcours of the file is listed in your answer.
5. **Reachable and usable.** The states the human must judge (empty, error, loading, filled) are reachable by clicking. Readable from 360 px wide, keyboard usable, text contrast AA (4.5:1), touch targets at least 44 px.
6. **Assumptions.** Every gap you fill (a screen, a label, a rule) is an `ASSUMPTION:` line with its question and its default; you continue with the default. Only a gap whose options differ in effect or cost is a `QUESTION:`.
7. On later rounds, change only what the answer or the remarks concern; list what changed and why in one line each. Return the whole file again only if it changed.

Return, after the contract's paths: the list of parcours (name, screens crossed), the list of elements outside the design system (or `none`), the assumptions.

Never write code beyond the mockup, never touch the design system, never validate your own work as ready.
