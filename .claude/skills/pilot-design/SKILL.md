---
name: pilot-design
description: "Creates or revises the project's design system and brand charter, shown in the \"Design\" tab of its PILOT dashboard (.pilot/pilot-process.md). Not one of the five phases: the designer leads a live discussion with a human (pair only, never --auto), deriving colors, type, spacing, components and accessibility rules from the project's own docs and whatever the human hands over, until the human approves; the approved sections are written into the dashboard's own database. PM and architect are summonable (--with pm,architect) or can be summoned mid-session. --section <charter|colors|type|space|components|a11y> restricts the run to one section; the rest of the document is left untouched. Needs a project with a dashboard (/pilot-dashboard) and the tool that writes to its database. Use whenever a human wants to create or change the design system or the brand charter."
argument-hint: "[--section charter|colors|type|space|components|a11y] [--with pm,architect] [what to create or change, in free text]"
disable-model-invocation: true
---

# PILOT design — `pilot-design`

Read `.pilot/pilot-process.md` first — it is the source of truth for the roster. Here the
designer leads, there is no validator (the human approves), and the PM and architect are
summonable (`.pilot/pilot-process.md` §4 "Roster"); `.pilot/pilot-task-advise.md` is read and
passed into a summoned persona's call. Always pair: it needs a human live and is never run
from a scheduled sweep.

## Steps

0. **The module.** `python3 .pilot/pilot.py module list`: with the `design` module off, say so and propose turning
   it on (`python3 .pilot/pilot.py module enable design --with-requires`, which turns the `dashboard` module on
   too); on a yes go on, on a no stop.
1. **Preconditions.** `.pilot/state.json` has `dashboardUrl`, else stop and point at
   `/pilot-dashboard`. The tool that writes to the dashboard's database (`ArtifactData`,
   `ToolSearch` loads it if deferred) must be available, else say so and stop. Repo =
   `owner/repo` from `git config --get remote.origin.url`, matching `[\w.-]+/[\w.-]+`.
2. **Read** the current document: `ArtifactData` `get` on `design/<owner>__<repo>` at
   `dashboardUrl`, keeping its version. Absent → creation (the whole document, or just
   `--section`). Present → everything outside the asked section stays as it is.
3. **Sources.** List (don't blindly read) the filenames under `docs/` (and `apps/<app>/docs/`
   in a monorepo) and open only what looks like a brand, mockup, wireframe or UX guideline by
   name, plus any theme/token file the project has; add whatever the human gives in the
   session (view an image, read a file).
4. **Discuss.** Call `Agent` for `pilot-designer` with `.pilot/pilot-task-write-design-system.md`,
   the current document, the section, the human's text, the sources and the conversation so
   far — nothing else from this conversation. Show the human the designer's proposal and its
   questions as a natural conversation (a provisional default as the recommended option when
   one helps), feed the replies back, and call it again. Any persona from `--with`, or
   summoned or dismissed by the human, takes part the same way. Stop when the designer says
   the section is ready and the human approves.
5. **Write.** Validate the returned JSON: hex values `#RGB`/`#RRGGBB`, numeric sizes, `logo`
   an inline SVG under 20 KB, each component `preview` a fragment under 4 KB with no `<script>`,
   event handler or external URL, nothing but plain text elsewhere — fix or ask, never write it
   unchecked. The document, `previous` included, must stay under 250 KB serialized: when it
   would not, leave `previous` out and say so. Merge the approved sections into the current document, keep the document as it
   was before this run in a `previous` field (replacing any older one, never nesting them), and
   `ArtifactData` `set` it on `design/<owner>__<repo>` (pass `if_version` when it existed), with
   `kind: "design"`, `repo` and `at` (now, UTC ISO 8601). A version conflict → `get` again, merge
   your sections into that one and retry once. A refusal (the write reads as not found) means
   this person lacks the Contributor level on the dashboard: save the approved JSON to a
   temporary file, give its path, and say to ask the dashboard's owner for that level — never
   drop the approved work.
6. **Report** the sections written and the dashboard's address with `#design`. The tab is
   readable by everyone the dashboard is shared with; everyone at the Contributor level or above
   can run this, and `previous` holds one step back to restore from.
