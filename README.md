# PILOT

PILOT is a lightweight, in-house ticket-process framework: `plan` → `investigate` →
`lay out` → `operate` → `test & validate`, each its own isolated, low-token agent context
instead of one accumulating one — plus a mandatory sixth phase, human QA, for every
`type:feature` story once every sub-ticket (including its automated end-to-end test) has
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
`/pilot-init` copies it into your project as `docs/pilot-process.md`, and
`/pilot-update` keeps it in sync.

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
    `docs/pilot-process.md`, the GitHub Actions workflow, the `PILOT:INTRO` blocks in
    `CLAUDE.md`/`README.md`, the GitHub labels) from a fresh clone of this repo into
    your project. Overwrites, no merge — see the warning in `.claude/skills/pilot-update/SKILL.md`.
  - `/pilot-story`, `/pilot-scope`, `/pilot-spec`, `/pilot-dev`, `/pilot-review`,
    `/pilot-qa` — the six phases themselves.
- **Agents** (`.claude/agents/`): the six personas the phase skills delegate to —
  `pilot-pm`, `pilot-architect`, `pilot-techlead`, `pilot-dev`, `pilot-e2e` (phase 4's
  persona for an end-to-end-test sub-ticket, `type:e2e`, instead of `pilot-dev`), and
  `pilot-qa` (phase 6's persona, a human-paired manual QA gate for every `type:feature`
  story once its sub-tickets are all done).
- **Scripts** (`scripts/`): `setup-github-labels.sh`, idempotent creation/update of every
  label the state machine uses.
- **Templates** (`assets/templates/`): the doc skeletons `/pilot-init` fills in.

## Installing in a project

There's no install command to run — a brand-new project has no PILOT skill available
yet to invoke one. Instead:

1. Clone this repo somewhere accessible: `git clone https://github.com/Jonas-Eve/pilot`.
2. Copy its `.claude/skills/` and `.claude/agents/` straight into your project's own
   `.claude/skills/`/`.claude/agents/` (verbatim, same paths — this is exactly what
   `/pilot-init` does for itself when re-run later, so this manual first copy and every
   subsequent `/pilot-update` end up identical).
3. Run `/pilot-init` in your project. It takes care of everything else (docs, labels,
   the status-cascade workflow).

## Updating

Everything PILOT ships is a plain file copy living in your project's own git tree —
there's no separate plugin-update mechanism to think about. Run `/pilot-update` in your
project whenever you want to pick up a change made here: it re-clones this repo fresh,
diffs every PILOT-owned skill/agent/doc/workflow/label against your project's copy, and
asks for confirmation before overwriting anything that differs.

## Developing this repo

Trunk-based development on `main`, Conventional Commits, rebase-merge PRs — see
`CLAUDE.md` for the full set of conventions used to develop PILOT itself.
