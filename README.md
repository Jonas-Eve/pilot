# PILOT

PILOT is a set of **workflows** where the human decides, through documents in a formatted
intermediate language, agents execute, and code checks. A request becomes a need (wiki
entries), then ADRs and tickets, then code, then a recette on the deployed main; each step
is an isolated, low-token agent call, and a human is asked only where no document decides.

It is packaged as a standalone repo any project clones and copies from — **not a Claude Code
plugin** (plugin installation stays local to one machine and never reached Claude Code on the
web or mobile). This repo's `.claude/skills/` and `.claude/agents/` are copied as-is into a
project's own, where they work identically on every surface.

The canonical spec is [`assets/docs/pilot-process.md`](./assets/docs/pilot-process.md): where
objects live, statuses and flags, the run, claim and resume, isolation, events, modules.
`/pilot-init` copies it into a project as `.pilot/pilot-process.md`; `/pilot-update` keeps it in sync.

## What this repo ships

- **Workflows** (`assets/workflows/*.json`, copied as `.pilot/workflows/`): eleven, as data — steps,
  personas, task docs, code checks, judges, where a failure goes, a contract of statuses.
  `scripts/pilot.py` serves one step at a time and decides the next from the data;
  `assets/formats.json` holds the document formats the checks validate.
- **Skills** (`.claude/skills/`), one per command:
  - Run a workflow: `/pilot-need`, `/pilot-plan`, `/pilot-build`, `/pilot-accept`, `/pilot-report`, `/pilot-express`.
  - Frames and design: `/pilot-wiki` (functional frame), `/pilot-architecture` (technical frame),
    `/pilot-design` (design system), `/pilot-proto` (prototype), `/pilot-flow` (personas and user flows).
  - Bootstrap and maintenance: `/pilot-init`, `/pilot-update`, `/pilot-dashboard`, `/pilot-help`.
- **Agents** (`.claude/agents/`): seven personas — `pilot-pm`, `pilot-architect`, `pilot-techlead`,
  `pilot-dev`, `pilot-e2e`, `pilot-qa`, `pilot-designer`. Each file is an identity only; its duties are
  `assets/docs/pilot-task-<duty>.md`, injected by the runner into the agent call.
- **Docs** (`assets/docs/`): `pilot-process.md` (generic), `pilot-link-<topic>.md` (read by two or more
  skills; `agent-contract` goes into every agent call), `pilot-task-<duty>.md` (one persona, one duty).
- **Scripts** (`scripts/`): `pilot.py` and `pilot_checks.py`, the deterministic mechanics and code checks
  as a CLI (copied as `.pilot/pilot.py`, `.pilot/pilot_checks.py`).
- **Templates** (`assets/templates/`) and **GitHub** (`assets/github/`: the merge workflow and PR template).

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
   docs, labels, the merge workflow).

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
