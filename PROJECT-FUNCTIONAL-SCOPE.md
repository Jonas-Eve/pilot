# pilot — Functional Scope

## Vision
PILOT gives a project a lightweight, agent-driven ticket process, from a raw idea to a merged and
verified change, that works the same way on every Claude Code surface (CLI, web, mobile). Its users
are the maintainers of the projects that copy it, the humans who drive a phase, and the agents that
run one. It is not an application: its product is the process and the tools that carry it. The
canonical description of that process is `assets/docs/pilot-process.md`.

## In scope
- **The ticket process**: five phases (Discovery, Spec, Dev, Review, human QA), each run by a skill
  in an isolated agent context, with the labels, the claim protocol and the state machine that move
  a ticket between them.
- **The personas** the phases delegate to (PM, architect, tech lead, dev, e2e, QA, designer), each
  with one identity and one task doc per duty.
- **Project commands outside the phases**: the design system and prototypes (`pilot-design`,
  `pilot-proto`), the wiki (`pilot-wiki`), the architecture bundle (`pilot-architecture`), the
  cockpit dashboard (`pilot-dashboard`), and help (`pilot-help`).
- **Deterministic mechanics** as a CLI (`scripts/pilot.py`): pools, claims, transitions, contracts,
  snapshots, the wiki and architecture engines, and the preflight checks.
- **Distribution**: a plain repo that projects clone and copy from, kept in sync by `pilot-init`
  and `pilot-update`, with optional modules a project turns on or off.
- **Adaptation to a project**: per call (pair or auto, `--with`, `--multi`), per module, per
  workflow profile (`standard`, the whole chain, or `lean`: no human QA, no e2e task, the tech lead
  alone reviews) chosen with `pilot.py workflow`, and per ticket: risk signals a project declares
  make a ticket pair only and add guardrails, and a ticket may carry its own `workflow:` label.

## Out of scope / not yet decided
- A Claude Code plugin: tried first, dropped, because installation stays local to one machine.
- Hosting, a server or a database of its own: the tickets live on GitHub, and the cockpit's data in
  its own Claude Artifact.
- Replacing a project's own CI, deployment or documentation conventions.
- Merging a pull request on its own: only a human merges, unless they pass `--merge` explicitly.
- Not yet decided: a project's own risk signals (`docs/workflow-design.md`), the `wiki` module on
  this repo itself, and recording the interaction mode of each run.

## Glossary
- **Phase**: one of the five steps a ticket goes through, each a `pilot-<phase>` skill.
- **Persona**: an agent identity (`.claude/agents/pilot-*.md`); the duty to perform arrives in the
  prompt from a task doc.
- **Task doc**: `assets/docs/pilot-task-<duty>.md`, one persona's instructions for one duty.
- **Link doc**: `assets/docs/pilot-link-<topic>.md`, what two or more skills need to agree on.
- **Pair / `--auto`**: a live human in the loop, or an unattended run.
- **Cockpit**: the dashboard published as a private Claude Artifact per project.
- **Module**: an optional capability of a project (`wiki`, `architecture`, `dashboard`, `design`,
  `proto`), switched in `.pilot/state.json`.
