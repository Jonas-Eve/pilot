# PILOT task — Draft a technical guideline

Injected by `.claude/skills/pilot-architecture/SKILL.md` (`--guideline`) into the `pilot-architect` persona's prompt,
together with `.pilot/pilot-link-architecture.md`.

Write the guideline in the language the prompt names (English when it names none).

You receive a rule a human wants the project to follow, the guidelines and ADRs that bear on it and the relevant code.
Write the guideline: **one rule**, in the imperative, in one short paragraph, such that a reviewer reading a diff can say
"respected" or "violated". Add at most one concrete example taken from this project's code, and, when a tool can enforce
the rule (a lint rule, an architecture test, a compiler option), name it. A vague rule ("write clean code") is not a
guideline: put the missing precision in `questions`, or split a request that holds several rules into one entry each.

Carry no reasoning: if an accepted ADR gave the reason, name it in `adr` (its id); if the reason is a choice that
outlives a ticket and nobody recorded it, say so in `questions` so the human can run `--adr`. Never invent a reason.
If the rule contradicts an accepted guideline or ADR, name it in `conflicts`. If it only restates one, say so in
`questions` and propose no entry.

Return one JSON object, nothing else:

```json
{"title": "", "description": "", "slug": "<lowercase-dash-separated>", "body": "",
 "adr": "", "conflicts": [""], "questions": [""]}
```
