---
name: pilot-proto
description: "Builds a prototype of a feature with a human, to decide whether to build it — before any Discovery (see .pilot/pilot-process.md). Not one of the five phases. The PM first frames the idea alone with the human (the feature, who for, what the prototype must teach) into a brief they validate; then the designer leads a live discussion that builds a clickable mockup from what the human says, stored in the project's dashboard and shown in its \"Prototypes\" tab; when the human says it is done, the PM checks it against the brief (and debates the designer if it objects). Creates a type:poc ticket as status:poc-draft as soon as a first mockup exists, status:poc-review once approved. <n> --accept accepts a prototype under review (status:poc-validated), after which /pilot-discovery --from-proto <n> may start from it; <n> --reject [reason] rejects any open prototype, with its reason, and closes it. --from-artifact <url> imports one of the human's own Claude artifacts as the mockup (self-contained, under 1 MB). --resume <n> picks a draft back up. --with architect adds the architect from the start; the human can summon or dismiss a persona at any time. Always pair, never --auto, never Routine-driven. Needs a project with a dashboard (/pilot-dashboard) and the tool that writes to its database."
argument-hint: "<feature idea in free text> [--with architect] | --from-artifact <artifact url> [note] | --resume <issue number> | <issue number> --accept | <issue number> --reject [reason]"
disable-model-invocation: true
---

# PILOT proto — `pilot-proto`

Read `.pilot/pilot-process.md` first (labels `type:poc` and `status:poc-*`, the roster). Here the PM
frames, the designer leads, the PM validates and the architect is summonable; the human approves.
`.pilot/pilot-task-advise.md` is passed into a summoned persona's call. Always pair: it needs a human
live (except `--accept` and `--reject`, which are one mechanical step).

## Steps

-1. **The module.** `python3 .pilot/pilot.py module list`: with the `proto` module off, say so and propose turning
   it on (`python3 .pilot/pilot.py module enable proto --with-requires`, which turns the `dashboard` module on
   too); on a yes go on, on a no stop.
0. **Preflight**, once per session: `python3 .pilot/pilot.py doctor` — skip it if it already reported
   `ok: true`. `ok: false` or a failure → report and stop.
1. **Input.**
   - `<n> --accept`: `python3 .pilot/pilot.py proto <n> accept`. Then, in the dashboard (step 8), `update`
     `protos/p<n>` with `decision: "accepted"` and `decidedAt` (now, UTC ISO 8601). Say it can now start a
     Discovery (`/pilot-discovery --from-proto <n>`). Stop.
   - `<n> --reject [reason]`: with no reason given, ask the human for one, in one question. `python3
     .pilot/pilot.py proto <n> reject --reason "<reason>"`; then `update` `protos/p<n>` with
     `decision: "rejected"`, `reason` and `decidedAt`. Stop.
   - `--resume <n>`: `python3 .pilot/pilot.py resolve proto <n> --resume`, then `claim proto <n> --mode
     <the returned action>` (`resume-orphaned` or `resume-cleared`). Read the ticket's body (the brief) and
     the mockup of `protos/p<n>` (step 5's parts, joined), then go to step 4 with that state.
   - `--from-artifact <url> [note]`: imports a Claude artifact as the mockup. Needs the `Artifact` tool, else
     stop. `Artifact read` the url: only the human's own plain single-page artifact comes back as HTML (its header
     says they can edit it). One made from an Artifact type (a Design canvas, a deck) or with several files
     returns no page: stop and say so — the human can ask Claude to rebuild it as one self-contained HTML file. Keep that page as the mockup in a temporary file; the note, if any, is the idea
     (otherwise ask what the prototype should teach). Go on.
   - Anything else is the feature idea, without its `--with` (ask if none given); go on. If it reads as a technical need or a bug,
     point at `/pilot-spec --tech`/`--bug` and stop.
2. **Preconditions.** `.pilot/state.json` has `dashboardUrl`, else stop and point at `/pilot-dashboard`; the
   tool that writes to the dashboard's database (`ArtifactData`, `ToolSearch` loads it if deferred) is
   available, else stop. Repo = `owner/repo` from `git config --get remote.origin.url`. Read the design system
   if there is one (`ArtifactData` `get` on `design/<owner>__<repo>`; none is fine, the designer then chooses
   plainly and says so).
