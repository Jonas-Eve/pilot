---
name: pilot-qa
description: "Phase 5 of PILOT: human QA for a type:feature story at status:qa (every task merged, the e2e one included). Builds a manual test plan from the acceptance criteria and the merged tasks, walks a human through it live and reports: a full pass sets status:done; a genuine defect becomes a type:bug ticket and the story goes back to status:qa; an unclassifiable failure gets the needs-human flow. Pair by default; --browser --url <URL> runs the cases itself in a browser and closes the story only if every case was tested and passed, else leaves it to a human. --resume <issue> [--browser] continues a ticket from its test log, --with designer; bare, it picks the next status:qa or can-resume ticket. Use once a story's tasks have all merged."
argument-hint: "<issue number, optional — picks the next fresh status:qa or resumable status:in-qa ticket if omitted> [--with designer] [--browser [--url <environment URL>]] | --resume <issue number> [--browser [--url <environment URL>]]"
disable-model-invocation: true
---

# PILOT — Phase 5: Human QA

Read `.pilot/pilot-process.md` before running this if you haven't already — it's the source
of truth for labels, states, and the claim protocol, and the "Phase 5 — Human QA" section below covers this phase;
this skill only covers the mechanics of running it. `.pilot/pilot-link-ticket-tree.md` (the levels) and `.pilot/pilot-link-cascade.md` (what sets `status:qa` and `status:done`) complete it. The roster (`.pilot/pilot-link-roster.md` "Roster"): `pilot-qa` leads, no validator (the human is; none in `--browser`), the designer is summonable. Summons and
dismissals are recorded in the test-log comment; `.pilot/pilot-task-advise.md` is passed into its call.

## Steps

