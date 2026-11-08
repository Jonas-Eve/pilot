# PILOT task — Write or revise the wiki entries of a story

Injected by `.claude/skills/pilot-discovery/SKILL.md` (target status `proposed`) and
`.claude/skills/pilot-spec/SKILL.md` (target status `specified`) into the `pilot-pm` persona's
prompt, together with `.pilot/pilot-link-wiki.md`, when the project's `wiki` module is enabled.

Write every title, description and body in the language the prompt names (English when it names none), whatever language the story is in.

You receive the story as finalized (title, body, acceptance criteria; for Spec also its tasks),
the entries that already exist in the domains it touches (id, title, path, status, text), the
target status, and the project's functional domains (the folders of `wiki/`).

1. **One entry per behavior or rule a user can observe**, written in the present tense as what
   the product does: no implementation, no ticket vocabulary. The acceptance criteria are the
   source; never add behavior they do not state.
2. **Reuse before adding.** A story that changes or extends a behavior an entry already states
   revises that entry (same id, new text); a new entry is for new behavior only; never write
   the same behavior twice. A story that removes behavior deprecates the entry that states it.
3. **Place each entry in a functional domain**: an existing folder that fits, else a new
   lowercase folder named for the product area. One entry is one file `<domain>/<id>.md`, the id in lowercase
   letters, digits and dashes.
4. **Conflicts are not yours to settle.** If the story contradicts an existing entry without
   saying it replaces it, return it under `conflicts` with the question to put to a human, and
   write nothing for that entry.

Return one JSON object, nothing else:

```json
{"entries": [{"action": "add|update|deprecate", "id": "", "title": "", "path": "<domain>/<id>.md", "description": "", "body": ""}],
 "conflicts": [{"id": "", "question": ""}]}
```

`description` is one sentence (it is the entry's line in the index), `body` the prose only (both empty for
`deprecate`); the skill writes the ticket numbers and
the status.
