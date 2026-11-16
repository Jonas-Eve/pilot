---
name: pilot-flow
description: "Tests one user flow of the project's wiki (wiki/user-flow/) as one or several user personas (wiki/persona/), in a browser against an environment URL, on demand only. --new persona|flow drafts a new persona or user flow with a human and opens one wiki PR. Each persona runs in its own isolated browser session with its own test account, in parallel when isolation holds; each step is passed, failed or untestable, with the friction that persona meets. A defect becomes a type:bug ticket (never duplicated across personas); friction and non-bugs go in a report kept as one private Artifact per flow, a new run added to its history. The dashboard shows each flow's last run and who played it. Claims no ticket, sets no status, never --auto. Use to check a journey end to end the way a given kind of user lives it."
argument-hint: "<user-flow id> [--as <persona id>[,<persona id>...]] [--url <environment URL>] | --new persona|flow <description>"
disable-model-invocation: true
---

# PILOT — user flow test

Read `.pilot/pilot-link-knowledge.md` (reading the wiki), `.pilot/pilot-link-wiki.md` and `.pilot/pilot-process.md` first. Not one of the five phases: no ticket is claimed, no label changes, no `--auto`, no Routine —
a human launches it. Two modes: a flow id runs it (below), `--new persona|flow <description>` drafts an entry (last section). The agent of a run is `pilot-qa` (`.pilot/pilot-task-flow-run.md` runs one persona through the flow, `.pilot/pilot-task-flow-report.md` consolidates).

## Steps

0. **Preflight**, once per session: `python3 .pilot/pilot.py doctor` — skip it if it already reported `ok: true` earlier in this conversation; `ok: false` or an error → report it and stop.
1. **Inputs.** The `wiki` module must be on (`python3 .pilot/pilot.py module list`; off → say so and stop). `python3 .pilot/pilot.py wiki show <flow id>` must be an entry of `type: UserFlow` (else say what it is, or
   that it does not exist, and stop). Personas: `--as`, else the ones the flow lists; none → ask the human. Each must be an entry of `type: Persona` (`wiki show`), else stop and name it.
2. **Prerequisites**, before any session starts (a failure → report it and stop, nothing has changed):
   - A browser the agent can drive: a browser tool of the session, else Playwright/Chromium through `Bash`.
   - The environment URL: `--url`, else the one the project documents — with the `architecture` module on, `python3 .pilot/pilot.py arch search "<environment URL staging>"` and the runbooks (`arch show`).
     Nothing found → ask the human for it and stop. Never guess one, never test production unless that URL was given.
   - One test account per persona the flow needs to log in as: the environment variables `PILOT_ACCOUNT_<ID>_USER` and `PILOT_ACCOUNT_<ID>_PASSWORD` (`<ID>` the persona id in capitals, dashes as underscores), checked with
     `[ -n "${VAR:-}" ]` and never printed. Missing → ask the human to set them in the environment, or give them in this conversation. Credentials are never written to the wiki, a ticket, a comment or a report.
3. **Isolation.** One persona is one independent session: its own browser context (Playwright `browser.newContext()`: its own cookies and storage), never a second tab of a profile another persona uses.
   Isolation guaranteed → run the personas in parallel; only a browser tool with one shared profile → run them one after the other, ending each session (logout, storage cleared) before the next, and say so in the report.
4. **Run.** One `Agent` call per persona, `subagent_type: "pilot-qa"`, with `.pilot/pilot-task-flow-run.md`, the flow entry's and that persona's entry's full text (`wiki show`), the URL and the names of its account variables
   (never their values). Parallel runs are all sent in one message. Each returns its per-step results (the JSON `.pilot/pilot-task-flow-run.md` defines); a persona whose session could not start returns that, not a guess.
5. **Consolidate.** One more `Agent` call, `pilot-qa`, with `.pilot/pilot-task-flow-report.md`, `.pilot/pilot-link-bug-tickets.md` in full, the flow's text and every persona's results. It returns what it did: the `type:bug`
   tickets it originated (one per root cause, whichever personas hit it), the findings that are not bugs, the friction by persona.
6. **Report.** Tell the human: a persona × step table (`passed`/`failed`/`untestable`), the bug tickets, each non-bug finding to raise via Discovery, the friction per persona, and whether the runs were parallel or
   sequential. Then keep it: one private Artifact per flow, named after the flow's title, found with the `Artifact` tool's `list` (a match on that title) and updated at the same address, else created (`quickstart` first, `intent: "other"`).
   Its latest run comes first, with the date, the URL tested, the personas (account labels, never credentials), the table, the tickets (linked), the non-bugs, the friction and the steps not run; the earlier runs stay below,
   newest first, so two runs can be compared. Never share it; the human decides. No `Artifact` tool, or a refusal → say so and give the report in the reply only.
   Nothing is written to the wiki: a flow is never stamped by a run.
7. **Dashboard** (best-effort; skipped silently when `.pilot/state.json` has no `dashboardUrl`, `modules.dashboard` is `false` or `ArtifactData` — `ToolSearch` loads it — is unavailable): write the personas' runs, the consolidation and the report's
   address (`reportUrl`) as `{"flow": …, "personas": […], "report": …, "reportUrl": …}` to a temporary file, `python3 .pilot/pilot.py flow doc --in <file> --out <doc file>`, then `ArtifactData` `set` on the dashboard's
   `flowRuns` collection, id `<owner>__<repo>__<flow id>` (`get` it first and pass `if_version` if it exists), `file_path` that document. Never read the dashboard back, never retry; mention a failure in the report only.

## `--new persona|flow <description>`

Pair only: a human is live. The `wiki` module is on, else say so and stop; preflight as above. A persona is drafted by `pilot-designer` (`.pilot/pilot-task-draft-persona.md`), a flow by `pilot-qa` (`.pilot/pilot-task-draft-flow.md`).

1. Read what exists, per `.pilot/pilot-link-knowledge.md`: the vision (`wiki show vision`), `wiki index --under persona`, `wiki index --under user-flow`, and for a flow `wiki search` on the description with `wiki show` of the few behaviors it
   touches. A persona or flow that already covers the description → say so and ask whether to revise it instead.
2. `Agent` call with the task doc, `.pilot/pilot-link-wiki.md` in full, the project's language (`pilot.py module list`), the description and what step 1 read (for a flow, every persona's id, title and description). It returns the draft and its
   questions (the JSON its task doc defines). Show both to the human, feed their answers back to a new call with the conversation as text, and repeat until they approve; each turn re-reads nothing else.
3. Check the approved draft: the id is `[a-z0-9-]+` and unused; a flow lists only existing persona ids (a missing one → offer `--new persona` first and stop here); no credential or secret anywhere in the text.
4. `python3 .pilot/pilot.py wiki add persona/<id>.md --type Persona --status implemented --title … --description … --body …` (a flow: `user-flow/<id>.md`, `--type UserFlow`). Branch `wiki/persona-<id>` or `wiki/flow-<id>`, commit, push, open one PR
   and report it. Never merge it: only a PR changes the wiki, a human merges it.
