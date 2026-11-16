---
name: pilot-flow
description: "Tests one user flow of the project's wiki (wiki/user-flow/) as one or several user personas (wiki/persona/), in a browser against an environment URL, on demand only. Each persona runs in its own isolated browser session with its own test account, in parallel when isolation holds; each step is passed, failed or untestable, with the friction that persona meets. A defect becomes a type:bug ticket (never duplicated across personas); friction and non-bugs go in the report. Claims no ticket, sets no status, never --auto. Use to check a journey end to end the way a given kind of user lives it."
argument-hint: "<user-flow id> [--as <persona id>[,<persona id>...]] [--url <environment URL>]"
disable-model-invocation: true
---

# PILOT — user flow test

Read `.pilot/pilot-link-knowledge.md` (reading the wiki), `.pilot/pilot-link-wiki.md` and `.pilot/pilot-process.md` first. Not one of the five phases: no ticket is claimed, no label changes, no `--auto`, no Routine —
a human launches it. The agent is `pilot-qa` (`.pilot/pilot-task-flow-run.md` runs one persona through the flow, `.pilot/pilot-task-flow-report.md` consolidates).

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
6. **Report** to the human: a persona × step table (`passed`/`failed`/`untestable`), the bug tickets, each non-bug finding to raise via Discovery, the friction per persona, and whether the runs were parallel or sequential.
   Nothing is written to the wiki: a flow is never stamped by a run.
