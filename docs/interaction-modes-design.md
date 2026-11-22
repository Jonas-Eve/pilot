# PILOT — interaction modes and the analyze / propose / challenge cycle (design proposal)

Status: **decisions taken (§8). Built: Discovery and Spec, then Dev, Review, Design, Proto and the drafting duties of Architecture, Wiki and Flow (QA gets no `--human`).** Human-only document: no skill or agent reads it, and it is not copied into a project.

## 1. The idea

Today a run has two modes. **Pair**: the agent proposes, a live human iterates with it. **`--auto`**: the agents decide everything, one pass, no checkpoint.
Two changes, one frame.

1. A third mode, where the **human proposes** and the agent helps them decide (working name `--human`; see §8).
2. A **cycle every skill follows, whatever the mode**:

   1. **Analyze** the existing (product via the wiki, code, architecture), for what the ticket or request touches. Written down, sourced, shown to the human.
   2. **Propose** — the only step the mode changes: the human (`--human`), the agent with the human (pair), the agent alone (`--auto`).
   3. **Challenge** the proposal, wherever it came from: holes and inconsistencies against the existing; optimizations or improvements only when the human asks.
   4. Back to 2 as many times as needed, until everyone agrees.

In `--human` the agent still **writes** the tickets and the code; what the human decides is the plan and the decisions. The agent never fills a gap the human left: it asks.

## 2. Who goes through which steps

The cycle is per persona. The personas are the ones the roster already defines (`pilot-link-roster.md`); no new family of agents.

