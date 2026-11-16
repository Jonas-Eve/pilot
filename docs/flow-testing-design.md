# Testing a user flow as a persona — design

Human-facing; no skill or agent reads it. The command is `/pilot-flow` (`.claude/skills/pilot-flow/SKILL.md`).

## Why not a ticket

`/pilot-qa` checks one story's acceptance criteria. A journey (book a trip, change it, get help on the way) crosses stories, and what a person with a constraint lives in it is not in any criterion. The flow is therefore
a wiki entry, not a ticket: nothing is claimed, no status moves, and a run never stamps it.

## The two folders

`wiki/persona/<id>.md` — `type: Persona`, `--status implemented`, no ticket. The prose says who the person is, what they need and the constraints a test must reproduce (device, assistive technology, language, ease with
digital tools), and names the test account by a label. Credentials never live in the wiki: `PILOT_ACCOUNT_<ID>_USER` / `PILOT_ACCOUNT_<ID>_PASSWORD` in the environment (`<ID>` the persona id in capitals, dashes as underscores),
or given by the human at run time.

`wiki/user-flow/<id>.md` — `type: UserFlow`, same status. The prose gives the journey's goal, a `Personas:` line (ids), where it starts, then numbered steps, each `do → expect`.

```
wiki add persona/marie-senior.md --status implemented --title "Marie, 74, low vision" --description "Senior, uses the phone at 200 % zoom, wary of forms." --body "…"
wiki add user-flow/book-assisted-trip.md --status implemented --title "Book an assisted trip" --description "From search to confirmation with assistance requested." --body "…"
```

`persona/` and `user-flow/` are not functional domains: `/pilot-wiki --lint` and `--bootstrap` and the entries a story writes leave them out (`assets/docs/pilot-link-wiki.md`). A flow is up to 800 words, a persona 400.

## Independent sessions

Two tabs of one browser share cookies, so two accounts cannot run side by side in them. Each persona gets its own browser context (Playwright `browser.newContext()`), which is why the runs go in parallel only when that
isolation is available; with a single shared profile they run one after the other.

## Launching from the dashboard

The Wiki tab shows a launcher under each `user-flow/` and `persona/` entry. On a flow: the personas it lists are pre-picked, pick others or fewer, optionally give an environment address; on a persona: choose the flow.
Either way the page writes `/pilot-flow <flow> --as <personas> [--url <URL>]` and opens it in Claude Code, like the other buttons: written, not sent. Only an http(s) address is passed on. The snapshot carries each
entry's `type` (a dashboard published before that falls back to the folder name), and the flow's persona list is read from its `Personas:` line.

## Creating them, and the state of a flow

The dashboard's Wiki tab has a card to create a persona or a user flow: it writes `/pilot-flow --new persona|flow <description>` and opens it in Claude Code. The designer drafts a persona, `pilot-qa` a flow (its steps grounded in the
wiki's behaviors, what the wiki does not say listed as gaps), both with the human live, and the result is one wiki PR a human merges.

After each run `pilot.py flow doc` builds a `flowRuns` document (the flow, when, each persona with its result, the bugs, the report's address, and a short hash of the text of the flow and of every persona that played). The skill
writes it to the dashboard, and the flow's row shows: *jamais joué*, or the result (passé / partiel / échec), when, each persona with its result, and *à rejouer* as soon as the flow or a persona that played has changed since. The page
only reads this document: it never writes the wiki, and a dashboard published before the `flowRuns` rule needs `/pilot-update` to receive it.

## A flow shares the wiki's life cycle

That is why flows live in the wiki: a story that creates or changes a journey lists it as one of its entries, Spec moves it to `specified`, and the Dev PR whose task completes it (every other task it lists is closed) moves it to
`implemented`, with no step of its own. Its text then differs from the last run's hash, so the dashboard shows it *à rejouer*.

## The report

The chat reply is the immediate answer; the durable one is a private Artifact per flow (found by its title, updated at the same address), with the latest run first and the earlier runs below it so regressions
show. It holds what no ticket keeps: the persona × step table, the friction, the non-bugs and the steps not run. Bugs live in their tickets, linked from the page. It is not a dashboard tab and is not committed to the repo.

## Not done yet

Flows where two personas interact (a carer and the person they assist), and running several flows for one persona in one command.