3. **Frame, alone with the human, before any ticket exists.** Call `Agent` for `pilot-pm` with
   `.pilot/pilot-task-frame-proto.md`, the idea, the design system and the framing conversation so far,
   (and, with `--from-artifact`, the imported mockup: the brief states what it shows and what it must teach)
   round by round: show the human its brief and questions as a natural conversation (a provisional default
   as the recommended option when one helps), feed the replies back. Stop when the PM says the brief is
   ready and the human confirmed it, or when the idea is out of scope (report, create nothing).
4. **Build.** With `--from-artifact` the mockup already exists: skip the first designer call, create the ticket
   as below, run step 5 (if `proto-pack` refuses the mockup, report its `problems` and stop — the human fixes
   the artifact, or starts again from an idea) and go on; the designer takes part only if the human asks for
   changes. Otherwise call `Agent` for `pilot-designer` with `.pilot/pilot-task-build-proto.md`, the validated brief,
   the design system, the current mockup (if any), the conversation so far and the human's words — nothing
   else from this conversation. Show the human its assumptions and questions; write the returned HTML to a
   temporary file. After the **first** mockup: create the ticket (`mcp__github__issue_write`) — title from the
   brief, body = the validated brief, `type:poc` + `level:story` + `status:poc-draft`, assigned to this
   session — then run step 5 and tell the human to open the dashboard's Prototypes tab
   (`<dashboardUrl>#proto/<n>`; it opens there, or under Prototypes › #<n> if the link opens the home page).
   Each later round the designer revises, step 5 stores it again and the ticket body keeps the current brief.
   Any persona from `--with`, or summoned or dismissed by the human, takes part the same way.
5. **Store the mockup** (whenever it changed): `python3 .pilot/pilot.py proto-pack <n> --html <file> --out <dir>
   --brief "<the brief, short>"`. It refuses a mockup that is empty, over 1 MB or not self-contained — give
   the designer its `problems` and ask for a fix. Otherwise `get` `protos/p<n>`: if it exists, remember its
   `parts`. Then one `ArtifactData` `batch`: `protos/p<n>` (`update` with `proto-<n>.json` when it exists, else
   `set`), every `protoHtml/<n>-<k>` from the files `proto-pack` wrote (`set`, `if_version` when it exists), and
   a `delete` for each old part beyond the new `parts`.
6. **Validate.** When the human says the work is done, call `Agent` for `pilot-pm` with
   `.pilot/pilot-task-check-proto.md`, the recorded brief and the mockup only — not the discussion. An
   objection brings the PM into the debate with the designer and the human, then back on the revised mockup
   alone (`.pilot/pilot-link-agent-dialogue.md` "Roster").
7. **Finalize** once the human approves: `python3 .pilot/pilot.py set <n> --status poc-review --unassign`.
   Say how to decide: accept (`/pilot-proto <n> --accept`) or reject (`/pilot-proto <n> --reject`), also from
   the dashboard.
8. **Dashboard** (best-effort, `.pilot/pilot-link-dashboard.md`): push the `event`/`activity` that `pilot.py
   claim|set|proto` return. Skipped silently when `dashboardUrl` is absent.
9. Report the ticket number, its state and where to see it.

## `status:poc-*` — a prototype's own lifecycle, outside the pipeline
- `status:poc-draft` — being built with a human; assigned while a session works on it
  (resumable like any other claim: `can-resume`, `/pilot-proto --resume <n>`).
- `status:poc-review` — published, unassigned, waiting for a human: accept it
  (`/pilot-proto <n> --accept`) or reject it (`--reject`).
- `status:poc-validated` — accepted. Only now may `/pilot-discovery --from-proto <n>` start from
  it; the prototype ticket is closed, label kept, once that Discovery's stories are approved.
- `status:poc-rejected` — rejected; the reason is a comment on the ticket, which is closed.

These are the only labels `/pilot-proto` changes; `pilot.py proto <n> accept|reject|from-proto`
applies the transitions and refuses any other.
