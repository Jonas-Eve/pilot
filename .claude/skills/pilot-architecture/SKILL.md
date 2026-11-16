---
name: pilot-architecture
description: "The project's architecture (architecture/ at the project root, .pilot/pilot-link-architecture.md): overview of the apps, the technical guidelines AIs and developers must respect, the reference of how the code is built today (stack and versions, data model, structure), and the architecture decision records (ADR: why a choice was made). No flag, or a question in free text → answers from it with citations (path, status), and says when it does not cover it. --guideline \"<rule>\" → drafts one rule with the architect and a human, one PR. --adr \"<decision>\" → drafts an ADR, one PR; one that replaces an accepted ADR supersedes it. --edit <id> \"<change>\" → rewrites an entry, one PR (an accepted ADR is replaced, never edited). --deprecate <id> → deprecates an entry or removes a proposed one, one PR. --verify [<id>] → checks the reference entries against the code, stamps those that hold, a human arbitrates each divergence, one PR. --bootstrap → drafts overview, guidelines and reference from the existing apps/, docs and code, one PR. --scaffold → creates the apps' skeletons and the overview. --lint → mechanical checks. Never merges a PR, never claims a ticket. When the module is off it proposes to turn it on first. Use to ask how the project is built and why, to add a rule, to record a decision, or to set the architecture up."
argument-hint: "[<question>] | --guideline \"<rule>\" | --adr \"<decision>\" | --edit <id> \"<change>\" | --deprecate <id> | --verify [<id>] | --bootstrap | --scaffold [<free-text apps and tech>] | --lint"
---

# PILOT architecture — `pilot-architecture`

Read `.pilot/pilot-link-knowledge.md` (how to read the bundle) and `.pilot/pilot-link-architecture.md` (layout, statuses, the rules below) first. Mechanics are in
`python3 .pilot/pilot.py arch …` (`index`, `reindex`, `show`, `lint`, `add`, `set`, `remove`, `supersede`); run the
script, never hand-edit an entry's frontmatter or an `index.md`. Not one of the five phases: it claims no ticket
and changes no label.

## Preflight

Run `python3 .pilot/pilot.py doctor --no-wiki` once per session; stop with its report if it fails.

## The module

`python3 .pilot/pilot.py module list` tells whether the `architecture` module is on. Off, or `architecture/`
missing: say so and propose turning it on (`python3 .pilot/pilot.py module enable architecture`, then
`python3 .pilot/pilot.py arch reindex`, which creates `architecture/` with its root `index.md`). On a yes, go on
with what was asked; on a no, stop. When the project has an `apps/` folder or `apps` in `.pilot/state.json`, offer
`--bootstrap` right after; when it has none, offer `--scaffold`.

## Question (no flag)

1. Read per `.pilot/pilot-link-knowledge.md`: `arch index --depth 1`, then `arch search` or a folder, then `arch show` only those that bear on the question (`--all` for history).
2. Answer from them, citing each as its `path` and status. A `proposed` entry is not yet a rule: say so; a
   `superseded` one is history, point at its successor. Where the architecture is silent, say it is not
   covered; do not fill the gap from the code.

## `--guideline "<rule>"`

1. Check it is a rule, not a fact or a reason (`.pilot/pilot-link-architecture.md`): a fact (a version, a table) is a
   `reference` entry (`--verify` keeps those true), a reason for a choice is an ADR (`--adr`); say which and stop.
2. Call `Agent` for `pilot-architect` with `.pilot/pilot-task-architecture-guideline.md`,
   `.pilot/pilot-link-architecture.md`, the rule, `.pilot/pilot-link-knowledge.md` (the architect reads the entries that bear on it itself), the project's language (`pilot.py module list`) and the
   relevant code — nothing else from this conversation. Validate the returned JSON; fix or call again.
3. Show the draft, its `conflicts` and `questions` to the human, who edits and validates it (pair); `--auto` is not offered: a rule is a
   human's. A `questions` entry asking for a reason offers `--adr` after this run.
