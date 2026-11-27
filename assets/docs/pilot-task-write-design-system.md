# PILOT task — Write a design-system entry

Injected by the `build` step of the `design-system` workflow into the `pilot-designer` persona.

You receive the design intention, the audit's delta and the proposed scope. You write one entry in format `design-entry`; each field and its checks are in `.pilot/formats.json`.

1. **Derive, never invent.** Take values from the existing design system, the sources the intention points to and the human's words. A value none supports is an `ASSUMPTION:` with its default. Never replace a value the existing system fixes unless the delta's resolution says so, and then say what it replaces.
2. **Tokens.** One line per token, named by role (`color.text.primary`), never by appearance. Always a `light` and a `dark` value, and `on:` the token it is displayed on for every foreground token. Each pair reaches WCAG AA: 4.5:1 for text, 3:1 for large text and interface borders, in both themes. A pair that fails is fixed before you write it, or listed as a defect you could not fix.
3. **Components.** One line per component, with a `category` of the format and every state its category requires (`required_states`), plus the tokens it uses. A component needs no state the category does not list, but never fewer. Interactive targets are at least 44 px; meaning never rests on color alone.
4. **Scope.** `pilot.scope` takes the terms of the project's vocabulary the audit proposed, no other.
5. **Stay at design-system level.** Tokens and components shared by every screen; no page layout, no product scope, no code.
6. **Never write the theme** (CSS variables, token files): it is generated from the entry. Never edit another entry; an overlap with one is resolved by what the delta says, else a `QUESTION:`.
7. **Demonstration page.** Also one self-contained HTML file (inline CSS and JS, no external resource) showing every component in every one of its states, in light and dark, with the entry's tokens as literal values.

A choice that changes an existing component's behavior for the screens that use it is a `QUESTION:`; every other choice is an `ASSUMPTION:`.

Return the entry's path, the demonstration page's path, and what the entry replaces (or `nothing`).
