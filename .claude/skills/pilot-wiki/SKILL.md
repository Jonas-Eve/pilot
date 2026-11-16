---
name: pilot-wiki
description: "The project's wiki (wiki/ at the project root, .pilot/pilot-link-wiki.md): the source of truth for what the product does and what is promised, read by agents and humans. No flag, or a question in free text → answers from the wiki with citations (path, status — including the in-flight status derived from the tickets), and says when the wiki does not cover it. --lint [domain|entry-id] → checks implemented entries against the code, stamps the conforming ones, and has a human arbitrate each divergence (the wiki is right, the code conforms); one PR per run. --edit <id> \"<change>\" → corrects an entry's wording or precision, one PR; a behavior change goes back to /pilot-discovery. --deprecate <id> → retires a proposed entry, a persona or a user flow, one PR. --bootstrap [domain] → drafts the wiki from closed tickets, accepted prototypes and the code, one PR per domain, entries where tickets and code agree already stamped, divergences left to the human. Pair by default (a human arbitrates live); --auto lists divergences in the PR instead and decides nothing. Never merges a PR, never claims a ticket. When the wiki module is off it proposes to turn it on first (and to bootstrap, if the project has tickets or code to document). Use to ask what the product does, to verify, correct or retire an entry, or to create the wiki."
argument-hint: "[<question>] | --lint [<domain or entry id>] [--auto] | --edit <id> \"<change>\" | --deprecate <id> | --bootstrap [<domain>] [--auto]"
---

# PILOT wiki — `pilot-wiki`

Read `.pilot/pilot-link-knowledge.md` (how to read the bundle) and `.pilot/pilot-link-wiki.md` (entry format, statuses, the rules below) first. Mechanics are
in `python3 .pilot/pilot.py wiki …` (`index`, `reindex`, `show`, `status`, `lint`, `add`, `set`, `remove`,
`migrate`); run the script, never hand-edit an entry's frontmatter or an `index.md`. Not one of the five phases: it
claims no ticket and changes no label.

## Preflight

Run `python3 .pilot/pilot.py doctor --no-wiki` once per session (the wiki check is the one this skill
repairs); stop with its report if it fails.

## The module

