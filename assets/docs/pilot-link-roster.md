# PILOT link — the roster of a discussion

Read by every skill that runs or can summon a discussion between personas: `pilot-discovery`, `pilot-spec`, `pilot-dev`, `pilot-review`,
`pilot-qa`, `pilot-design`, `pilot-proto` and `pilot-auto`. The turn-taking of Discovery and Spec is `.pilot/pilot-link-agent-dialogue.md`.

## Roster: who is in the discussion

A phase run is one discussion between the human and agents. Each step has fixed
leads, an optional validator, and personas the human may summon:

| Step | Lead(s) | Validator | Summonable |
|------|---------|-----------|------------|
| Discovery | `pilot-pm` | `pilot-architect` | `pilot-designer` |
| Spec — `type:feature`/`type:tech` | `pilot-architect` + `pilot-techlead` | `pilot-pm` (`type:feature` only) | `pilot-designer` |
| Spec — `type:bug`, raw report (no ticket yet) | `pilot-architect` + `pilot-techlead` | — | `pilot-designer` |
| Spec — `type:bug`, existing ticket | `pilot-techlead` | — | `pilot-architect` |
| Dev | `pilot-dev` (`pilot-e2e` for `type:e2e`) | — | `pilot-techlead`, `pilot-architect`, `pilot-designer` |
| Review | `pilot-techlead` + `pilot-pm` (`type:feature`/`type:e2e`), `pilot-techlead` alone (`type:tech`/`type:bug`) | — | `pilot-architect` |
| QA | `pilot-qa` | — | `pilot-designer` |
| Proto (`/pilot-proto`, not a phase) | `pilot-designer`, after `pilot-pm` has framed the idea alone with the human | `pilot-pm` | `pilot-architect` |
| Design (`/pilot-design`, not a phase) | `pilot-designer` | — | `pilot-pm`, `pilot-architect` |

- **Lead.** The skill opens the discussion with the lead(s). `--with <persona>[,...]`
  (any phase skill) adds personas from that step's Summonable column from the start; any
  other name is refused.
- **Validator.** Once the human says the lead's work is done, the validator joins the
  same discussion and is given the deliverable only — not the discussion. Approves →
  the step continues. Objects → it stays for the debate with the lead(s) and the human;
  once the lead(s) have revised or contested the objection it goes dormant (no calls
  while they work), then returns with only its own objections plus the revised
  deliverable and gives a new verdict. Repeat until it approves: the verdict is always on
  a deliverable, never on a conversation.
- **Summon / dismiss.** The human may at any time summon a persona from the step's
  Summonable column, or dismiss any persona in the discussion; a dismissed persona gets no
  further call. Dismissing the last lead, or the validator, before the deliverable is
  validated is refused — replace the validator instead by summoning one from the column, or
  end the step with `needs-human` stating it was not validated. Each summon, dismissal and
  validator verdict is recorded in the step's own checkpoint (above).
- **Context.** Every call stays isolated (`.pilot/pilot-process.md` §5): a persona entering mid-discussion receives
  the ticket's latest checkpoint — never the transcript — and, from then on, only the
  messages posted since its own last turn (a validator: the deliverable, then the same).
  A persona may ask the skill to show one specific earlier message.
- **Advisory personas never block.** `pilot-designer` advises; its objection alone never
  justifies `needs-human`.
- **`--auto`** (no human, so no summon/dismiss; `--with` still applies): leads, then
  validator, run in sequence; an objection sends the validator and lead(s) into the
  turn-taking dialogue of `.pilot/pilot-link-agent-dialogue.md` (no round cap),
  `needs-human` only for the genuine disagreement that doc describes.
- **Review** keeps its parallel, isolated reviewers (`.pilot/pilot-link-review-consensus.md`): `--with` there extends the
  reviewer set at the start (`--only` instead fixes the exact set), and nothing can be summoned mid-run.

---
