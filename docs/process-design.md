# PILOT v3 — the process document, by contract (design proposal)

Status: **proposal, nothing changed yet**. Human-only: no skill or agent reads it, and it is not copied into
consuming projects. Once the work is done this file is removed.

## 1. The problem

`assets/docs/pilot-process.md` is 1125 lines, 79 KB, about 20 000 tokens, and every phase loads it on every run.
A phase uses a fraction of it. The rest describes what the *other* phases do, how a ticket travels the whole chain,
or what `scripts/pilot.py` already decides. That is coupling: each phase carries the knowledge of its neighbours.

## 2. The principle

Like a layered architecture, a phase depends on **contracts**, never on the phases around it. Each one knows:

- **where it comes from** — the status it consumes and the artifacts it expects (a contract, not who produces it);
- **what it does** — its own job;
- **where it goes** — the status(es) it produces and the artifacts it leaves (a contract, not who consumes it).

The chain is the *composition* of those contracts. It is checked by code, not known by any agent. What links two
phases is a link doc (`pilot-link-*.md`), which is already their contract.

**The test for a paragraph in `pilot-process.md`:** does a phase need it to do its job or to honor its contract?
If it describes a neighbour, the whole chain, or something the script decides, it moves or goes.

What stays generic (needed by every phase): the vocabulary (labels and what each status means), the cross-cutting
flags (`needs-human`, `on-hold`, `can-resume`), the claim contract, pair/`--auto`, context isolation, the module
switch.

## 3. Where each section goes

Sizes are those of today's file. "Script" means `scripts/pilot.py` is already the reference and the prose shrinks to
the contract.

| Section | Lines | Bytes | Today's reader | Verdict |
|---|---:|---:|---|---|
| 0 Prerequisites & Quickstart | 34 | 2154 | all | The label list duplicates `setup-github-labels.sh` and `doctor`; the quickstart is for humans → companion. Keep 3 lines. |
| 1 The Five Phases (table) | 13 | 2380 | all | The chain at a glance is for humans → companion. Each skill states its own contract. |
| 2 Ticket Types And Levels | 72 | 5326 | all | Keep one line per type (what it is, which reviewer set). Origination by type is Discovery's or Spec's contract → their skills/task docs. |
| Three levels | 71 | 5361 | Spec, QA, Discovery, 4 link docs | Vocabulary stays (3 lines); the mechanics are the tree contract → `pilot-link-ticket-tree.md`, read by Discovery, Spec, QA. |
| Prerequisite tech/bug tickets | 59 | 4188 | Spec | Spec's contract; `pilot-link-bug-tickets.md` already covers the shared part → Spec. |
| Dependencies between tasks | 12 | 774 | Spec, scope task | The `Depends on #N` format is a writer contract the script reads → keep 5 lines. |
| Re-scoping a split story | 51 | 3478 | Spec, epic-descent | Spec's contract (the epic-descent link doc has the shared part) → Spec. |
| `type:`, `level:` labels | 36 | 2425 | all | Vocabulary; keep, shortened. |
| `status:` state machine | 132 | 9649 | all | **Code first** (§4): each phase's consumed/produced statuses become data in the script; the prose keeps one line of meaning per status, the per-status detail goes to the phase that produces or consumes it. |
| `status:poc-*` | 12 | 810 | `pilot-proto` | The proto module's own lifecycle → `pilot-proto`. |
| `needs-human` | 87 | 6163 | all | Cross-cutting, keep the contract (~25 lines); the resolution flows are `flag`/`unflag` in the script and each phase's own step. |
| `on-hold`, `can-resume` | 43 | 2985 | all | Cross-cutting, ~15 lines together; `pool`/`resolve` are the reference. |
| `priority:` | 27 | 1918 | Discovery, Spec | Vocabulary 8 lines; who sets it is the PM's / architect's duty (task docs already say). |
| 4 Claim Protocol | 31 | 2074 | the four claiming phases | Contract, ~10 lines, script is the reference. |
| Picking the next ticket | 20 | 1193 | epic-descent | Script (`pool`) → 2 lines. |
| Explicit ticket with open sub-issues | 13 | 953 | nobody cites it | Covered by `pilot-link-epic-descent.md` → delete. |
| Blocked-by dependencies | 23 | 1496 | Spec | Script gate → 5 lines. |
| Resuming a `needs-human` ticket | 27 | 1794 | claiming phases | Script `resolve` → shrink. |
| Resuming an orphaned claim | 40 | 2779 | claiming phases | Script `resolve`/`can-resume` → ~8 lines. |
| Reclaiming `changes-requested` | 28 | 1748 | Dev, Review | The Review→Dev contract → `pilot-link-review-consensus.md`. |
| Scheduled sweeps | 15 | 1034 | `pilot-auto` | `pilot-auto` skill. |
| Interaction modes (pair / `--auto`) | 102 | 7519 | all | Keep the generic contract (~30 lines); per-phase deltas into each skill. |
| Agent dialogue | 13 | 918 | two skills | `pilot-link-agent-dialogue.md` already holds it → delete. |
| Roster | 48 | 3473 | Discovery, Spec, link docs | Into `pilot-link-agent-dialogue.md`. |
| 5 Token efficiency | 25 | 1528 | all | The isolation principle; keep ~10 lines. |
| 6 Review consensus | 17 | 1062 | link doc only | Nobody cites §6; the link doc is the contract → delete. |
| 7 Human QA (+2 subsections) | 31 | 1901 | QA, e2e link | `pilot-qa` and its task doc. |
| 8 Optional modules | 25 | 2209 | all | Keep the switch rule (~8 lines); each module's detail is in its link doc. |

Target: from 79 KB to about a quarter of it (roughly 300 lines), the rest living where one phase or one pair of
phases reads it. These are targets, not promises: each move is checked against the whole file (CLAUDE.md §3).

## 4. The state machine, by contract

Today `pilot.py set` accepts any known status from any other: the graph exists only in prose, and an agent reading
it is the only guard. Instead:

1. `PHASES` in the script gains, per phase, the statuses it **consumes** and **produces** (it already has the
   pre-claim status), plus the cross-cutting exits (`needs-human`, `wont-do`).
2. `pilot.py contract <phase>` prints that one phase's contract; its skill refers to it instead of restating it.
3. A test checks the composition offline: every produced status has a consumer, every consumed status a producer,
   `done` and `wont-do` being the only sinks.
4. `set` warns (a `warning` field, no refusal) on a transition no contract allows; a refusal comes only after a
   run on `pilot-test` shows which real transitions occur (a refusal changes behavior: major version).
5. Only then do the per-status paragraphs shrink.

## 5. Order and risk

Each step is checked on its own; none ships without the file as a whole re-read.

1. **Rule** in `CLAUDE.md` §3: a phase documents only its contract; what links two phases is a link doc.
2. **Contracts as data** in the script, with `contract` and the composition test (backward compatible).
3. **Moves**, one PR per group: Spec-only content, QA, link-doc duplicates, mechanisms the script owns.
4. **Shrink** the generic file and add a size ceiling test so it cannot grow back.

Risk: this is the product itself, so a rule lost in a move changes behavior. Mitigation: move without rewriting,
`grep` every `§` reference and quoted heading afterwards, re-run the walkthrough scenarios on `pilot-test`.
