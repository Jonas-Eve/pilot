# PILOT

PILOT is a lightweight, in-house ticket-process framework: `plan` → `investigate` →
`lay out` → `operate` → `test & validate`, each its own isolated, low-token agent context
instead of one accumulating one — plus a mandatory sixth phase, human QA, for every
`type:feature` story once every task (including its automated end-to-end test) has
merged. It was built inside a single monorepo and is packaged here as a standalone,
reusable repo any project can copy from.

This repo is **not a Claude Code plugin** — plugin installation turned out to be local
to whichever machine/container runs it (a Codespace, a local CLI), so it never reached
Claude Code on the web or the mobile app. PILOT is distributed the simpler way instead:
this repo's own `.claude/skills/` and `.claude/agents/` are exactly what gets copied into
a consuming project's — same paths, same layout — where they work identically on every
surface, because that's exactly how any other project-local skill works.

See [`assets/docs/pilot-process.md`](./assets/docs/pilot-process.md) for the full state
machine, label taxonomy, and claim protocol — it's the canonical copy;
`/pilot-init` copies it into your project as `.pilot/pilot-process.md`, and
`/pilot-update` keeps it in sync.

Each skill reads three layers, not just its own file: `pilot-process.md` for what every
phase shares, a `pilot-link-<topic>.md` doc (below) for what it coordinates with a couple
of other skills on, and its own `SKILL.md` for everything specific to that one phase. The
actual judgment work happens in a separate `Agent` call to one of the six personas below,
each carrying only a small, stable identity — the skill reads a `pilot-task-<duty>.md`
doc (below) and passes it into that call, so a persona is told what to do fresh each
time instead of carrying every one of its duties' instructions on every invocation.

## What this repo ships

- **Skills** (`.claude/skills/`): three bootstrap/maintenance commands, plus the six
  PILOT phase commands — copied verbatim into a consuming project's `.claude/skills/`
  (see "Installing in a project" below), so all of them, `pilot-init`/`pilot-init-archi`/
  `pilot-update` included, are ordinary project-local commands once installed.
  - `/pilot-init` — one-time: name the project, write its functional vision, copy in
    PILOT's own skills/agents/docs, generate `CLAUDE.md` / `README.md` /
    `PROJECT-FUNCTIONAL-SCOPE.md`, and create the GitHub labels PILOT depends on.
  - `/pilot-init-archi` — one-time: describe the monorepo's apps and technology choices (or
    accept the defaults — Clean Architecture, Node.js backend, React frontend, Expo for
    mobile, TypeScript throughout), generate each app's docs, and scaffold its skeleton
    pinned to the latest compatible dependency versions.
  - `/pilot-update` — re-sync everything PILOT-owned (skills, agents,
    `.pilot/pilot-process.md`, its `.pilot/pilot-process-*.md` companion(s),
    `.pilot/pilot-link-*.md` cross-skill link doc(s), `.pilot/pilot-task-*.md` per-duty task
    doc(s), the GitHub Actions workflow, the `PILOT:INTRO` blocks in
    `CLAUDE.md`/`README.md`, the GitHub labels) from a fresh clone of this repo into
    your project. Overwrites, no merge — see the warning in
    `.claude/skills/pilot-update/SKILL.md`.
  - `/pilot-story`, `/pilot-scope`, `/pilot-spec`, `/pilot-dev`, `/pilot-review`,
    `/pilot-qa` — the six phases themselves.
  - `/pilot-auto` — dispatcher: tries `/pilot-review --auto`, `/pilot-dev --auto`,
    `/pilot-spec --auto`, `/pilot-scope --auto`, in that order, stopping at the first one
    that finds work (an optional `--merge` forwards to `/pilot-review` only, `--again`
    keeps sweeping until a full pass finds nothing instead of stopping at the first
    candidate). Bare (or a
    subset like `/pilot-auto spec scope`), each phase works its own pool. Given a single
    issue number instead (`/pilot-auto 48`), the same four are tried against that one
    ticket rather than a pool — each phase's own claim protocol reports nothing to do when
    the ticket isn't currently theirs, so this command never reads the ticket's `status:`
    itself. `--next` (alias `--continue`) keeps re-dispatching one ticket through the full
    chain until nothing's left, `needs-human`, it closes, or it looks orphaned — given an
    issue number, that ticket; given none, whichever candidate the first sweep pass
    claims. Not a phase itself, and never invokes
    `/pilot-story`/`/pilot-qa` (pair-only).
    Lets one scheduled Routine drive the whole pipeline, or several Routines split it by
    cadence, or a human/Routine hand it one ticket without knowing which phase it's in —
    see `.claude/skills/pilot-auto/SKILL.md`.
- **Agents** (`.claude/agents/`): the six personas the phase skills delegate to —
  `pilot-pm`, `pilot-architect`, `pilot-techlead`, `pilot-dev`, `pilot-e2e` (phase 4's
  persona for an end-to-end-test task, `type:e2e`, instead of `pilot-dev`), and
  `pilot-qa` (phase 6's persona, a human-paired manual QA gate for every `type:feature`
  story once its tasks are all done). Each file is just that persona's identity — its
  duty instructions (how it scopes, how it reviews, ...) live in `pilot-task-<duty>.md`
  instead, below.
- **Scripts** (`scripts/`): `setup-github-labels.sh`, idempotent creation/update of every
  label the state machine uses — also bumps the calling project's own
  `.pilot/state.json` (`lastLabelsSyncAt`) when run from that project's root.
- **Templates** (`assets/templates/`): the doc skeletons `/pilot-init` fills in.

See [`assets/docs/pilot-process-companion.md`](./assets/docs/pilot-process-companion.md) for a
sequence diagram of a `type:feature` story moving through all six phases — a purely
human-facing companion to `pilot-process.md`, kept in sync the same way.

`assets/docs/pilot-link-<topic>.md` files are the third kind: operational like
`pilot-process.md` itself but scoped to the specific two-or-more skills/agents that need
to coordinate on something, rather than all six phases — synced the same way, as
`.pilot/pilot-link-<topic>.md`. See `assets/docs/` for the current set.

`assets/docs/pilot-task-<duty>.md` files are the fourth: one persona's instructions for
one specific duty, never read by the persona itself but injected into the `Agent` call's
prompt by the one skill that owns that duty — synced the same way, as
`.pilot/pilot-task-<duty>.md`.

## Installing in a project

There's no install command to run — a brand-new project has no PILOT skill available
yet to invoke one. Instead:

1. Download just the `pilot-init` skill file into your project's own
   `.claude/skills/pilot-init/SKILL.md` (same path, no need to clone the whole repo for
   one file), e.g.:
   `curl -o SKILL.md https://raw.githubusercontent.com/Jonas-Eve/pilot/main/.claude/skills/pilot-init/SKILL.md`
   — that's the only piece that needs manual seeding, since `/pilot-init` copies every
   skill and agent (itself included) from a fresh clone in step 2.
2. Run `/pilot-init` in your project. It takes care of everything else (skills, agents,
   docs, labels, the status-cascade workflow).

## Updating

Everything PILOT ships is a plain file copy living in your project's own git tree —
there's no separate plugin-update mechanism to think about. Run `/pilot-update` in your
project whenever you want to pick up a change made here: it re-clones this repo fresh,
diffs every PILOT-owned skill/agent/doc/workflow/label against your project's copy, and
asks for confirmation before overwriting anything that differs.

## Developing this repo

Trunk-based development on `main`, Conventional Commits, squash-merge PRs by default
(rebase-merge only for deliberately separate commits) — see `CLAUDE.md` for the full set
of conventions used to develop PILOT itself.
