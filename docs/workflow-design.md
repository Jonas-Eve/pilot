# PILOT — adaptive workflow (design proposal)

Status: **proposal, nothing implemented**. Human-only document: no skill or agent reads it, and it
is not copied into consuming projects. Once validated, the contract moves into `assets/docs/` and
this file is removed. Companion of `docs/roles-matrix.md` (who does what today) and
`docs/modules-design.md` (the module switch this builds on).

## 1. Goal

One workflow that is the least constraining, the safest and the fastest for a given project and a
given ticket, instead of one fixed chain for everyone. Two projects drive it: `pilot` itself
(maintainer = PM = user, mechanism changes, a framework) and a product such as myAVI Mobility
(users with specific needs, real-world equipment data: accessibility and reliability matter).

Today adaptation happens per call (`--auto`, `--with`, `--only`, `--multi`) and per module
(on/off). The chain itself, its personas and its phases are the same everywhere, and nothing
records why a ticket took a given path.

## 2. Principle

Put the constraint where the risk is, nowhere else. Three independent axes:

1. **Project profile**: fixed at init in `.pilot/state.json`: which steps and personas by default.
2. **Ticket risk**: objective signals that raise one ticket to a stricter profile.
3. **Interaction mode**: pair or auto. Exists today, unchanged.

## 3. Profiles (hypothesis, to validate)

| | `lean` (pilot) | `standard` | `strict` (product with accessibility needs) |
|---|---|---|---|
| Discovery | optional | PM + architect | PM + architect, designer summoned |
| Spec | tech lead leads, architect validates on risk | architect + tech lead | + PM validates, designer summoned |
| Dev | auto | pair | pair |
| Review | tech lead alone | tech lead (+ PM for feature) | tech lead + PM + architect, accessibility check |
| Human QA | none | features | features, accessibility cases |
| Default mode | auto | pair | pair |

Discovery keeps the architect as contributor and validator in every profile that has a
Discovery: a story badly thought out there makes the rest of the chain wrong.

## 4. Risk signals

A ticket is raised one profile when any signal holds. Signals are mechanical (a script computes
them), never an agent's opinion: a change to labels or statuses (for `pilot`), a public contract,
security or data, a conflict with an ADR or guideline, `priority:P0`, a sensitive path touched,
a `needs-human` raised on the way. A raised ticket is pair-only (the cockpit's `pairOnly`).

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
- `pilot.py snapshot` adds, per ticket, its **route**: effective profile, the signal that raised
  it, the roster of its next step, whether auto is allowed.
- Probably a **major** version: a project acts differently.

## 8. The cockpit

The cockpit holds no workflow logic: it shows what the snapshot gives it, as it already does for
`modules` (`TAB_MODULE`). GitHub labels and `state.json` stay the source of truth; `pilot.py`
computes the route.

- **Banner**: active profile as a badge, linking to the roster table of that profile.
- **Phases from data**: `PHASES` is no longer a constant; a phase absent from the profile is
  hidden or greyed.
- **Route per ticket**: chips with the effective profile and why a ticket was raised, e.g.
  "raised to standard: label change". Filter "raised tickets" and `needs-human` at a glance.
- **"My queue" follows the step's roles**: a ticket where the architect validates shows in the
  architect's queue only at validation time.
- **Launch buttons**: the command text stays simple (`/pilot-spec 123`): the skill reads the
  profile in `state.json` and composes the roster, so the cockpit cannot drift from the skills.
  The cockpit varies only the mode and the options: which button is primary (auto for `lean`,
  pair for `strict` or a raised ticket), auto hidden when the route is pair-only, and the
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

1. myAVI's non-negotiable risk: accessibility of journeys, reliability of equipment state, or
   both. It sets what `strict` requires (the designer, an accessibility audit, which QA cases).
2. Does the state machine admit a path that skips Spec's dialogue (`lean`) without a new status?
   `contract` should answer before any code.
3. Where do risk signals live: `state.json` (per project) or a default set in `pilot.py`
   overridden per project?
4. Is the profile per project only, or can a monorepo set one per app?

## 10. Rollout

1. Apply `lean` to `pilot` itself first, through PILOT (type:tech tickets, no new ticket types).
2. Measure a few tickets (agent calls, objections, time) before generalising.
3. Define `strict` with myAVI's real constraints, then `standard` as the default.
4. Cockpit changes on the demo artifact, then published with the release.
