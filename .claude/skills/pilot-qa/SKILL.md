---
name: pilot-qa
description: "Phase 5 of PILOT (see .pilot/pilot-process.md): human QA for a type:feature story once every task — including its mandatory e2e one — has merged (status:qa). Builds a manual test plan from the story's acceptance criteria and merged tasks, walks a human through testing it live, and reports the verdict. Pair-only, no --auto, never Routine-driven. On a full pass, or once every failure resolves to not-a-bug, sets status:done and closes the issue (reports any not-a-bug finding to the human to raise via Discovery). On a genuine defect, originates a type:bug ticket via PILOT's one shared bug-creation mechanism and unclaims the story itself (back to status:qa) — same mechanics as a bug found mid-implementation in phase 3. An unclassifiable failure gets the standard needs-human flow (label + comment posted immediately, per .pilot/pilot-process.md §3 — resolved and cleared live in the same turn when the human answers right there, since this phase is always pair). Also resumes a ticket left mid-pair with --resume <issue number>, and bare (no argument) picks up the next status:qa (fresh) or can-resume-marked status:in-qa ticket, skipping anything on-hold. Use once a type:feature story's tasks have all merged and it's ready for a human to confirm the shipped behavior."
argument-hint: "<issue number, optional — picks the next fresh status:qa or resumable status:in-qa ticket if omitted> [--with designer] | --resume <issue number>"
disable-model-invocation: true
---

# PILOT — Phase 5: Human QA

Read `.pilot/pilot-process.md` before running this if you haven't already — it's the source
of truth for labels, states, and the claim protocol, and the "Phase 5 — Human QA" section below covers this phase;
this skill only covers the mechanics of running it. `.pilot/pilot-link-ticket-tree.md` (the levels) and `.pilot/pilot-link-cascade.md` (what sets `status:qa` and `status:done`) complete it. The roster (`.pilot/pilot-link-roster.md` "Roster"): `pilot-qa` leads, no validator (the human is), the designer is summonable. Summons and
dismissals are recorded in the test-log comment; `.pilot/pilot-task-advise.md` is passed into its call.

## Steps

0. **Preflight**, once per session: `python3 .pilot/pilot.py doctor` — skip it if it already reported `ok: true` earlier in this conversation. `ok: false` (exit 1) or a failure (exit 2, script missing) → report each entry of `failed` (or the error) and stop here, before anything has changed.
1. Determine the input: `python3 .pilot/pilot.py resolve qa <issue> [--resume]`. With no issue
   given, run `python3 .pilot/pilot.py pool qa` first — the pool of
   `.pilot/pilot-process.md` §4 "Picking the next ticket..." (fresh `status:qa`, resumable
   `status:in-qa` + `can-resume`; `needs-human`, `on-hold` and open "Depends on #N" excluded;
   priority, then "Blocks #M", then oldest). `pick: null` → report nothing to do; otherwise
   resolve `pick.number` the same way. No `--auto`, never Routine-driven
   (`.pilot/pilot-process.md` §4 "Interaction modes", "Scheduled sweeps"). Act on the
   returned `action`:
   - `claim-fresh` → step 2 (mode `fresh`).
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
2. **Claim** it: `python3 .pilot/pilot.py claim qa <issue> --mode <mode>` (the mode named in
   step 1) — it applies `.pilot/pilot-process.md` §4 "Claim Protocol" (assignee +
   `status:in-qa`, re-read to confirm). Any refusal (`lost-race`, `not-claimable`, …) →
   report `reason` and stop.
2a. **Dashboard** (best-effort): per `.pilot/pilot-link-dashboard.md`, push the `event`/`activity` that `pilot.py claim|set|flag|unflag` return, with `ArtifactData` (`ToolSearch` loads it if deferred) — skipped silently when `dashboardUrl` is absent from `.pilot/state.json`.
3. Gather context: the story's own body (acceptance criteria) and, for each of its dev and
   e2e tasks, the spec (phase 2) and the merged PR (`mcp__github__issue_read`,
   `mcp__github__pull_request_read`) — not the running conversation history. When the `wiki` module is enabled (`.pilot/pilot-process.md` §8), also the story's entries (`python3 .pilot/pilot.py wiki index --ticket <issue>`, each
   with `wiki show <id>`).
4. Call the `Agent` tool with `subagent_type: "pilot-qa"`. Read `.pilot/pilot-task-human-qa.md`
   and pass its content as part of the prompt, plus `.pilot/pilot-link-bug-tickets.md` in
   full (the classify/originate mechanic for step 3's "real-bug failures" case — the task
   doc covers the phase-5-specific delta itself), along with that context (and `.pilot/pilot-link-knowledge.md` and `.pilot/pilot-link-wiki.md`
   in full when the wiki module is enabled). The agent
   returns a manual test plan: concrete cases and how to test each.
5. Walk the human through it (pair, always — no `--auto`): show the plan, then go case by
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
     bug"): `python3 .pilot/pilot.py set <issue> --status done --close` — the one
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
it's a human physically exercising the shipped, integrated feature and saying whether it
actually behaves as intended — the one check in PILOT no agent can perform on its own,
because it requires a real environment and a real person's judgment on the experience, not
just the diff. `type:tech`/`type:bug` tickets never reach this phase: a `type:tech` split
cascades straight to `status:done` once all its tasks are done (`.pilot/pilot-link-cascade.md` "Cascading completion"); a `type:bug` ticket — always a standalone `level:task`, never split (`.pilot/pilot-link-ticket-tree.md` "Three levels") — reaches `status:done` directly once its own PR merges.

## When it fires

Set by `.pilot/pilot-link-cascade.md` "Cascading completion": once a `type:feature` story's e2e task (and therefore
every dev sibling it depends on, per `.pilot/pilot-link-e2e-tasks.md`) reaches `status:done`,
the story itself lands on `status:qa` instead of `status:done` — unclaimed, unassigned,
the pool `/pilot-qa` picks from.

## Running it

`/pilot-qa` is **pair-only** (`.pilot/pilot-process.md` §4 "Interaction modes"). It claims the story (`.pilot/pilot-process.md` §4 "Claim
Protocol": `status:qa` → `status:in-qa`), builds a manual test plan, and walks the human
through it case by case. A failure is classified and handled exactly as
`.pilot/pilot-link-bug-tickets.md` describes — a genuine defect gets its own
`type:bug` ticket (via the same single mechanism every other phase uses) and unclaims the
story back to `status:qa`; a non-bug failure is reported
for the human to raise via Discovery themselves; anything unclassifiable is a live
`needs-human` block (`.pilot/pilot-process.md` §3 "A human is live in the same session"). Confirmed, or every
failure resolved to "not actually a bug" → `status:done`, the one direct exception `.pilot/pilot-process.md` §3
"`status:done`" already notes. `pilot-qa/SKILL.md` covers the rest of the mechanics.