0. **Preflight**, once per session: `python3 .pilot/pilot.py doctor` — skip it if it already reported `ok: true` earlier in this conversation. `ok: false` (exit 1) or a failure (exit 2, script missing) → report each entry of `failed` (or the error) and stop here, before anything has changed.
1. Determine the input: `python3 .pilot/pilot.py resolve qa <issue> [--resume]` (or `pool qa`; a refusal `phase-not-in-profile`:
   this project's workflow has no human QA — say so and stop). With no issue
   given, run `python3 .pilot/pilot.py pool qa` first — the pool of
   `.pilot/pilot-process.md` §4 "Picking the next ticket..." (fresh `status:qa`, resumable
   `status:in-qa` + `can-resume`; `needs-human`, `on-hold` and open "Depends on #N" excluded;
   priority, then "Blocks #M", then oldest). `pick: null` → report nothing to do; otherwise
   the pool has already resolved its pick: act on `pick.action` (pair unless `--browser` is given, never the ticket's `mode`, `.pilot/pilot-process.md` §4 "Interaction modes"). A `--auto` or `--human` given to `/pilot-qa` itself is not a QA flag: say that QA runs in pair or with `--browser`, and stop before anything else:
   - `claim-fresh` → step 2 (mode `fresh`). Under `--browser`, `resume-cleared` (a human cleared `needs-human` and set `can-resume`) and `resume-orphaned` (only with `--resume`, a human's explicit call that the claim is orphaned) go on as in pair, from the test log (step 5); `ask-resume` still stops and asks for `--resume`.
   - `resume-orphaned` (`--resume`: a session left mid-pair) or `resume-cleared`
     (`can-resume`: a human cleared `needs-human`) → step 2 (mode of the same name), then
     read the ticket and thread to reconstruct which cases were already confirmed (and, for
     `resume-cleared`, the blocking point's resolution) and skip to step 5 with that state —
     never restart the test plan from step 3/4 (`.pilot/pilot-process.md` §4 "Resuming an
     orphaned claim", "Resuming a `needs-human` ticket").
   - `ask-resume` → looks like a session left mid-pair; report and ask the human to re-run
     with `--resume`, or add `can-resume` themselves.
   - `stop` → report `reason` and stop: `depends-on-open` (name the `depends_on` ticket),
     `flagged` (unresolved `needs-human`/`on-hold`), `wrong-status` (not `status:qa` —
     `status:split`, `status:done`, a type that never reaches it, `.claude/skills/pilot-qa/SKILL.md`
     "When it fires"), `assigned`, `closed`, `not-found`.
   Script missing or exiting 2 → report that and stop: `.pilot/pilot.py` ships with
   `/pilot-init`/`/pilot-update` and needs `python3` and a working `gh`.
1a. **`--browser` prerequisites**, before anything is claimed (any failure → report it and stop, nothing has changed):
   - A browser the agent can drive: a browser tool of the session, else Playwright/Chromium through `Bash`.
   - The environment URL: `--url`, else the one the project documents — when the `architecture` module is enabled, `python3 .pilot/pilot.py arch search "<environment URL staging>"` and the
     runbooks' entries (`arch show`). Nothing found → ask the human for it (`/pilot-qa --browser --url <URL>`) and stop; never guess a URL, never test a production environment unless that URL was given.
   - The story's test account, if a case needs a login: the environment variables `PILOT_ACCOUNT_QA_USER` and `PILOT_ACCOUNT_QA_PASSWORD`, checked with `[ -n "${VAR:-}" ]` and never printed; else the human may give them, which you write to a
     mode-600 file in the session's scratchpad (deleted when the run ends) and pass its path, never the values, to the agent. Never invented: a case needing a login with none is untestable (step 4). Credentials, tokens and personal data seen in the environment never go into the test log.
2. **Claim** it: `python3 .pilot/pilot.py claim qa <issue> --mode <mode>` (the mode named in
   step 1) — it applies `.pilot/pilot-process.md` §4 "Claim Protocol" (assignee +
   `status:in-qa`, re-read to confirm). Any refusal (`lost-race`, `not-claimable`, …) →
   report `reason` and stop.
2a. **Dashboard** (best-effort): per `.pilot/pilot-link-dashboard.md`, push the `event`/`activity` that `pilot.py claim|set|flag|unflag` return, with `ArtifactData` (`ToolSearch` loads it if deferred) — skipped silently when `dashboardUrl` is absent from `.pilot/state.json`.
3. Gather context: the story's own body (acceptance criteria) and, for each of its dev and
   e2e tasks, the spec (phase 2) and the merged PR (`mcp__github__issue_read`,
   `mcp__github__pull_request_read`) — not the running conversation history. When the `wiki` module is enabled (`.pilot/pilot-process.md` §8), also the story's entries (`python3 .pilot/pilot.py wiki index --ticket <issue>`, each
   with `wiki show <id>`).
4. Call the `Agent` tool with `subagent_type: "pilot-qa"` (`--browser`: with the URL and the instruction to run the cases itself — `.pilot/pilot-task-human-qa.md` "`--browser`"). Read `.pilot/pilot-task-human-qa.md`
   and pass its content as part of the prompt, plus `.pilot/pilot-link-bug-tickets.md` in
   full (the classify/originate mechanic for step 3's "real-bug failures" case — the task
   doc covers the phase-5-specific delta itself), along with that context (and `.pilot/pilot-link-knowledge.md` and `.pilot/pilot-link-wiki.md`
   in full when the wiki module is enabled). The agent
   returns a manual test plan: concrete cases and how to test each.
5. **`--browser`:** after a resume the agent is given the test log and the resolution comment: it retests nothing already `passed`, and a case the log marks `untestable` stays so unless the resolution says how to test it. The agent runs every case itself and returns one result per case and a coverage list (each acceptance criterion with the cases that cover it); write both as the one test-log comment (below, never collapsed) and go to step 6. **Pair:** walk the human through it: show the plan, then go case by
   case — ask them to run one, report what happened, feed that back to the agent, move to
   the next — until every case is reported. Keep one running comment updated in place
   (`mcp__github__update_issue_comment` — create it once, append each case's result to it)
   rather than posting a new comment per case, the same incremental-checkpoint discipline
   every pair-mode phase follows (`.pilot/pilot-process.md` §4 "Interaction modes") — this
   is what makes `--resume` possible if the session ends before a final verdict. Unlike
   Spec's or Dev's scratch checkpoints, **don't collapse this one once the verdict lands**
   — it's the actual test log (what was tried, case by case, and what happened), the one
   place that record exists at all, not work-in-progress toward some other final
   artifact.
6. Apply the agent's verdict:
   - **Approved** (every case confirmed, or every failure resolved to "not actually a
     bug"; in `--browser`, only when every case was tested and passed and every acceptance criterion of the story has at least one passed case in the coverage list — a single untested case, an uncovered criterion, a failure not classified as a bug, or an unsure result is never an approval): `python3 .pilot/pilot.py set <issue> --status done --close` — the one
     phase that sets `status:done` directly, since there's no PR merge here for
     `.github/workflows/pilot-status-on-merge.yml` to react to, and nothing to cascade (a
     `type:feature` story is never itself a task of another `status:split` parent).
     Include any "not actually a bug" finding in the report to the human (step 7) — they
     raise it via Discovery themselves.
   - **One or more real-bug failures**: nothing further to set — the agent already
     originated the `type:bug` ticket(s), directly as `level:task`/`status:backlog`
     (never split, `.pilot/pilot-link-ticket-tree.md` "Three levels"), commented naming
     them, cleared the assignee, and moved the story back to `status:qa` itself, the same
     pattern `pilot-dev`/`pilot-e2e` use for a bug found mid-implementation
     (`.pilot/pilot-link-bug-tickets.md`). Takes priority over a same-pass "not actually a
     bug" failure — don't set `status:done` while a real bug is open. It's now an ordinary
     `status:qa` candidate again, gated only by the dependency (step 1's last bullet) — no
     flag to clear, no `--resume` needed; whichever future run claims it starts a fresh test plan.
   - **A failure still unresolved**: the agent already applied `needs-human` with a
     comment listing what failed and why, the moment it couldn't classify it
     (`.pilot/pilot-process.md` §3 "`needs-human`" — label and comment go on immediately,
     never held back on the chance a human answers right away). `status:in-qa` stays.
     Should be rare — the human who can answer is normally right there in step 5, in
     which case the agent posts the resolution and clears the flag itself in the same
     turn, and you'll see the approved/bug outcome instead.
   - **`--browser`, some case untestable by the agent** (needs a real device, a screen reader, a judgment on the experience, a credential the project does not document) with no real bug originated in the same pass (a bug takes precedence: the untestable cases are only named in its unclaim comment, no `needs-human`, and the next run plans afresh): the agent applied `needs-human` with a comment naming those cases and why; `status:in-qa` stays, the test log holds the tested ones. A human clears the flag and `/pilot-qa --resume`
     (pair) tests only what is left (step 1's `resume-cleared`).
   - **Wiki stamps** (only when the `wiki` module is enabled, with an approved outcome): for each of the story's entries (`python3 .pilot/pilot.py wiki index --ticket <story>`) that is `implemented`, unstamped and returned
     `passed` by the agent, after `git fetch origin <default branch>`, run `python3 .pilot/pilot.py wiki set <id> --stamp $(git rev-parse origin/<default branch>) --by process:pilot-qa` (the commit that was tested: the default branch's head) on branch
     `wiki/qa-<story>`, commit, push, open one PR (`mcp__github__create_pull_request`) listing the entries and give the human its link — never merge it. An entry with a case that failed or could not be tested,
     or already stamped, is left as it is.
   These can land in the same pass — apply what applies; each is independent
   (`.pilot/pilot-process.md` §3).
7. Report the outcome (approved + closed, any not-a-bug finding to raise via Discovery, bug
   ticket(s) originated, and/or unresolved findings) back to the human. Never invoke
   `pilot-e2e`/`pilot-dev` from this skill — a `type:bug` ticket the agent originates is
   already `status:backlog`, `/pilot-spec` picking it up next from that pool whenever it
   next runs, never handed off to phase 3 directly from here.

Do not run this against a `type:tech`/`type:bug` ticket, or against a task itself —
neither ever reaches `status:qa` (`.claude/skills/pilot-qa/SKILL.md` "When it fires").

## Phase 5 — Human QA (`type:feature` only)

Every other phase in this document is agent-driven, code-level work. Phase 5 is neither:
it's the shipped, integrated feature exercised in a real environment and judged on whether it
actually behaves as intended, not just on the diff. By default a human does it; with `--browser` the agent
does it in a browser, and whatever needs a real person's judgment on the experience stays for one. `type:tech`/`type:bug` tickets never reach this phase: a `type:tech` split
cascades straight to `status:done` once all its tasks are done (`.pilot/pilot-link-cascade.md` "Cascading completion"); a `type:bug` ticket — always a standalone `level:task`, never split (`.pilot/pilot-link-ticket-tree.md` "Three levels") — reaches `status:done` directly once its own PR merges.

## When it fires

Set by `.pilot/pilot-link-cascade.md` "Cascading completion": once a `type:feature` story's e2e task (and therefore
every dev sibling it depends on, per `.pilot/pilot-link-e2e-tasks.md`) reaches `status:done`,
the story itself lands on `status:qa` instead of `status:done` — unclaimed, unassigned,
the pool `/pilot-qa` picks from.

## Running it

`/pilot-qa` is pair, or `--browser` with an environment URL (`.pilot/pilot-process.md` §4 "Interaction modes"). It claims the story (`.pilot/pilot-process.md` §4 "Claim
Protocol": `status:qa` → `status:in-qa`), builds a manual test plan, and walks the human
through it case by case (`--browser`: the agent runs it in a browser itself). A failure is classified and handled exactly as
`.pilot/pilot-link-bug-tickets.md` describes — a genuine defect gets its own
`type:bug` ticket (via the same single mechanism every other phase uses) and unclaims the
story back to `status:qa`; a non-bug failure is reported
for the human to raise via Discovery themselves; anything unclassifiable is a live
`needs-human` block (in `--browser`, a block left for a human) (`.pilot/pilot-process.md` §3 "A human is live in the same session"). Confirmed, or every
failure resolved to "not actually a bug" → `status:done`, the one direct exception `.pilot/pilot-process.md` §3
"`status:done`" already notes. `pilot-qa/SKILL.md` covers the rest of the mechanics.
