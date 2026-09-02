# PILOT task — Formalize a raw `type:bug` report

Injected by `.claude/skills/pilot-story/SKILL.md` into the `pilot-architect` persona's
prompt, when the raw need auto-detects (or is declared via `--bug`) as a defect report.

You receive a raw bug report in free text — a human's account, or a technical trace
(failing assertion, error log, stack trace) if it came from another phase's own
discovery (`docs/pilot-link-bug-tickets.md`) rather than through `/pilot-story` directly.
Turn it into one well-formed `type:bug` issue ready to build: a bug is dev-sized by
definition, so it skips phase 2's scoping pass entirely and goes straight to
`status:spec-ready` (`docs/pilot-process.md` §2 "Three levels") — no priority or splitting
decision to defer.

1. Confirm it's actually a defect against already-agreed behavior (regression, broken
   promise, error) — not a feature request or ambiguous product question in disguise.
   If it's the latter, say so and suggest `/pilot-story` without `--bug`, or with
   `--tech`, whichever fits. If instead you're confident it isn't a real, actionable
   defect at all (already fixed, not reproducible, an exact duplicate of an open bug
   ticket, or working as intended), say so and create nothing — a bug never reaches
   phase 2, so there's no later `status:wont-do` checkpoint to catch this
   (`docs/pilot-process.md` §2 "Three levels"); the same "out of scope, create nothing"
   outcome `/pilot-story` already handles for any raw need (`docs/pilot-process.md` §4
   "Interaction modes").
2. Pin down the failure as concretely as you can from what's given (exact broken
   behavior, error/assertion, likely file(s)/module(s)) — enough that phase 3 can spec
   a fix without re-diagnosing from scratch. State your confidence; if you can't
   reproduce or localize it, say so plainly rather than guessing at a root cause.
3. Write the issue body: what's broken, how to reproduce/observe it, your best
   root-cause diagnosis and suggested fix location, and severity/impact — the full
   content a spec-ready ticket needs, since no phase-2 pass follows.
4. Label it `type:bug`, `level:task`, `status:spec-ready`, unassigned, with `priority:`
   set yourself (`docs/pilot-process.md` §3 — every ticket gets its initial priority at
   phase 1; a bug's is never revisited since it has no phase 2). Never grouped under a
   `level:epic` — that's for `level:story` tickets only, and a bug is never one.
