# PILOT task — Rewrite an architecture entry

Injected by `.claude/skills/pilot-architecture/SKILL.md` (`--edit`) into the `pilot-architect` persona's prompt,
together with `.pilot/pilot-link-architecture.md`.

Write in the language the entry is written in.

You receive one entry (its kind, title, description, text and stamp), the change a human asks for, the entries that
bear on it and the relevant code. Return the entry as it should read after the change, nothing more changed than the
request says:

- a **guideline** stays one rule, in the imperative, checkable by a reviewer reading a diff, with no reasoning of its
  own (an `adr` line at most); a request that adds a second rule, or a reason, is split out in `questions`;
- a **reference** entry stays a statement of fact (names, versions, tables, paths), read from the code where the
  request touches a fact, never a rule and never a reason;
- the **overview** and a **runbook** keep their shape (apps and how they relate; steps in order, none dropped).

State only what the human and the code give you; where something is missing, put it in `questions` instead of
inventing it. If the change contradicts an accepted guideline or ADR, name it in `conflicts`.

Return one JSON object, nothing else:

```json
{"title": "", "description": "", "body": "", "conflicts": [""], "questions": [""]}
```
