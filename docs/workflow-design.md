# PILOT — adaptive workflow (design proposal)

Status: **proposal, nothing implemented**. Human-only document: no skill or agent reads it, and it
is not copied into consuming projects. Once validated, the contract moves into `assets/docs/` and
this file is removed. Companion of `docs/roles-matrix.md` (who does what today) and
`docs/modules-design.md` (the module switch this builds on).

## 1. Goal

One workflow that is the least constraining, the safest and the fastest for a given project and a
given ticket, instead of one fixed chain for everyone. Two projects drive it: `pilot` itself
(maintainer = PM = user, mechanism changes, a framework) and myAVI Mobility (a multi-tenant product
for people with disabilities, a proof of concept with strict identity and tenant-isolation rules).

Today adaptation happens per call (`--auto`, `--with`, `--only`, `--multi`) and per module
(on/off). The chain itself, its personas and its phases are the same everywhere, and nothing
records why a ticket took a given path.

## 2. Principle

Put the constraint where the risk is, nowhere else. Three independent axes:

1. **Project profile**: fixed at init in `.pilot/state.json`: `lean` or `standard`, which steps and
   personas by default.
2. **Ticket risk**: objective signals, each carrying its own roster additions for that one ticket.
3. **Interaction mode**: pair or auto. Exists today, unchanged.

## 3. Profiles

Two, not three: what a third `strict` profile would have bought is expressed as risk signals
(section 4), per ticket, instead of a per-project level that taxes every ticket.

| | `lean` (pilot) | `standard` (myAVI) |
|---|---|---|
| Discovery | optional | PM + architect |
| Spec, `type:tech` | tech lead alone; the architect validates on a signal and **leads** when the ticket declares dependencies, names several apps, or the tech lead's pass finds it must split | tech lead leads, the architect always validates (one call), and leads on the same triggers |
| Spec, `type:feature` | architect + tech lead | architect + tech lead |
| Dev | auto | pair by default, or auto with pair forced by a signal |
| Review | tech lead alone | tech lead (+ PM for feature/e2e) |
| Human QA | none | features, depth set by signal (see section 4) |
| Default mode | auto | pair |

Discovery keeps the architect as contributor and validator in every profile that has a
Discovery: a story badly thought out there makes the rest of the chain wrong.

## 4. Risk signals

A signal is a rule a script can evaluate (labels, paths touched, keywords in the ticket), never an
agent's opinion. Each one carries the **additions** it makes to the roster of that ticket, rather
than "raising one level". Examples, declared per project in `.pilot/state.json` with a default set
in `pilot.py`:

| Signal | Additions |
|---|---|
| Touches labels or statuses (`pilot`) | pair only, architect validates the spec |
| Touches identity, JWT, tenant isolation, `X-Internal-Secret` (myAVI) | pair only, architect validates the spec and joins the review |
| `type:feature` on the front (myAVI) | designer summoned in Spec, accessibility audit (RGAA) before review, human QA includes the cases automation cannot reach (screen reader, Android back, iOS gesture, mobile focus) |
| Public contract, security or data, conflict with an ADR or guideline, `priority:P0` | pair only, architect validates |
| `needs-human` raised on the way | stops, a human decides (as today) |

A ticket with a signal is pair-only (the cockpit's `pairOnly`). Keep the list short at first,
three or four signals, and grow it from what the measurements show.

## 5. What never changes, whatever the profile

Labels, claim protocol, state machine, `needs-human`, and the rule that only a human merges
(unless `--merge` is passed explicitly). Profiles change which steps a ticket traverses and which
personas sit in the roster, never the vocabulary.

## 6. Safety without weight

- **Mechanical checks first**: tests, `VersionBumpTests`, `arch lint`, `wiki lint`, `contract`;
  for `pilot` a cross-reference lint to replace the greps CLAUDE.md asks for by hand. An agent
  judges only what a script cannot.
- **The validator is the economy mechanism**: one call on the deliverable, cheap when there is
  nothing to object to.
- **Performance**: parallel reviewers (as today), no step the profile does not need, `--auto`
  sweeps for `lean`.

## 7. What it asks of the core

- A `workflow` block in `.pilot/state.json` (profile, default mode, escalation rules), read by
  `pilot.py` the way it reads `modules`.
- `pilot.py contract` checks that every path a profile allows composes (no status without a
  producer or a consumer); today it checks the single chain.
- The roster becomes one table per profile instead of one fixed table.
- `pilot.py snapshot` adds, per ticket, its **route**: effective profile, the signals that apply,
  the roster of its next step, whether auto is allowed.
- Probably a **major** version: a project acts differently.

## 8. The cockpit

The cockpit holds no workflow logic: it shows what the snapshot gives it, as it already does for
`modules` (`TAB_MODULE`). GitHub labels and `state.json` stay the source of truth; `pilot.py`
computes the route.

- **Banner**: active profile as a badge, linking to the roster table of that profile.
- **Phases from data**: `PHASES` is no longer a constant; a phase absent from the profile is
  hidden or greyed.
- **Route per ticket**: chips with the effective profile and which signals added guardrails, e.g.
  "pair only: label change". Filter "tickets with a signal" and `needs-human` at a glance.
- **"My queue" follows the step's roles**: a ticket where the architect validates shows in the
  architect's queue only at validation time.
- **Launch buttons**: the command text stays simple (`/pilot-spec 123`): the skill reads the
  profile in `state.json` and composes the roster, so the cockpit cannot drift from the skills.
  The cockpit varies only the mode and the options: which button is primary (auto for `lean`,
  pair for `standard` or a ticket with a signal), auto hidden when the route is pair-only, and the
  Options panel (`WITHS`, `--only`, `--multi`, `--next`) read from the profile's roster instead
  of the hard-coded table.
- **"i" help**: the active profile, what each mode does in it, and why a given ticket is
  pair-only.
- **Metrics, to tune the profiles**: from the events the cockpit already receives, per profile
  and per phase: agent calls per ticket, time per status, validator objection rate,
  `needs-human` rate. This is the measurement needed to decide whether the architect earns its
  calls on a `type:tech`.
- **Not a control surface**: changing profile is a command (`pilot.py workflow set <profile>`),
  not a button.
- **Compatibility**: a snapshot without a `workflow` field renders today's full chain, like a
  snapshot without `modules` shows every tab.
- **Development**: on the demo artifact with fake data, never a real project's dashboard;
  `scripts/test_dashboard.js` changes with the page.

## 9. Open questions

1. myAVI's non-negotiable risk. Resolved from the repository (315 issues, 260 merged PRs; 51 % of
   issues are `type:tech`, 74 of those 162 mention security, 121 tenants): identity and tenant
   isolation first. Accessibility is already enforced mechanically in the front components and
   their tests; the open gap is new screens and flows, covered by the `type:feature` signal above.
