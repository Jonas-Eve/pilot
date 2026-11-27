# PILOT task — Group a validated entry into a story and an epic

Injected by the `group` step of the need workflow into the `pilot-pm` persona's `Agent` call.

You receive the validated entry, the other ready entries whose scope overlaps its own, and the stories still `forming` (with their epic) whose scope overlaps it.
Return one proposal as a JSON object, the shape `need.check-2` reads:

`{"story": <number of a forming story> | "new", "epic": <number> | "new" | null, "entries": [<entry ids>], "explanation": "<at most three sentences>"}`

Rules:
- `story`: join a listed story only when its entries and this one serve the same user goal and would be built and accepted together. Otherwise `"new"`, the default. Never
  name a story that is not in the list you received.
- `entries`: the new entry plus the listed ready entries that belong in the same story, no duplicate. Include an entry only if it is in your input.
- `epic`: `null` unless the request is large: several stories that share one user goal, or one story that would take many tasks. Then name the epic of the joined story,
  an existing listed one that fits, or `"new"`. When a joined story already has an epic, keep it.
- `explanation`: one to three sentences, in the user's language of the entry, saying why these entries go together (the shared goal) and, if any, why an overlapping
  entry was left out. No list, no process.
- Overlap of scope alone is not a reason to group. Two entries that can be accepted separately go in separate stories.

Never: create or modify an entry or a ticket; merge two stories; propose an epic for a single small story; add commentary around the JSON beyond the contract's lines.
