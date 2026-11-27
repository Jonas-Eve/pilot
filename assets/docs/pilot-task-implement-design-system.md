# PILOT task — Implement a design system
Injected by the `implement` step of the design-system workflow into the `pilot-dev` persona's prompt.

You receive a validated design entry (tokens, components with their category, states and tokens), the generated theme, and the guidelines and tooling of the interface (component library, token format).

1. The generated theme is the only source of values. Never edit it by hand; if it lacks a token the entry declares, QUESTION: the theme is regenerated, not patched.
2. Build each component of the entry with the library the guidelines name. It implements every state its category requires in `.pilot/formats.json` (`required_states`) plus those the entry lists, and uses only the tokens the entry lists for it.
3. No color, spacing, size, radius, shadow or typography value is written in a component or screen: only theme tokens. Dark and light both come from the theme.
4. Write the rule "tokens only": any hard-coded value of those kinds in the interface is reported. It is limited to the entry's `pilot.scope`; it never fires outside it.
5. Examples, written first: components using tokens must pass; a component with one hard-coded value must fail. Inject one such value in a scratch copy, confirm the rule reports it, then remove it.
6. Each component has a test per state (rendered, accessible name and role present, focus visible where the category has focus).
7. Run the rule on the existing interface code in scope. A pre-existing hard-coded value is not fixed by you: list it as an ASSUMPTION with its paths.
8. A choice the entry and guidelines do not cover whose options differ in effect or cost: QUESTION; otherwise ASSUMPTION.

Never: edit the entry, the theme or a guideline, invent a token, widen the scope, open a PR.

Return the paths of the components, rule, cases and tests, then ASSUMPTION lines, then a QUESTION if any.
