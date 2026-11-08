# PILOT task — Draft an architecture decision record

Injected by `.claude/skills/pilot-architecture/SKILL.md` (`--adr`) into the `pilot-architect` persona's prompt,
together with `.pilot/pilot-link-architecture.md`.

Write the ADR in the language the prompt names (English when it names none).

You receive a decision a human wants recorded, the architecture entries that bear on it and the relevant code.
Write the ADR: **context** (the forces and constraints, the wiki entry that forced it if any), **decision** (one
paragraph, in the present tense), **alternatives rejected** (each with why), **consequences** (what becomes easier,
what becomes harder, what it forbids). State only what the human and the code give you; where a reason is missing,
put it in `questions` instead of inventing it. If it reverses an accepted ADR, name it in `supersedes`. If it
contradicts a guideline, name the guideline in `conflicts`.

Return one JSON object, nothing else:

```json
{"title": "", "description": "", "slug": "<lowercase-dash-separated>", "body": "",
 "supersedes": "", "conflicts": [""], "questions": [""]}
```
