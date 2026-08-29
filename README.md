# PILOT

PILOT is a lightweight, in-house alternative to running the full BMAD-METHOD agent
framework for ticket work: five short phases — `plan` → `investigate` → `lay out` →
`operate` → `test & validate` — each its own isolated, low-token agent context instead of
one accumulating one. It was built inside a single monorepo and is packaged here as a
standalone **Claude Code plugin** so any project can install it.

See [`assets/docs/pilot-process.md`](./assets/docs/pilot-process.md) for the full state
machine, label taxonomy, and claim protocol this plugin implements — it's the canonical
copy; `/pilot:init` copies it into your project as `docs/pilot-process.md`, and
`/pilot:update` keeps it in sync.

## What this plugin ships

- **Skills** (`skills/`): three bootstrap/maintenance commands, plus the five PILOT
  phase commands.
  - `/pilot:init` — one-time: name the project, write its functional vision, generate
    `CLAUDE.md` / `README.md` / `PROJECT-FUNCTIONAL-SCOPE.md`, copy in
    `docs/pilot-process.md`, and create the GitHub labels PILOT depends on.
  - `/pilot:init-archi` — one-time: describe the monorepo's apps and technology choices (or
    accept the defaults — Clean Architecture, Node.js backend, React frontend, Expo for
    mobile, TypeScript throughout), generate each app's docs, and scaffold its skeleton
    pinned to the latest compatible dependency versions.
  - `/pilot:update` — re-sync PILOT's own files (`docs/pilot-process.md`, the GitHub
    labels) from this plugin into your project. Overwrites, no merge — see the warning
    in `skills/update/SKILL.md`.
  - `/pilot:story`, `/pilot:scope`, `/pilot:spec`, `/pilot:dev`, `/pilot:review` — the
    five phases themselves.
- **Agents** (`agents/`): the four personas the phase skills delegate to —
  `pilot-pm`, `pilot-architect`, `pilot-techlead`, `pilot-dev`.
- **Scripts** (`scripts/`): `setup-github-labels.sh`, idempotent creation/update of every
  label the state machine uses.
- **Templates** (`assets/templates/`): the doc skeletons `/pilot:init` fills in.

## Installing in a project

Add this repo as a plugin marketplace source, then install the `pilot` plugin — see
Claude Code's plugin documentation for the exact marketplace-add command for your
version. Once installed, run `/pilot:init` in the target project.

## Updating

- **Skills, agents, and this doc's own content**: handled automatically by Claude Code's
  plugin update mechanism — no PILOT-specific action needed.
- **Files copied into a consuming project's own git tree** (`docs/pilot-process.md`, the
  GitHub labels): run `/pilot:update` in that project after updating the plugin.

## Developing this plugin

Trunk-based development on `main`, Conventional Commits, rebase-merge PRs — see
`CLAUDE.md` for the full set of conventions used to develop PILOT itself.
