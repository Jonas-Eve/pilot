# PILOT — who does what at each step (roles review)

Human-only document: no skill or agent reads it, and it is not copied into consuming projects.
Source of truth stays `assets/docs/pilot-link-roster.md` and the `pilot-task-*.md` docs; this file
is a review of them, to check every persona sits where it should and to decide what to lighten.

Legend: **L** lead · **V** validator (gets the deliverable only, one verdict) · **R** reviewer
(parallel, isolated) · **S** summonable by the human (`--with`, summon).

## 1. Matrix

| Step | PM | Architect | Tech lead | Dev / e2e | QA | Designer |
|---|---|---|---|---|---|---|
| Discovery | L: `frame-idea`, `write-story` | V + co-author: `anticipate-architecture` | — | — | — | S |
| Spec, no-ticket entry (`--tech`/`--bug`) | — | L: `challenge-need`, then `formalize-tech-need` / `formalize-bug-report` | L: `verify-need` | — | — | S |
| Spec, `feature`/`tech` | V: `check-split-coverage` (feature only) | L: `scope-story` | L: `write-spec` | — | — | S |
| Spec, bug on an existing ticket | — | S | L alone: `write-spec` | — | — | — |
| Dev | — | S | S | L: `implement` (+ `implement-e2e`) | — | S |
| Review, `feature`/`e2e` | R: `review-product-fit` | S: `review-architecture` | R: `review-spec-conformance` | — | — | — |
| Review, `tech`/`bug` | — | S | R alone | — | — | — |
| QA | — | — | — | — | L: `human-qa` | S |
| Proto | L: `frame-proto`; V: `check-proto` | S | — | — | — | L: `build-proto` |
| Design | S | S | — | — | — | L: `write-design-system` |
| Modules | `wiki-entries` | `architecture-bootstrap`, `architecture-adr` | `wiki-lint`, `wiki-bootstrap` | — | — | — |

Each persona keeps one identity across its duties: PM = product value, architect = soundness,
security and consistency, tech lead = feasibility and conformance against the real code, dev/e2e =
execution, QA = human testing, designer = usage.

## 2. Well placed

- Discovery: the PM frames, the architect contributes and validates.
- Review: independent reviewers; `tech`/`bug` go through the tech lead alone.
- Dev, QA, Proto, Design: one clear lead, no overlap.
- The designer never blocks.

## 3. Heavy or misplaced

1. **Spec `feature`/`tech` has two leads in alternating dialogue** — the only step built that way.
   For an unsplit `type:tech`, the architect's contribution (challenge, build-or-`wont-do`,
   security/architecture decisions, priority) is validator-shaped.
2. **The no-ticket entry stacks stages.** The architect speaks three times before a spec exists
   (`challenge-need`, `formalize-*`, then `scope-story`); the tech lead reads the code twice
   (`verify-need`, then `write-spec`).
3. **Discovery's architect is a validator and a co-author** (Architecture notes, body of a
   `type:tech` enabler story). Decided: keep it. A ticket badly thought out at Discovery makes
   the rest of the chain wrong, so the architect shapes the story, it does not only judge it. The
   roster should say "validator and contributor" rather than plain validator.
4. **Review's architect duty is nearly empty** (`review-architecture`, 8 lines), while the tech
   lead already checks conformance against guidelines and ADRs when the `architecture` module is
   on. Keep it optional (`--with`), never in a default set.
5. **The PM may be called in Spec for `wiki-entries`** with the `wiki` module on. To check whether
   this also applies to a `type:tech`, which has no product promise to write.
6. Dev self-reviews before the PR and the tech lead reviews after: intended (`implement.md` 5a),
   not a defect.
7. `pilot-e2e.md` called the e2e persona "phase-4"; Dev is phase 3. Fixed.

## 4. Proposed changes (mechanism, to go through PILOT itself)

| # | Change | Level |
|---|---|---|
| 1 | Spec `type:tech`: tech lead leads; the architect validates the deliverable (one call when nothing to object to) and leads instead when the ticket declares dependencies, names several apps or must split (`docs/workflow-design.md` section 3). `type:feature` keeps the architect as lead (split, mandatory e2e). | minor |
| 2 | `--tech` entry: fold `verify-need` into the tech lead's own pass; run `challenge-need` only when the request is vague. | minor |
| 3 | Roster: Discovery's architect named "validator and contributor". Wording only. | patch |
| 4 | Review: architect stays optional, not in a default set. No change. | — |
| 5 | Check `wiki-entries` at Spec for `type:tech`. | patch or none |

Measure before changing 1 and 2: run a few `type:tech` tickets through the full path, note how many
calls the architect uses and how often it changes something substantive.
