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
  persona for an end-to-end-test task, `type:e2e`, instead of `pilot-dev`), and
  `pilot-qa` (phase 6's persona, a human-paired manual QA gate for every `type:feature`
  story once its tasks are all done).
- **Scripts** (`scripts/`): `setup-github-labels.sh`, idempotent creation/update of every
  label the state machine uses.
- **Templates** (`assets/templates/`): the doc skeletons `/pilot-init` fills in.

## Example: a `type:feature` story end to end

The golden path below is deliberately the richest one PILOT has — it's the only path that
touches all six phases, a mandatory split with mixed task types, and every `status:`
transition that isn't itself a branch (`wont-do`, `changes-requested`, `needs-human`,
`on-hold`, a prerequisite ticket, `--resume`/reclaim, or re-scoping a story whose split is
already done) — those are covered in `assets/docs/pilot-process.md` instead, which stays
the operational spec every phase skill actually reads; this diagram is purely for a human
getting oriented.

```mermaid
sequenceDiagram
    actor Human
    participant PM as pilot-pm
    participant Arch as pilot-architect
    participant Tech as pilot-techlead
    participant DevAgent as pilot-dev / pilot-e2e
    participant Rev as pm + architect + techlead
    participant QAAgent as pilot-qa
    participant GH as GitHub (issue/PR)

    rect rgb(240,240,255)
    Note over Human,GH: Phase 1 — Plan (/pilot-story)
    Human->>PM: raw need (type:feature auto-detected)
    PM-->>Human: draft story + acceptance criteria (pair)
    Human-->>PM: approve
    PM->>GH: create issue — status:draft → status:backlog, level:story
    end

    rect rgb(240,255,240)
    Note over Human,GH: Phase 2 — Investigate (/pilot-scope)
    Human->>Arch: /pilot-scope #12
    GH->>Arch: status:backlog → status:scoping (claim)
    Note over Arch: type:feature ⇒ split is mandatory, never a judgment call
    Arch-->>Human: proposed tasks — a mix of type:feature/type:tech, plus exactly one type:e2e
    Human-->>Arch: approve
    Arch->>PM: type:feature tasks only (coverage check — tech/e2e excluded)
    PM-->>Arch: approve / block
    Arch->>GH: parent → status:split · each task → status:spec-ready, level:task
    end

    rect rgb(255,250,230)
    Note over Human,GH: Phases 3-5, once per level:task (reviewer set follows that task's own type:)
    loop each level:task
        Human->>Tech: /pilot-spec #<task>
        GH->>Tech: status:spec-ready → status:in-spec (claim)
        Tech-->>GH: spec written (or test plan, for type:e2e) — status:dev-ready
        Human->>DevAgent: /pilot-dev #<task>
        GH->>DevAgent: status:dev-ready → status:in-dev (claim; pilot-e2e if type:e2e)
        DevAgent-->>GH: PR opened — status:in-review
        Human->>Rev: /pilot-review #<PR>
        Rev-->>GH: verdict — status:approved (or status:changes-requested, loops back to DevAgent)
        Human->>GH: merge PR
        GH-->>GH: status:done (pilot-status-on-merge.yml)
    end
    end

    rect rgb(255,235,235)
    Note over GH: the e2e task depends on every sibling, so it structurally closes last
    GH-->>GH: type:feature parent: status:split → status:qa (not status:done)
    end

    rect rgb(235,245,255)
    Note over Human,GH: Phase 6 — Human QA (/pilot-qa, type:feature only)
    Human->>QAAgent: /pilot-qa #12
    GH->>QAAgent: status:qa → status:in-qa (claim)
    QAAgent-->>Human: manual test plan
    Human-->>QAAgent: results, case by case
    alt all confirmed
        QAAgent->>GH: status:done + close issue
    else one or more failures
        QAAgent->>GH: needs-human + findings (bug-handling flow: still provisional)
    end
    end
```

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
