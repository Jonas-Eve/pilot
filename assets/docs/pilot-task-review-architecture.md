# PILOT task — Review architecture/security conformance

Injected by `.claude/skills/pilot-review/SKILL.md` into the `pilot-architect` persona's
prompt, alongside `.pilot/pilot-link-review-consensus.md` for the shared verdict format and
`change`/`decision` tagging rule.

Review the shipped PR against the security/architecture decisions recorded on the ticket
at scope time.

**Reconciling an ensemble (`--multi`, `.pilot/pilot-link-multi-consensus.md`)**: sometimes
you're given N other instances' full verdicts for this same PR instead of being asked to
review it yourself — compare them, never draft your own. A `change`/`decision`-tagged
point only some instances raised is coverage, not disagreement — union it in. Only two
instances reaching opposite judgments about the identical point is genuine disagreement —
report exactly which point and quote each differing instance's position, without picking a
winner yourself.
