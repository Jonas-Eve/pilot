# PILOT — Visual Reference

This is a companion to `docs/pilot-process.md`, not a replacement for it. It exists purely
to help a **human** get oriented — nothing here is read by any phase skill or agent, and
nothing here is authoritative: if this file and `docs/pilot-process.md` ever disagree,
`docs/pilot-process.md` is right. It's PILOT-owned and kept in sync by `/pilot-update`, the
same as `docs/pilot-process.md` itself — never hand-edit it in a project that copied PILOT.

## Command quickstart

Every command below is a plain example — the exact syntax and behavior for each is
authoritative in that skill's own `SKILL.md` (`argument-hint`), not here:

```
/pilot-story "let a user filter search results by wheelchair accessibility"
    → opens a type:feature issue (PM agent, auto-detected)

/pilot-story "add the GitHub Actions CI workflow described in our tech-debt backlog"
    → opens one or more type:tech issues (architect agent, auto-detected)

/pilot-story --tech "..."   → skips detection, declares the need type:tech upfront
/pilot-story --bug "clicking export on the reports page throws a 500"
    → skips detection, declares it type:bug upfront (architect agent)
/pilot-story --resume 12    → picks back up a status:draft ticket left mid-pair

/pilot-scope 42        → scopes/decomposes existing issue #42
/pilot-spec 42         → writes the technical spec for #42 (must be status:spec-ready)
/pilot-dev             → claims and implements the next status:dev-ready ticket, no
                          argument needed
/pilot-dev 42          → claims and implements #42 specifically
/pilot-review 57       → claims and runs phase 5 against PR/issue #57, pair by default
                          (must be status:review-ready, or status:in-review resumable)
/pilot-review 57 --auto  → same, no live checkpoint (needed for a scheduled Routine)
/pilot-review 57 --merge → merges the PR itself once every reviewer approves
/pilot-review 57 --resume → recovers a claim orphaned by a crashed phase-5 run
/pilot-qa 61           → runs phase 6 (human QA) against story #61 (must be status:qa)
```

## Example: a `type:feature` story end to end

The golden path below is deliberately the richest one PILOT has — it's the only path that
touches all six phases, a mandatory split with mixed task types, and every `status:`
transition that isn't itself a branch (`wont-do`, `changes-requested`, `needs-human`,
`on-hold`, a prerequisite ticket, `--resume`/reclaim, or re-scoping a story whose split is
already done) — those are covered in `docs/pilot-process.md` instead.

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
        DevAgent-->>GH: PR opened — status:review-ready
        Human->>Rev: /pilot-review #<PR>
        GH->>Rev: status:review-ready → status:in-review (claim)
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
    alt all confirmed, or a failure isn't actually a bug
        QAAgent->>GH: status:done + close issue (reports any non-bug finding for phase 1)
    else genuine bug
        QAAgent->>GH: originates type:bug (level:task, spec-ready) + unclaims (status:in-qa → status:qa)
    else can't classify on its own
        QAAgent->>GH: needs-human + findings (resolved live and cleared same-turn, or left for later)
    end
    end
```
