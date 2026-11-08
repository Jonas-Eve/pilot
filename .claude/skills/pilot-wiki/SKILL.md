---
name: pilot-wiki
description: "The project's wiki (wiki/ at the project root, .pilot/pilot-link-wiki.md): the source of truth for what the product does and what is promised, read by agents and humans. No flag, or a question in free text → answers from the wiki with citations (path, status — including the in-flight status derived from the tickets), and says when the wiki does not cover it. --lint [domain|entry-id] → checks implemented entries against the code, stamps the conforming ones, and has a human arbitrate each divergence (the wiki is right, the code conforms); one PR per run. --bootstrap [domain] → drafts the wiki from closed tickets, accepted prototypes and the code, one PR per domain, entries where tickets and code agree already stamped, divergences left to the human. Pair by default (a human arbitrates live); --auto lists divergences in the PR instead and decides nothing. Never merges a PR, never claims a ticket. When the wiki module is off it proposes to turn it on first (and to bootstrap, if the project has tickets or code to document). Use to ask what the product does, to verify the wiki, or to create it."
argument-hint: "[<question>] | --lint [<domain or entry id>] [--auto] | --bootstrap [<domain>] [--auto]"
---

# PILOT wiki — `pilot-wiki`

Read `.pilot/pilot-link-wiki.md` first (entry format, statuses, the rules below). Mechanics are
in `python3 .pilot/pilot.py wiki …` (`index`, `reindex`, `show`, `status`, `lint`, `add`, `set`, `remove`,
`migrate`); run the script, never hand-edit an entry's frontmatter or an `index.md`. Not one of the five phases: it
claims no ticket and changes no label.

## Preflight

Run `python3 .pilot/pilot.py doctor --no-wiki` once per session (the wiki check is the one this skill
repairs); stop with its report if it fails.

## The module

`python3 .pilot/pilot.py module list` tells whether the `wiki` module is on. Off, or `wiki/` missing: say so and
propose turning it on (`python3 .pilot/pilot.py module enable wiki`, then `python3 .pilot/pilot.py wiki
reindex`, which creates `wiki/` with its root `index.md`). On a yes, go on with what was asked; on a no, stop.
When the project has closed tickets or code to document, offer `--bootstrap` right after.

## Question (no flag)

1. `wiki index` for the entries; open (`wiki show <id>`) only those that bear on the question.
2. Answer from them, citing each as its `path` with its `display` status (e.g. `specified · in-review`).
   A `proposed`/`specified` entry is a promise, not behavior: say so. Where the wiki is silent,
   say it is not covered; do not fill the gap from the code.

## `--lint [target]`

1. `wiki lint`. Its findings (unreadable entry, duplicate id, orphaned promise, …) go in the
   report; fix none of them silently.
2. Entries to verify: `implemented` ones (all, or `target`). Call `Agent` for `pilot-techlead`
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
   of document. Domains: the given one, else propose the list — one per `level:epic` ticket
   (its stories are the domain's tickets), and for stories under no epic, the areas the tickets and
   the code suggest — and have the human confirm it; `--auto` takes the proposal as is.
2. Per domain, gather the intent: closed tickets at `status:done` and prototypes at
   `status:poc-validated` that belong to it (`gh issue list`/`gh issue view`, with comments), and
   where its code lives. Nothing to gather → skip the domain, say so.
3. Call `Agent` for `pilot-techlead` with `.pilot/pilot-task-wiki-bootstrap.md`,
   `.pilot/pilot-link-wiki.md`, that material and `git rev-parse HEAD`. Validate the returned JSON
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