2. Does the state machine admit a path that skips Spec's dialogue (`lean`) without a new status?
   `contract` should answer before any code.
3. Signals: declared per project in `state.json` with a default set in `pilot.py` (as written
   above); confirm the schema, and who may edit it.
4. Is the profile per project only, or can a monorepo set one per app?
5. QA granularity: per story (today) or batched per epic or per release? 20 of myAVI's 25 open
   feature stories wait at `status:qa`; none has ever closed through QA, so the epics above them
   cannot close either (they auto-close once every story is closed).
6. Mode of Dev: no measurement could separate auto from pair (section 11), so the default per
   profile stays a choice until PILOT records the mode in a field instead of inferring it.

## 10. Rollout

1. Apply `lean` to `pilot` itself first, through PILOT (type:tech tickets, no new ticket types).
2. Measure a few tickets (agent calls, objections, time) before generalising.
3. Define `standard` and its signals with myAVI's real constraints (migration from PILOT 2.9.0:
   no `workflow` block means today's chain).
4. Cockpit changes on the demo artifact, then published with the release.

## 11. Evidence from myAVI (measured 2026-11, read-only)

Source: the `myavimobility` repository (PILOT 2.9.0, 315 issues, 260 merged PRs). Figures come from
GitHub search counts and from agents that read reviews, tickets and comments; each caveat below
matters, the samples are small and come from one project.

| Measure | Result |
|---|---|
| Ticket mix | `type:tech` 162 (51 %), `feature` 95, `bug` 36, `e2e` 22; 74 of the 162 tech tickets mention security, 121 tenants |
| Review outcome (80 PRs with a PILOT review) | 64 approved first time (80 %), 16 changes requested (20 %), all approved on the next round |
| Review by type | `fix` 0 of 11 blocked, `feat` 13 of 55, `test` 3 of 12 |
| Who blocked (first 40 PRs, 12 blocking points on 7 PRs) | tech lead 11, PM 1 (borderline wording), architect 0 (never a reviewer); 0 product-fit blocks; nature: tests 5, docs or skills 5, security 1, spec conformance 1 |
| Review likely run without a human (60 PRs: 22 explicit `--auto`, 38 `--merge` runs inferred as unattended) | 22 % changes requested, every one fixed and approved next round |
| Bug origin (36 bugs) | e2e 9, review 7, dev 3, Spec 1, human QA 0, unknown 16 |
| Spec on 15 closed `type:tech` stories | 4 split (15 tasks), 11 unsplit; the architect added substance on 7 (split shape, dependencies, re-scoping, concrete decisions), confirmed only on 1, 7 undeterminable; one explicit tech lead objection changed the spec |
| Human QA | no story has gone through it yet (19 at `status:qa`, 1 at `in-qa`); the maintainer says it is coming |

Caveats: reviews are submitted as `COMMENTED`, so verdicts are read from the text; the mode (auto or
pair) is inferred from the submitting account and wording and is confounded with author and type of
work; in pair mode a human fixes some defects before the review, so they never show; checkpoint
comments record outcomes, not the dialogue, so who proposed what in Spec is inferred.

### What each cell stands on

| Cell | Standing |
|---|---|
| Review `fix`/`tech`, tech lead alone | **supported** |
| Review without a human present | **supported**, with the mode inferred for 38 of the 60 PRs |
| Spec: architect leads on declared dependencies or several apps; validates otherwise | **partly supported**; both triggers are known before Spec starts, a script can read them. "Will split" is an outcome, so it only counts once the tech lead's pass finds it |
| Review `feat`/`e2e`, PM | review is useful (24 % of `feat` blocked) but the PM's share is **not shown**: lighten it only after a measure that attributes catches |
| Spec `type:feature`, Discovery, Dev mode, QA default | **a choice**, no measurement |

Next measures: lead time by type (creation to closure); a field in PILOT recording the mode of each
run; the first QA runs, to see what human QA finds that e2e and review do not.