4. `arch add guidelines/<slug>.md … --status accepted` (`apps/<app>/guidelines/<slug>.md` when only one app is concerned), the ADR it names written as a
   line `Why: adr/<id>` at the end of the body. Branch `architecture/guideline-<slug>`, commit, push, open one PR.

## `--edit <id> "<change>"`

1. `arch show <id>`. An `accepted` ADR is never edited: say so and point at `--adr` (a new ADR that supersedes it), then stop. A `deprecated` or
   `superseded` entry is history: say so and stop. Anything else goes on.
2. Call `Agent` for `pilot-architect` with `.pilot/pilot-task-architecture-edit.md`,
   `.pilot/pilot-link-architecture.md`, the entry (kind, title, description, text, stamp), the change, `.pilot/pilot-link-knowledge.md` (the architect reads the entries that bear on it itself), the entry's language and the
   relevant code — nothing else from this conversation. Validate the returned JSON; fix or call again.
3. Show the result, its `conflicts` and `questions` to the human, who edits and validates it (pair); `--auto` is not offered: an entry is a
   human's.
4. Write the text under the frontmatter (the only hand-edited part), `arch set <id> --title … --description …` when they changed, and, when the entry was
   stamped, `arch set <id> --clear-stamp`: a changed `reference` entry or overview is offered `--verify <id>` after this run. Branch `architecture/edit-<id>`, commit, push, open one PR.

## `--deprecate <id>`

1. `arch show <id>`: tell the human which entries cite it (`backlinks`), and, for an ADR, that `--adr` is the way when a new decision replaces it.
2. The human confirms (pair); `--auto` is not offered.
3. A `proposed` entry is removed (`arch remove <id>`); an `accepted` one becomes `deprecated` (`arch set <id> --status deprecated`); another status: say so and stop.
   Branch `architecture/deprecate-<id>`, commit, push, open one PR.

## `--verify [<id>]`

Checks the `reference` entries (all, or `<id>`) and the overview against the code.
1. `arch lint`; its findings go in the report.
2. Call `Agent` for `pilot-techlead` with `.pilot/pilot-task-architecture-verify.md`, `.pilot/pilot-link-architecture.md`, those entries' text and
   stamps, and `git rev-parse HEAD` — nothing else from this conversation.
3. `ok` verdicts → `arch set <id> --stamp <commit>`. `unverifiable` keeps the old stamp.
4. Each `drift` goes to the human with the agent's evidence and its three outcomes (`.pilot/pilot-link-architecture.md`): propose the exact
   `/pilot-spec --bug "<description>"` when the code is wrong; edit the entry in this run's branch with the `corrections` when the human confirms it is stale or
   wrong (`arch set <id> --clear-stamp`, then `--stamp` on the corrected text); point at `/pilot-spec --tech` when the code must change on purpose.
   `--auto`: decide nothing, list every drift under "To arbitrate" in the PR and leave it unstamped.
   A fact in `undocumented` the human wants becomes a new `reference/<id>.md` (`arch add … --status accepted --stamp <commit>`).
5. Changes → branch `architecture/verify-<YYYY-MM-DD>`, commit, push, open one PR. Nothing to change → no PR.

## `--adr "<decision>"`

1. Check the decision meets the bar (`.pilot/pilot-link-architecture.md`: it outlives a ticket and someone could
   be tempted to reverse it); otherwise say it belongs in a guideline (a rule), a `reference` entry (a fact) or a ticket and stop.
2. Call `Agent` for `pilot-architect` with `.pilot/pilot-task-architecture-adr.md`,
   `.pilot/pilot-link-architecture.md`, the decision, `.pilot/pilot-link-knowledge.md` (the architect reads the entries that bear on it itself), the project's language (`pilot.py module list`) and the
   relevant code — nothing else from this conversation. Validate the returned JSON; fix or call again.
