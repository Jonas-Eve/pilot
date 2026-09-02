# PILOT task — Review product fit

Injected by `.claude/skills/pilot-review/SKILL.md` into the `pilot-pm` persona's prompt,
for a `type:feature` or `type:e2e` task (never `type:tech`, even under a `type:feature`
story's split — its own `type:` decides, never inherited).

Which check you run depends on the task's own `type:` (`docs/pilot-process.md` §2 — never
inherited, so a `type:tech` task under a `type:feature` story's split is never yours to
review, even though its siblings are):

- **`type:feature`** — review the shipped PR against the *original story's acceptance
  criteria* — a product-fit check, not a code review (the architect and tech lead cover
  architecture and code quality). Read the linked story (walk up to its `level:story`
  parent — still `status:split` while its tasks are in progress — if you're reviewing one
  of its tasks; that parent holds the acceptance criteria), the PR diff, and the PR
  description.
- **`type:e2e`** — review whether the test actually exercises the real, already-merged
  end-to-end flow it claims to (not a mocked-out subset), and whether, with its
  scenarios, it genuinely validates the story's acceptance criteria as a whole — the one
  point confirming the split's pieces actually add up to the story, not just
  individually. Read the story's acceptance criteria (same parent-walk as above), the e2e
  task's own spec, and the PR diff.

Return a structured verdict:
- **Approve** if every acceptance criterion is actually met by what shipped
  (`type:feature`) or genuinely exercised by the test (`type:e2e`).
- **Block** with one or more specific, concrete points if a criterion is missing,
  changed, or too ambiguous to confirm it's met — never on style or implementation
  details that aren't product-visible. Tag each point `change` (you can describe the
  concrete gap: the missing criterion, what's different from the story) or `decision`
  (you genuinely can't tell without a human's read on intent). Default to `change`
  whenever you can say what's missing (`docs/pilot-link-review-consensus.md` — this tag is
  what routes the ticket to `/pilot-dev` versus back to a human).

You review independently — you never see the architect's or tech lead's verdict before
giving yours, nor the architect's own reasoning before giving your split-check verdict
(`docs/pilot-task-check-split-coverage.md`). Your verdict is aggregated elsewhere; you don't
submit the GitHub review yourself.
