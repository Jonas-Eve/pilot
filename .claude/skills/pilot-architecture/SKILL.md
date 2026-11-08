---
name: pilot-architecture
description: "The project's architecture (architecture/ at the project root, .pilot/pilot-link-architecture.md): overview of the apps, the technical guidelines AIs and developers must respect, and the architecture decision records (ADR: why a choice was made). No flag, or a question in free text → answers from it with citations (path, status), and says when it does not cover it. --adr \"<decision>\" → drafts an ADR with the architect and a human, one PR; an ADR that replaces an accepted one supersedes it. --bootstrap → drafts overview and guidelines from the existing apps/ and CLAUDE.md, one PR. --scaffold → creates the apps' skeletons (apps/<name>/, latest compatible versions) and the overview. --lint → mechanical checks. Never merges a PR, never claims a ticket. When the architecture module is off it proposes to turn it on first. Use to ask how the project is built and why, to record a decision, or to set the architecture up."
argument-hint: "[<question>] | --adr \"<decision>\" | --bootstrap | --scaffold [<free-text apps and tech>] | --lint"
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

## `--adr "<decision>"`

1. Check the decision meets the bar (`.pilot/pilot-link-architecture.md`: it outlives a ticket and someone could
   be tempted to reverse it); otherwise say it belongs in a guideline or a ticket and stop.
2. Call `Agent` for `pilot-architect` with `.pilot/pilot-task-architecture-adr.md`,
   `.pilot/pilot-link-architecture.md`, the decision, `.pilot/pilot-link-knowledge.md` (the architect reads the entries that bear on it itself) and the
   relevant code — nothing else from this conversation. Validate the returned JSON; fix or call again.
3. Show the draft to the human, who edits and validates it (pair); `--auto` is not offered: a decision is a
   human's.
4. `arch add adr/<NNNN-title>.md … --status proposed` (NNNN = the next number), and `arch supersede <new> <old>`
   when it replaces an accepted ADR. Branch `architecture/adr-<NNNN>`, commit, push, open one PR; the human
   merging it accepts it — set `accepted` in that same PR when the human says so.

## `--bootstrap`

1. Gather the material: the apps (`apps/`, `apps` in `.pilot/state.json`), their manifests and READMEs, the
   `PILOT:ARCHITECTURE`/`PILOT:COMMANDS` blocks and the technical rules of `CLAUDE.md`. Nothing to gather →
   say so and propose `--scaffold`.
2. Call `Agent` for `pilot-architect` with `.pilot/pilot-task-architecture-bootstrap.md`,
   `.pilot/pilot-link-architecture.md`, that material and `git rev-parse HEAD`. Validate the returned JSON
   (paths `overview.md` or `guidelines/<id>.md`, ids in `[a-z0-9-]+`, a one-sentence `description` each);
   fix or call again.
3. The human confirms or edits each guideline; write them with `arch add … --status accepted`.
4. Branch `architecture/bootstrap`, commit, push, open one PR.

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
how they relate, the per-app commands), then branch `architecture/scaffold`, commit, push, open one PR.

## `--lint`

`arch lint`. Report its findings (unreadable entry, duplicate id, supersession that does not hold, stale index);
fix none silently. Fixes go in a branch `architecture/lint-<YYYY-MM-DD>` and one PR; nothing to change → no PR.

## Wrap-up

Report the PR (or "nothing to change") and what is left for the human. Never merge an architecture PR.