3. Show the draft to the human, who edits and validates it (pair); `--auto` is not offered: a decision is a
   human's.
4. `arch add adr/<NNNN-title>.md … --status proposed` (`apps/<app>/adr/<NNNN-title>.md` when only one app is concerned) (NNNN = `arch next-number`), and `arch supersede <new> <old>`
   when it replaces an accepted ADR. Branch `architecture/adr-<NNNN>`, commit, push, open one PR; the human
   merging it accepts it — set `accepted` in that same PR when the human says so.

## `--bootstrap`

For a project that already has apps and documents.
1. Inventory: `python3 .pilot/pilot.py arch inventory` — the apps, an outline (path, size, title, first line) of `docs/**` and of each app's
   `README.md`, `CLAUDE.md` and `docs/**`, and the state of the `PILOT:ARCHITECTURE`/`PILOT:COMMANDS` blocks of `CLAUDE.md` and `README.md`
   (`placeholder`, `pointer`, `filled` with the project's own content, `absent`). Nothing to gather → say so and propose `--scaffold`.
2. Call `Agent` for `pilot-architect` with `.pilot/pilot-task-architecture-bootstrap.md`, `.pilot/pilot-link-architecture.md`, the project's language (`pilot.py module list`), the inventory and
   `git rev-parse HEAD`; it opens only the documents it classifies as architecture or decision. Validate the returned JSON (paths `overview.md`,
   `guidelines/<id>.md`, `reference/<id>.md`, `runbooks/<id>.md` or the same under `apps/<app>/`, ids in `[a-z0-9-]+`, a one-sentence `description` and a `source` each); fix or call again.
3. The human confirms or edits each guideline; write them with `arch add … --status accepted`. A `reference` entry is written the same way with `--stamp <commit>`, the architect having read it in the code. A `decision` document becomes an ADR only once the human gives
   the reasoning (`--adr`); a `functional` document is listed for `/pilot-wiki --bootstrap`, not converted here.
4. Blocks: a `placeholder` block of `CLAUDE.md`/`README.md` is replaced by the canonical pointer (`pilot-architecture-*.md.tmpl`, `pilot-commands-*.md.tmpl`);
   a `filled` one too, once the human agrees, since its content is now in `architecture/`.
5. Branch `architecture/bootstrap`, commit, push, open one PR whose description lists the source documents now duplicated by an entry: the human decides
   whether each is kept, trimmed to a pointer or deleted — never deleted here.

## `--scaffold`

For a project with no apps yet. Gather the apps from the argument or by asking: how many, and each one's name,
purpose and technology. Defaults when the human has no preference: Clean Architecture (Domain → Use Cases →
Adapters → Infrastructure); Node.js + TypeScript backend (Express); React + TypeScript with Vite for the web;
Expo + TypeScript for mobile (ask whether web and mobile share one Expo app or are two); TypeScript everywhere.
For every framework or library introduced, read its latest stable compatible version from the registry
(`npm view <pkg> version`) and pin it. Create each `apps/<name>/` minimal but real (installable, with `dev`,
`build` and `test` scripts, a `README.md`): a backend gets `src/domain`, `src/application`, `src/adapters`,
`src/infrastructure`, `src/main.ts` and `tests/`; a Vite or Expo frontend its entry files, with a lighter layering.
Record the apps in `.pilot/state.json` (`apps`: `{name, purpose, stack}`), write `architecture/overview.md` (the apps,
how they relate, the per-app commands), replace a `placeholder` block of `CLAUDE.md`/`README.md` by the canonical pointer, then branch
`architecture/scaffold`, commit, push, open one PR.

## `--lint`

`arch lint`. Report its findings (unreadable entry, duplicate id, supersession that does not hold, stale index);
fix none silently. Fixes go in a branch `architecture/lint-<YYYY-MM-DD>` and one PR; nothing to change → no PR.

## Wrap-up

Report the PR (or "nothing to change") and what is left for the human. Never merge an architecture PR.
