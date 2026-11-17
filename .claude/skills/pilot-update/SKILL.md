---
name: pilot-update
description: "Re-syncs everything PILOT-owned in a project from a fresh clone of github.com/Jonas-Eve/pilot — every skill under .claude/skills/ and agent under .claude/agents/, .pilot/pilot-process.md, its human-facing companion doc(s) (.pilot/pilot-process-*.md), its cross-skill link doc(s) (.pilot/pilot-link-*.md), its per-duty task doc(s) (.pilot/pilot-task-*.md, injected into an Agent call's prompt by the phase skill that owns that duty), the status-cascade GitHub Actions workflow, the PILOT:INTRO/PILOT:MAINTENANCE marked blocks in CLAUDE.md/README.md, the GitHub labels, and the project's dashboard artifact when it has one. Overwrites, with no merge: any local edits to a PILOT-owned file are lost, so it diffs and confirms before overwriting each one, and flags any locally-copied skill/agent, .pilot/pilot-process-*.md, .pilot/pilot-link-*.md, or .pilot/pilot-task-*.md file no longer existing upstream (renamed or removed) for removal. Use periodically, or whenever you suspect PILOT's own skills/docs/labels have changed upstream, to pick up those changes in the project."
disable-model-invocation: true
---

# PILOT maintenance — `pilot-update`

Not one of the five PILOT phases, and not `pilot-init`'s one-time setup —
this is the ongoing maintenance command, safe to run repeatedly.

## Get a fresh copy of the source repo

Same as `pilot-init`: clone (or re-clone) `https://github.com/Jonas-Eve/pilot` into a
scratch directory — call it `$PILOT_SRC` — and use that one clone for every step. Always
re-clone fresh (or `git pull` an existing scratch clone) rather than reuse a stale one
from a previous run — the whole point is picking up upstream changes.

## What this does and does not touch

- **Every skill under `.claude/skills/`** whose directory name matches one that exists
  under `$PILOT_SRC/.claude/skills/` (i.e. every PILOT skill: `pilot-discovery`,
  `pilot-spec`, `pilot-dev`, `pilot-review`, `pilot-qa`, `pilot-auto`, `pilot-help`,
  `pilot-init`, `pilot-update`, `pilot-dashboard`, `pilot-architecture`) — and every agent under `.claude/agents/` matching
  `$PILOT_SRC/.claude/agents/pilot-*.md` — are PILOT-owned. This command re-copies all of them
  verbatim from `$PILOT_SRC`, **overwriting with no merge**. If a project-local skill or
  agent directory doesn't match anything under `$PILOT_SRC` (the project's own, unrelated
  skill), leave it alone — touch only what's actually PILOT's.
