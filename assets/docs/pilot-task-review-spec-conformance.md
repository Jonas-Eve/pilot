# PILOT task — Review spec conformance and code quality

Injected by `.claude/skills/pilot-review/SKILL.md` into the `pilot-techlead` persona's
prompt, alongside `.pilot/pilot-link-review-consensus.md` for the shared verdict format and
`change`/`decision` tagging rule.

**Verification is the review's first job.** For every binding wiki or architecture entry that bears on the PR (`.pilot/pilot-link-knowledge.md` "What binds": found from the PR's changed paths and
the ticket's own words, not by scanning the bundle), open it and check the PR against it; return with your verdict a **Checked against** list — each entry's id and `conforms`, `change` or `decision`. An
entry you did not open is not claimed as checked, and a binding entry that bears on the PR with no line in your list makes your verdict incomplete.

Before forming your verdict, **re-run the relevant validation commands directly against
the PR's branch** (the same build/test/lint commands the dev persona used in phase 3)
rather than trusting the PR description's claim that tests pass — a failure despite that
claim is an automatic block. This matters most with no CI yet, since your re-run is the
only check that actually executes anything; once CI exists, treat a red or pending run
the same way.

**Wiki** (only when the prompt carries entries): also run `python3 .pilot/pilot.py wiki lint` on the
PR's branch — a finding is a `change`. The entries state what the code must do. Behavior the PR adds
or changes that no entry states, an entry the PR leaves contradicting its code, or an entry moved to
`implemented` while another dev task it lists is still open (or the other way round: the PR completes
an entry and leaves it `specified`) is a `change`. An entry the code cannot satisfy as written is a
`decision`. An entry the PR moves to `implemented` is verified by you, independently of the dev: read its `Verified:` line in the PR body and replay its command. The stamp stands only if the result is the same, the command tests what the entry
states in every detail it states, and only files under `wiki/` changed since the stamp's commit. A stamp with no `Verified:` line, a proof you cannot replay or that does not test the entry, or a stamp on any other entry, is a `change`. A
`not by command` line is accepted when its reason holds and the entry carries no stamp. Code that does something else than the entry states is a `decision`.

**Architecture** (only when the prompt carries the architecture index): open the entries that bear on the PR
(`arch show <id>`) and run `python3 .pilot/pilot.py arch lint` on the PR's branch when it changes `architecture/` — a
finding is a `change`. Code that breaks a guideline or contradicts an accepted ADR is a `change`; code that
needs to break one is a `decision`. A PR that edits an accepted ADR instead of superseding it is a `change`. A PR that changes a fact a `reference` entry states (a version, a table, a folder, a command) without updating that entry is a `change`.

Then review the shipped PR for two separate things, giving each its own attention rather
than letting the first crowd out the second:
- **Spec conformance** — does the implementation match the ticket's own spec, and if it
  deviates, is the deviation justified.
- **Code quality/maintainability** — readability/naming, whether tests actually exercise
  the claimed behavior (not just present), edge cases the diff misses, and anything you'd
  flag in a normal review regardless of spec match — including whether TDD was actually
  followed: check the commit history for a failing-test commit preceding the
  implementation commit(s) that fix it (`.pilot/pilot-task-implement.md` step 3). If the
  history doesn't show this clearly (squashed/force-pushed commits, tests and
  implementation mixed together), that's itself a `change`-worthy quality gap — don't
  assume test-first happened just because the PR says so. **Exception: `type:e2e` tasks**
  (implemented by `pilot-e2e`, not `pilot-dev`) have no red-green-refactor history by
  design (`.pilot/pilot-task-implement-e2e.md`) — judge them instead on whether the test
  exercises the real, already-merged integration points it claims to, without mocking
  them away. There's no separate reviewer here: `pilot-dev` already self-reviewed the
  diff before opening the PR (`.pilot/pilot-process.md` §4 "Interaction modes"), so your
  check is independent of, not a duplicate of, that self-review.
