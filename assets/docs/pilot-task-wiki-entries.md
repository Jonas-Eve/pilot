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

5. **Never write the `Vision` entry**, nor anything in `persona/` (not a functional domain). A story that contradicts one of them or needs it changed is a
   `conflicts` item for the human, not an `update`.
6. **A user flow, only when the story creates or changes a journey** that chains at least two behaviors or screens (a single rule is a behavior, not a flow). Read `user-flow/` and `persona/` yourself first. An existing
   flow that covers the journey is an `update` of that id, never a second one; otherwise an `add` at `user-flow/<id>.md`. Its body has a `Personas: <id>, <id>` line (only ids that exist: none fits → a `conflicts` item
   naming the persona to create with `/pilot-flow --new persona`, never an invented id), a `Start:` line when it does not begin at the home page, the goal, then numbered steps, each `do → expect`, the expectation taken from
   an entry of this story or an existing one. At target `proposed` the steps stay high level (one line each, what the user does and sees); at `specified` each is one action and one outcome a browser can check. At most 800 words.

Return one JSON object, nothing else:

```json
{"entries": [{"action": "add|update|deprecate", "id": "", "title": "", "path": "<domain>/<id>.md", "description": "", "body": ""}],
 "conflicts": [{"id": "", "question": ""}]}
```

`description` is one sentence (it is the entry's line in the index), `body` the prose only (both empty for
`deprecate`); the skill writes the ticket numbers and
the status.