- **`.pilot/pilot-process.md`**, every **`.pilot/pilot-process-*.md`** human-facing companion
  (currently just `.pilot/pilot-process-companion.md` — no skill or agent reads any of
  these), every **`.pilot/pilot-link-*.md`** cross-skill link doc (the opposite of a
  companion — read by the specific skills/agents it names, not every phase, not a human
  audience), every **`.pilot/pilot-task-*.md`** per-duty task doc (read by exactly one
  phase skill and injected into an `Agent` call's prompt — the `.claude/agents/pilot-*.md`
  persona files carry only identity, never a duty's mechanics),
  **`.pilot/pilot.py`** (the script the `pilot-spec`/`pilot-dev`/`pilot-review`/
  `pilot-qa` skills run for ticket selection, claiming and status transitions, from
  `$PILOT_SRC/scripts/pilot.py`), and
  **`.github/workflows/pilot-status-on-merge.yml`** are the same kind of PILOT-owned
  file, made by `pilot-init` from `$PILOT_SRC`.
- **The `<!-- PILOT:INTRO:START -->`/`END` and `<!-- PILOT:MAINTENANCE:START -->`/`END`
  blocks** in the project's `CLAUDE.md` and `README.md` are PILOT-owned content embedded
  inside otherwise project-owned files —
  see step 4.
- **The dashboard artifact**, when `.pilot/state.json` has a `dashboardUrl`, is PILOT-owned
  too: it is republished from the current template at the same address (step 5b); its data
  (snapshot, events, activity) is kept, and anything edited in the page itself is lost.
- **`wiki/`** is project-owned content, never touched here; the `wiki` module itself is the project's
  choice (`modules` in `state.json`, step 5c).
- **GitHub labels** are re-applied idempotently (create-or-update, never delete) — safe
  to always re-run.
- **`.github/pull_request_template.md`** is explicitly **not** PILOT-owned, even though
  `pilot-init` copies it in from `$PILOT_SRC/assets/github/pull_request_template.md`. It's
  a one-time scaffold, not a synced asset: this command never diffs, touches, or reports
  on it, so the project is free to customize it however it likes.
- Anything hand-edited inside a PILOT-owned file/block is lost on overwrite — that's why
  every step below diffs and confirms first, never overwrites silently.

## Steps

1. **Check preconditions.** Read `.pilot/state.json`. If missing or `pilotInitialized`
   is not `true`, stop and tell the human to run `/pilot-init` first.

2. **Diff and sync skills/agents.** For each directory under `$PILOT_SRC/.claude/skills/` and
   each file under `$PILOT_SRC/.claude/agents/`:
   - If the project has no matching `.claude/skills/<name>/` or `.claude/agents/<name>`,
     it's new upstream — copy it in and mention it in the final report as newly added.
   - If the project has a matching one and its content differs, show a diff and ask for
     confirmation before overwriting (same no-merge treatment as any other PILOT-owned
     file). Identical content needs no confirmation.
   Then check the reverse direction: for each `.claude/skills/pilot-*`
   and `.claude/agents/pilot-*.md` the project has, if nothing matching exists under
   `$PILOT_SRC` any more (renamed or removed upstream), flag it to the human as orphaned
   and ask before deleting — don't delete silently, and don't guess at a replacement name;
   if the human knows what it was renamed to, let them say so.

3. **Diff the PILOT-owned root files.** Compare the project's `.pilot/pilot-process.md`,
   every `.pilot/pilot-process-*.md`, `.pilot/pilot-link-*.md`, and `.pilot/pilot-task-*.md` the
   project has, `.pilot/pilot.py` (against `$PILOT_SRC/scripts/pilot.py`; new
   upstream if missing, `chmod +x` after copying), and
   `.github/workflows/pilot-status-on-merge.yml` against `$PILOT_SRC`'s
   copies (for the three glob sets, that means every such file currently under
   `$PILOT_SRC/assets/docs/` — treat each as its own set, not a fixed list of names,
   however many exist today). For each one that differs, show a diff and ask for
   confirmation before overwriting. A file identical to `$PILOT_SRC`'s needs no
   confirmation. If the project has no matching
   `.pilot/pilot-process-*.md`/`.pilot/pilot-link-*.md`/`.pilot/pilot-task-*.md` yet, it's new
   upstream — copy it in and mention it in the report as newly added. On confirmation,
   copy `$PILOT_SRC`'s version over the project's; on decline, leave it untouched and say
   so — a decline on one file must never block overwriting another, or block steps 2, 4,
   or 5.
   Then check the reverse direction, same as step 2: for every `.pilot/pilot-process-*.md`,
   `.pilot/pilot-link-*.md`, and `.pilot/pilot-task-*.md` the project has, if nothing matching
   that name exists under `$PILOT_SRC/assets/docs/` any more (renamed or removed
   upstream), flag it to the human as orphaned and ask before deleting — don't delete
   silently, and don't guess at a replacement name; if the human knows what it was
   renamed to, let them say so.

4. **Diff the marked blocks.** For each `(file, marker, canonical snippet)` triple —
   `(CLAUDE.md, PILOT:INTRO, pilot-intro-claude.md.tmpl)`,
   `(README.md, PILOT:INTRO, pilot-intro-readme.md.tmpl)`,
   `(CLAUDE.md, PILOT:MAINTENANCE, pilot-maintenance-claude.md.tmpl)`:
   - If the file has no `<!-- PILOT:<marker>:START -->` marker, it predates this
     convention (or was hand-authored before the project adopted PILOT). Don't guess
     where to insert one — report that this file has no managed block of that kind and
     skip it, unless the human explicitly asks you to locate the equivalent PILOT
     paragraph/section by hand and wrap it in markers now (a one-time fixup, not
     something to do silently).
   - If it has the markers, compare the content between them against
     `$PILOT_SRC/assets/templates/<canonical snippet>`. If it differs, show the diff and
     ask for confirmation before replacing the block's contents — same treatment as step
     3. Never touch anything outside the markers.
   `PILOT:ARCHITECTURE` and `PILOT:COMMANDS` (snippets `pilot-architecture-claude.md.tmpl`/`pilot-architecture-readme.md.tmpl` and
   `pilot-commands-claude.md.tmpl`/`pilot-commands-readme.md.tmpl`, for `CLAUDE.md` and `README.md`) are different: a project may have filled them with
   its own apps and commands. Replace one only when it still holds the placeholder (it names `/pilot-init-archi`) or an earlier copy of the
   pointer; a block with real content is left exactly as it is, and `/pilot-architecture --bootstrap` is what converts it.
   These blocks aren't limited to those above — if this repo's own templates gain
   another `PILOT:<name>:START`/`END` marker later, treat it the same way.

5. **Re-provision GitHub labels.** Resolve the repo (`gh repo view --json
   nameWithOwner --jq .nameWithOwner`) and run, from the project's own root,
   `$PILOT_SRC/scripts/setup-github-labels.sh <owner>/<repo>` — running it from there
   (not from inside `$PILOT_SRC`) is what lets it find this project's own
   `.pilot/state.json` and bump `lastLabelsSyncAt` itself (see the script's own header
   comment). If `gh` isn't installed or authenticated, tell the human and give them the
   exact command to run themselves later — don't block steps 2-4 or 6 on it, and leave
   `lastLabelsSyncAt` as whatever it already was.

5c. **Check the modules.** `python3 .pilot/pilot.py module list`. A `state.json` with no `modules` field predates them:
   record in step 6 what the project already uses, so nothing it relies on disappears — `dashboard` on when it has a
   `dashboardUrl`, and `design` and `proto` on with it (they only worked with it), `wiki` off. A `state.json` with no `language` means English: leave it, and mention `language` (the text of wiki and architecture entries) if the project writes them in another language. Say which modules exist
   (`.pilot/pilot-process.md` §8) and that each is turned on by its own skill (`/pilot-wiki`, `/pilot-architecture`, `/pilot-dashboard`,
   `/pilot-design`, `/pilot-proto`); never enable anything else here, and never create or change anything under
   `wiki/` or `architecture/`. With the `wiki` module on but `wiki/` missing, say that `doctor` fails until `/pilot-wiki` repairs it; with
   it on and entries still in the earlier format (several per page, `wiki lint` reporting `no-frontmatter`), offer
   `python3 .pilot/pilot.py wiki migrate` (one PR). When the project has closed tickets or code to document, mention
   `/pilot-wiki --bootstrap`. A project that ran `/pilot-init-archi` (a `state.json` with `archInitialized: true`, or `apps`, or real content in
   its `PILOT:ARCHITECTURE` block) keeps all of it working untouched: the module stays off unless the human asks; offer `/pilot-architecture
   --bootstrap`, which turns it on, reads that content, `docs/` and each app's own documents (`python3 .pilot/pilot.py arch inventory`), and drafts
   `architecture/` in one PR. Leave `archInitialized` and `apps` in place (the personas read `apps`); `archInitialized` is no longer written or read.
   The `/pilot-init-archi` skill is gone upstream, so step 3 flags it as orphaned: offer to delete it once nothing needs it.

5b. **Update the dashboard.** Only when `.pilot/state.json` has a `dashboardUrl`: run
   `/pilot-dashboard` (reusing this `$PILOT_SRC`), after asking the human whether to
   republish — it does nothing if the rendered page is unchanged, and a refusal or failure
   there (e.g. the current user can't edit the artifact) never blocks the rest of the update.
   Without a `dashboardUrl`, don't create one here: mention in the report that
   `/pilot-dashboard` can.

6. **Update the state marker.** Set `lastSkillsSyncAt` (if step 2 changed anything),
   `lastProcessDocSyncAt` (if step 3 changed any of its files), and
   `lastIntroSyncAt` (if step 4 changed anything) in `.pilot/state.json` to now, `modules` (step 5c, only when it was absent), and
   `pilotVersion` to the contents of `$PILOT_SRC/VERSION` (remember the previous value for
   the report; a project without one predates versioning).
   `lastLabelsSyncAt` needs no action here — step 5's script bumps it itself when it runs
   successfully; `/pilot-dashboard` writes its own `dashboard*` fields.

7. **Report.** Say which PILOT version the project moved from and to (`pilotVersion`). Run
   `python3 .pilot/pilot.py doctor` and include its result (a failed
   `pilot-labels` check means step 5's label sync did not complete; a failed `wiki` check means the module is on but `wiki/` is missing, step 5c). Summarize what changed across steps 2-5: skills/agents added, updated,
   flagged as orphaned (and whether removed), each root file added, updated, flagged as
   orphaned (and whether removed), or left as-is and why, intro blocks resynced or
   skipped, labels created/updated.