`python3 .pilot/pilot.py module list` tells whether the `wiki` module is on. Off, or `wiki/` missing: say so and
propose turning it on (`python3 .pilot/pilot.py module enable wiki`, then `python3 .pilot/pilot.py wiki
reindex`, which creates `wiki/` with its root `index.md`; then ask the human for the product's vision, 2-5 sentences,
and create it: `wiki add product/vision.md --type Vision --status implemented --title Vision --description "<one sentence>"
--body "<the vision>"`, in the wiki's language). On a yes, go on with what was asked; on a no, stop.
When the project has closed tickets or code to document, offer `--bootstrap` right after.

## Question (no flag)

1. Read per `.pilot/pilot-link-knowledge.md`: `wiki index --depth 1`, then `wiki search` or a folder, then `wiki show` only those that bear on the question.
2. Answer from them, citing each as its `path` with its `display` status (e.g. `specified · in-review`).
   A `proposed`/`specified` entry is a promise, not behavior: say so. Where the wiki is silent,
   say it is not covered; do not fill the gap from the code.

## `--edit <id> "<change>"`

Pair only: a human is live (`--auto` is not offered).
1. `wiki show <id>`. A `Persona` or `UserFlow` → point at `/pilot-flow --edit <id> "<change>"` and stop. A `deprecated` entry is history: say so and stop.
2. Call `Agent` for `pilot-pm` with `.pilot/pilot-task-wiki-edit.md`, `.pilot/pilot-link-wiki.md` in full, the entry (status, tickets, text), the change and the wiki's language (`pilot.py module list`)
   — nothing else from this conversation. Validate the returned JSON; fix or call again.
3. `behavior-change` → give the human the reason and point at `/pilot-discovery "<change>"`; write nothing and stop. `correction` → show the new text against the old and
   the `questions`; the human edits and validates it.
4. Replace the prose below the entry's frontmatter by hand, `wiki set <id> --title … --description …` when they changed; status and tickets stay as they are. A stamped entry:
   `wiki set <id> --clear-stamp`, and offer `--lint <id>` after this run. Branch `wiki/edit-<id>`, commit, push, open one PR. Never merge it.

## `--deprecate <id>`

Pair only: a human is live.
1. `wiki show <id>`; tell the human which entries cite it (`backlinks`). A `Persona` or `UserFlow` is retired directly (a flow that lists a retired persona is named for revision with `/pilot-flow --edit`).
   A `proposed` entry whose tickets are all closed or absent is removed. A `proposed` entry with an open ticket: point at that ticket (its story is `wont-do`) and stop.
   A `specified` or `implemented` entry, or the `Vision`: a product decision, not a button — point at `/pilot-discovery` (a story that removes a behavior deprecates the entry that states it) and stop.
2. The human confirms.
3. Retire: `wiki set <id> --status deprecated`; remove: `wiki remove <id>`. Branch `wiki/deprecate-<id>`, commit, push, open one PR. Never merge it.

## `--lint [target]`

1. `wiki lint`. Its findings (unreadable entry, duplicate id, orphaned promise, …) go in the
   report; fix none of them silently.
2. Entries to verify: `implemented` ones (all, or `target`), except the `Vision` entry (`type: Vision`) and the `Persona`/`UserFlow` entries, which no code verifies. Call `Agent` for `pilot-techlead`
   with `.pilot/pilot-task-wiki-lint.md`, `.pilot/pilot-link-wiki.md`, those entries' text and
   stamps, and `git rev-parse HEAD` — nothing else from this conversation.
3. `ok` verdicts → `wiki set <id> --stamp <commit>`. `drift`/`unverifiable` keep their old stamp.
4. Each `drift` goes to the human with the agent's evidence and its three outcomes
   (`.pilot/pilot-link-wiki.md`): propose the exact `/pilot-spec --bug "<description>"` when the
   code is wrong; edit the entry in this run's branch when the human confirms a pure correction;
   point at `/pilot-discovery` when the wiki must change behavior. `--auto`: decide nothing,
   list every drift under "To arbitrate" in the PR and leave it unstamped.
5. Wiki changes (stamps, confirmed corrections) → branch `wiki/lint-<YYYY-MM-DD>`, commit, push,
   open one PR. Nothing to change → no PR.

## `--bootstrap [domain]`

1. A domain is a functional area of the product (a folder of `wiki/`, e.g. `search/`), never a kind
   of document (`persona/` and `user-flow/` are not domains: leave them out). Domains: the given one, else propose the list — one per `level:epic` ticket
   (its stories are the domain's tickets), and for stories under no epic, the areas the tickets and
   the code suggest — and have the human confirm it; `--auto` takes the proposal as is.
2. Per domain, gather the intent: closed tickets at `status:done` and prototypes at
   `status:poc-validated` that belong to it (`gh issue list`/`gh issue view`, with comments), and
   where its code lives. Nothing to gather → skip the domain, say so.
3. Call `Agent` for `pilot-techlead` with `.pilot/pilot-task-wiki-bootstrap.md`,
   `.pilot/pilot-link-wiki.md`, the project's language (`pilot.py module list`), that material and `git rev-parse HEAD`. Validate the returned JSON
   (paths `<domain>/<id>.md` with the id in `[a-z0-9-]+` and no id already in the wiki, a one-sentence
   `description` each); fix or call again.
4. Write per triage:
   - `convergent` → `wiki add <path> --title … --description … --status implemented --ticket …`, then `wiki set <id> --stamp <commit>`.
   - `divergent` → ask the human the entry's `question`; what they settle decides the entry's text
     (then add and stamp it) or a `/pilot-spec --bug`. `--auto`: add unstamped, list under "To arbitrate".
   - `code-only` → add unstamped, listed as "undocumented"; the human may drop it.
   - `tickets-only` → ask the human: never delivered (add as `specified`, or open a ticket) or
     removed (add as `deprecated`, or skip). `--auto`: list under "To arbitrate", add nothing.
5. Branch `wiki/bootstrap-<domain>`, commit, push, open one PR whose description lists "To arbitrate"
   first, then summarizes the convergent entries (count, examples, each with its two proofs).

## Wrap-up

Report the PR (or "nothing to change") and what is left for the human. Never merge a wiki PR.
