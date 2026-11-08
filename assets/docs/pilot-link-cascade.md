# PILOT link — the merge workflow and cascading completion

Read by `pilot-dev`, `pilot-review`, `pilot-qa` and `pilot-spec` wherever a ticket reaches `status:done` or `status:qa` without a phase
setting it: `.github/workflows/pilot-status-on-merge.yml` does, independent of any agent session being alive. Cited by the
epic-descent and e2e-tasks link docs.

## What sets `status:done`

`status:done` closes a ticket that was merged (a task, or an unsplit `type:tech` story), completed by cascade (a `status:split` story, "Cascading completion" below)
or, for a `type:feature` story, confirmed in phase 5. A phase never sets it for an actionable ticket coming out of a merge — a merge is a human action or, for
phase 4, an explicit `--merge` run, both outside PILOT's control when it happens. The `.github/workflows/pilot-status-on-merge.yml` GitHub Actions workflow
sets it, independent of any agent session being alive:
- Triggered on `pull_request: closed` (gated on `merged == true`): resolves the issue(s)
  the merge closes via `PullRequest.closingIssuesReferences`, sets `status:done` on each,
  and, for any that's a task, runs the cascading-completion check ("Cascading completion" below) against its `status:split` parent story, then, if that story itself just
  closed, against its own parent Epic in turn. This is the only place `status:done` gets
  set on an actionable ticket coming out of a merge.
- Also triggered on `issues: closed`, for completions that never go through a PR merge at
  all: `status:wont-do`, which Spec sets and closes directly, and any hand-closed
  issue. This path only runs the cascading-completion check ("Cascading completion" below) — never sets `status:done` itself, since the closing party is
  responsible for the issue's own terminal `status:` label — and only when the issue
  already carries `status:done` or `status:wont-do`. It skips entirely when GitHub's own
  timeline shows the closure came from a merged commit reference, so the same closure is
  never processed twice.

`/pilot-qa` is the one place a phase skill *does* set `status:done` directly, once a
human confirms the story's behavior in phase 5 (`.claude/skills/pilot-qa/SKILL.md`) — there's no PR merge there for the
workflow to react to.

**Known limitation:** GitHub only recognizes a `Closes #N` reference (populating
`closingIssuesReferences`, which the workflow reads) when the merging PR's base is the
repository's *default* branch — never for a PR merged into an intermediate,
not-yet-merged branch, even once that branch later reaches the default branch itself.
If a ticket's implementing PR had to be based on another PILOT PR's branch instead of
the default branch directly, the workflow finds zero closing issues on that merge and
does nothing — set `status:done` on the ticket by hand once everything has actually
landed on the default branch. Not fixable in the workflow itself; a GitHub platform
behavior.

## Cascading completion

This applies to `status:split` stories only — a story's tasks are a fixed set for
whichever round is currently in flight (the original split, or a later re-scope round,
`.pilot/pilot-link-split-tickets.md` "Re-scoping a `type:feature` story after its split is done"), so completeness at
any given moment is provable from a live read of its current sub-issues — never a cached
list. An Epic's own story set can grow while it stays open — new stories are added under
it at any point — but once every one of them is closed (`status:done` or `status:wont-do`),
that's the Epic's own definition of done: the same live read, one level up, closes it too
(below), and that closure is final — it is never reopened to take another story back in.

Whenever a task reaches `status:done` or `status:wont-do`, check whether its parent
is a `status:split` story and, if so, whether *all* of that story's other tasks are
now also done/wont-do. A standalone `type:bug` task has no parent at all (`.pilot/pilot-link-ticket-tree.md` "Three levels") — this check simply finds none and does nothing further; the bug ticket's own
`status:done`, set directly on merge, is the end of it.
- Not all done yet → do nothing further, the parent stays `status:split`.
- All done, parent is `type:tech` (the only root type that can reach `status:split`
  without being `type:feature` — `type:bug` is never even a `level:story`, so it never
  has a parent to check in the first place) → set the parent story itself to
  `status:done` **and close its issue** — it was never merged directly, so nothing else
  in the pipeline would otherwise ever close it (unlike a task, whose merging PR closes it
  natively via `Closes #N`).
- All done, parent is `type:feature` → set the parent to **`status:qa`** instead of
  `status:done` (`.claude/skills/pilot-qa/SKILL.md` "Phase 5 — Human QA") — every `type:feature` split includes exactly
  one e2e task depending on all its dev siblings, so "all done" here is structurally the
  same moment the e2e task itself just finished. `status:done` for this story is set
  later, by `/pilot-qa` itself, once a human confirms the behavior.

Whenever a story's own issue closes — cascaded to `status:done` just above, closed
directly as `status:wont-do` (Spec), or closed by `/pilot-qa` once QA'd — also check
its own parent: if it belongs to an Epic and *every* one of that Epic's stories is now
closed (`status:done` or `status:wont-do`), close the Epic's issue too. An Epic carries no
`status:` label, so closing its issue is the whole of it — and it's terminal: a related
need afterward starts a new Epic, never a story reopening this one.

No periodic sweep exists beyond this — the check is event-driven, not polled. A
`status:split` story whose last task was closed without ever carrying
`status:done`/`status:wont-do` (mislabeled outside PILOT's own conventions) is the one
case this still can't catch, since there is no terminal-status event to react to.
