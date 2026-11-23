# PILOT task — Check architecture entries against the code

Injected by `.claude/skills/pilot-architecture/SKILL.md` (`--verify`) into the `pilot-techlead` persona's prompt,
together with `.pilot/pilot-link-architecture.md`.

You receive entries (id, kind, text, stamp) and a git commit to verify against. What `ok` means depends on the kind:

- `reference` and overview state a fact about the code today (a version, a table, a folder, a command, an integration):
  every statement holds as written.
- `guideline` states a rule: the code respects it. Look for violations where the rule applies (grep the pattern it
  forbids, read the layers it separates, run the check it names), over the whole code, not a sample you chose to agree.
- `adr` states a decision: the code implements it (the chosen technology or structure is what is there, the
  rejected alternative is not), as the decision reads. Its reasons are not yours to judge.

For each entry, read the code or the file that proves each statement (a manifest and its lockfile for a version, the
schema or the migrations for a table, the folder itself for a structure) and run the command where cheap, rather than
trusting names. Return one verdict per entry:

- `ok` — every statement holds as written.
- `drift` — a statement is wrong, missing or out of date. Give each wrong statement and the exact fact the code shows,
  so the human can decide without another reading (for a guideline or an ADR, each place that departs from it). Say, with
  the reason, whether the entry reads as stale or wrong or the code as a defect; the human decides.
- `unverifiable` — you cannot establish it (needs a service you cannot reach). Never `ok` by default.

For an `adr` verdict, `corrections` is empty: describe the departure in `evidence`.

Each verdict cites its evidence as `path:line` (and the command you ran). Separately, list facts you met that no
reference entry states and that a developer would need (`undocumented`, one line each, advisory only).

Return one JSON object, nothing else:

```json
{"verdicts": [{"id": "", "verdict": "ok|drift|unverifiable", "evidence": "", "corrections": [""]}],
 "undocumented": [{"fact": "", "evidence": ""}]}
```
