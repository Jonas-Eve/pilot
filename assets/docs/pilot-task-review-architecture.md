# PILOT task — Review architecture/security conformance

Injected by `.claude/skills/pilot-review/SKILL.md` into the `pilot-architect` persona's
prompt.

Review the shipped PR against the security/architecture decisions you recorded at
scope time. Return a structured verdict: approve, or block with one or more specific
points, each tagged either `change` — a concrete code-level fix you can articulate —
or `decision` — a genuine judgment call with no fix to propose until a human weighs
in. Default to `change` whenever you can say what should be different; reserve
`decision` for when the right answer depends on information or a preference only a
human has (`docs/pilot-link-review-consensus.md` — this tag is what routes the ticket to
`/pilot-dev` versus back to a human). You review independently — you don't see the
other reviewers' verdicts first, and you don't submit the aggregated GitHub review
yourself.
