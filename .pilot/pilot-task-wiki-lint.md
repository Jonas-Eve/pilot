# PILOT task — Check wiki entries against the code

Injected by `.claude/skills/pilot-wiki/SKILL.md` (`--lint`) into the `pilot-techlead` persona's
prompt, together with `.pilot/pilot-link-wiki.md`.

You receive wiki entries (id, status, text, tickets) with their stamps, and a git commit to
verify against. Entries are `implemented` (or derived `verified`): each states a behavior the
code must show. Never judge a `proposed` or `specified` entry against the code.

For each entry, read the code that implements the behavior and run it where cheap (a test, a
CLI call) rather than trusting names. Return one verdict per entry:

- `ok` — the behavior holds as the entry states it, in every detail it states.
- `drift` — the code does something else, or less, or more than a rule the entry states. Say
  which statement, and what the code does instead.
- `unverifiable` — you cannot establish it (needs a service you cannot reach, no code found).
  Never `ok` by default.

Each verdict cites its evidence as `path:line` (and the command you ran, if any). An entry
with no `verifiedAt` has never been checked: when it drifts, say whether the entry reads as a
wrong claim or the code as a defect, with the reason; the human decides.

Separately, list behaviors you met in the code that no entry states (`undocumented`, one line
each, advisory only).

Return one JSON object, nothing else:

```json
{"verdicts": [{"id": "", "verdict": "ok|drift|unverifiable", "evidence": "", "note": ""}],
 "undocumented": [{"behavior": "", "evidence": ""}]}
```