| Role | Analyze | Propose | Challenge |
|---|---|---|---|
| **Lead** (the step's main persona: the PM in Discovery, the dev in Dev…) | yes | yes, as the mode says | **yes** — the proposal, wherever it comes from |
| **Validator** (the roster's validator: the architect in Discovery, the PM on a Spec split…) | yes, against the proposal received | yes: verdict, objections, amendments | **no** |
| **Summoned** (`--with` or summoned mid-discussion: advisory, `pilot-task-advise.md`) | yes, only on the point raised | only if asked | only the point raised (a gap seen elsewhere is signalled in one line) |

- The validator has no challenge step: this is what stops the regress (a challenger of the challenger of…). Its objections are answered by the lead — accepts, rejects with arguments, or amends — which is the existing debate. A third party is only ever the human, when they are blocked.
- A summoned persona keeps `pilot-task-advise.md`'s rules (advises, never decides, never blocks alone, stops when it has nothing to add) and adds: it starts from the analysis already written and only adds the delta its point needs, with sources. In `--human` it proposes a solution only when the human asks; in pair it may offer one unasked.
- Every `Agent` call is an isolated context (`pilot-process.md` §5), so no extra "fresh agent" rule: what carries between calls is what the session passes (analysis, proposal, objections and answers) and the ticket (the proposal's checkpoints, a `needs-human` comment), never an agent's memory. A validator receives the deliverable, not the conversation, and returns with only its own objections (roster, "Validator").

## 3. What the challenge is worth

The challenge is an LLM acting as judge, with the usual limits (same model family, correlated blind spots, a tendency to find a plausible proposal fine). Rules that make it more than that:

- **Sourced objections only.** Each cites its source (code path, wiki entry, ADR). An objection without a source is dropped.
- **Objections or nothing**: no score, no global "looks fine". A round with no sourced objection ends the loop.
- **Independence comes from a different persona**, not from a fresh instance. In `--human`, the lead challenges the human's proposal and the validator then challenges it again: two independent looks. In pair and `--auto`, the lead challenges its own proposal: a **sourced self-review**, like `pilot-dev`'s before the PR, useful but not independent. Only a validator (another persona) is.
- It never replaces a human review: the exit for what the agents cannot settle stays `needs-human`.

## 4. Stopping

No round limit. Reuse `pilot-link-agent-dialogue.md` as is:

- **Everyone agrees** (in `--human`, the human's explicit agreement): done.
- **Genuine disagreement** — incompatible positions restated with nothing new: `needs-human` quoting every position; a live human decides on the spot. In `--human` the human is a party and present: they decide immediately, no `needs-human`.
- **Unproductive length** — everyone agrees but it keeps going: compare the proposal before and after a full round; no substantive change means converged.

## 5. Skills and modes

Pair-capable skills get `--human`. "Already" means the human already states the proposal and the agent drafts it, so `--human` adds almost nothing.

| Skill | Today | `--human` | `--auto` |
|---|---|---|---|
| `pilot-discovery` | pair only | new for drafting the stories; the framing stage (the PM alone with the human) is already human-led | no |
| `pilot-spec` (incl. `--tech`, `--bug`) | pair / `--auto` | new | yes |
| `pilot-dev` | pair / `--auto` | new (the human sets the approach, the agent codes) | yes |
| `pilot-review` | pair / `--auto` | new: the human decides the verdict, the reviewers analyze and object | yes |
| `pilot-qa` | pair / `--browser` | no (the plan derives from the acceptance criteria; the human already tests live) | no |
| `pilot-architecture` | pair only | already (`--guideline`, `--adr`, `--edit` start from the human's statement; the draft carries `conflicts` and `questions`) | no |
| `pilot-wiki` | pair; `--auto` on `--lint`, `--bootstrap` | already on `--edit`, `--deprecate`; no on `--lint`/`--bootstrap` (verification, the human arbitrates) | `--lint`, `--bootstrap` only |
| `pilot-design` | pair only | new | no |
| `pilot-proto` | pair only | new | no |
| `pilot-flow` | pair only | already on `--new`/`--edit`; no on running a flow | no |
| `pilot-auto` | dispatcher | no | yes |
| `pilot-dashboard`, `pilot-init`, `pilot-update`, `pilot-help` | mechanical / read-only | no | no |

The three mode flags `--pair`, `--auto` and `--human` are mutually exclusive with each other and each combines with `--resume`: a resumed run takes its mode from the ticket's checkpoint, which must record it, or from the flag given with `--resume`. `--human` is meaningless with `--multi` (no N agent proposals to compare). (A risk signal could once make a ticket pair-only; removed in 5.0.0, `docs/workflow-design.md`.) `--with` stays orthogonal.

## 6. The cycle, skill by skill

Persona columns come from the roster. **Independent challenge in pair/`--auto`** says whether a validator exists; where it does not, the lead's challenge is a self-review (§3) until a decision adds a validator.

| Skill | Lead | Validator | Summonable | Cycle relevant? | Independent challenge in pair/`--auto` |
|---|---|---|---|---|---|
| Discovery | PM | architect | designer | **Yes** | yes (architect) |
| Spec `type:feature` | architect + tech lead | PM | designer | **Yes** | yes (PM) |
| Spec `type:tech` | architect + tech lead | — | designer | **Yes** | self-review only |
| Spec `type:bug` | architect + tech lead, or tech lead | — | designer, or architect | **Yes** | self-review only |
| Dev | dev (e2e for `type:e2e`) | — | tech lead, architect, designer | **Yes, at the approach step**, not on finished code | self-review only |
| Review | tech lead + PM, or tech lead alone | — | architect | **The reviewers are the challenge step**: the cycle applies to the PR they challenge; the isolated parallel verdict is unchanged (`pilot-link-review-consensus.md`) | n/a |
| QA | qa | — | designer | Low (the plan derives from the criteria; the browser run is execution) | self-review only |
| Proto | designer, after the PM framed the idea | PM | architect | **Yes** | yes (PM) |
| Design | designer | — | PM, architect | **Yes** | self-review only |
| Architecture, wiki `--edit`, flow `--new`/`--edit` | the persona of the duty (to confirm per task doc) | — | — | **Yes** — what is missing is a systematic challenge, the analysis exists (`conflicts`, `questions`) | self-review only |
| `pilot-auto`, `dashboard`, `init`, `update`, `help` | — | — | — | None: no judgment of its own | — |

The skills marked "self-review only" keep the sourced self-review (decided). Adding a validator to one of them later changes neither the engine nor the cycle (for Dev, the tech lead is the natural candidate).

## 7. Where it lives

- **`pilot-process.md` "Interaction modes"** (generic, every phase): the cycle, the three roles, `--human`, the mutual exclusions.
- **A link doc** (e.g. `pilot-link-existing-analysis.md`): what the analysis contains, when it reaches the ticket (only with a `needs-human`), how a round's delta is fed to an isolated agent; the sourcing rule of §3. Read by every skill that runs the cycle. `pilot-link-agent-dialogue.md` stays the stopping rule, `pilot-link-roster.md` the roles.
- **Task docs**: one per duty, the persona's lens only (the architect's feasibility, the tech lead's code, the PM's acceptance criteria). `pilot-task-advise.md` gains the summoned persona's rules of §2.
- **`pilot.py`**: `workflow show` gives a ticket's mode; decide whether a project's `workflow` can default to `--human`.

A mechanism change that makes projects act differently: **major** version.

## 8. Decisions

1. **Name**: `--human` (says who decides; `--manual` suggests the agent is hands-off, but it still writes and codes).
2. **Review**: the human decides the verdict and may add what to check; the reviewers stay isolated and parallel and return sourced objections. Nothing is submitted to GitHub before the human decides, except a `needs-human`, which still goes out at once.
3. **Cost**: the analysis is bounded by its sources: it covers only what the ticket touches (`wiki search`, `arch index --active`, the code paths concerned) and lists what it does not cover. Later rounds redo only the delta.
4. **Where the analysis is written**: nowhere by default — it stays with the session (shown to the human, passed between calls). It is written to the ticket only when the work leaves the session: a `needs-human` flag's comment carries the part that bears on the blocker; a `--resume` that finds none runs a fresh analysis; the ticket body stays the deliverable. It is not reused across phases (it goes stale): each phase redoes its own delta.
5. **Default mode**: stays pair. `--human` is an explicit flag, never a project default (it needs a live human, so no sweep or Routine can take it); a `workflow` value for it can come later without touching the cycle.
6. **Scope**: two PRs. First the generic base (`pilot-process.md`, the link doc, the task docs) with Discovery and Spec, which already have a validator; then the other pair-capable skills.
7. **Who analyzes**: the first analysis is an agent's turn (one measured case: about 2 000 tokens kept in the session against about 8 500 if the session read the same material, at about ten times the total cost); the session answers targeted factual questions between rounds from a cited lookup and never rewrites the analysis.
