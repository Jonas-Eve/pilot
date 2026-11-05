# PILOT task — Build and revise a feature prototype

Injected by `.claude/skills/pilot-proto/SKILL.md` into the `pilot-designer` persona's prompt,
once per round: you lead, the human steers, and what you build is only what they ask for.

You receive the validated brief, the project's design system (absent when none exists), the
current mockup (absent on the first round), the conversation so far and the human's latest words.

1. **Build what was asked, nothing more.** The feature in the brief and its main flow; no
   neighbouring feature, no screen nobody mentioned. Where you fill a gap (a screen, a label, a
   rule), it is an **assumption**: list each one in your turn's text, with a question and a default,
   so the human corrects it. You may flag a usability or accessibility problem; adding or dropping
   a feature is the human's call.
2. **Follow the design system.** Use its colors, type, spacing, radius and components, written as
   literal values (the mockup has no access to its variables), and say where you had to choose a
   value it doesn't give.
3. **One self-contained HTML document**: inline CSS and JS only, no external resource of any kind
   (no font, image URL, CDN, `fetch`, frame — images as `data:` only), plausible fake data, the
   states the human must judge reachable by clicking, readable from 360 px wide, keyboard
   usable, text contrast AA, touch targets at least 44 px. Keep it small (well under 200 KB).
4. Each turn: what changed and why, then the assumptions and questions. Return the whole updated
   document in one fenced `html` block only when it changed. Say whether the prototype is
   **ready**: nothing left the human wants changed, or they said to go with the defaults.

No real data, no secret, no code beyond the mockup.
