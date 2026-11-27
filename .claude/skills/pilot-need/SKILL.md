---
name: pilot-need
description: "Runs the need workflow: a request becomes a wiki entry of observable criteria (when / then / verified by), validated by human F at a first gate, then grouped into a story (and an epic if the request is large) at a second gate. Takes a raw request, an accepted prototype, an entry sent back for rework, a user flow's candidate request, or a report qualified as uncovered."
argument-hint: "\"<request>\" [--proto <prototype run issue>] | --rework <run issue> | --from-flow <flow id>#<K> | --from-report <issue> | --resume <run issue>"
---

# PILOT — need

Read `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md`, then run workflow `need`. Human F decides at both gates; no human T.

**Input.** The request as the human wrote it. `--proto N`: the prototype run must have ended `accepted` (`pilot.py run show N`); its parcours are the `parcours` the checks read. `--rework N`: the run N carries the question card and the entry to rework; start from them.
`--from-flow`: the candidate request K of that user flow, set to `launched` by the final docs PR. `--from-report`: the report's qualification and form are the request.

**Specific.** The final step creates the story and the epic with `pilot.py ticket create` (`--status forming`, or `to-plan` for a one-entry story; the body only points to the entries), lists the story in the entry (`pilot.py wiki set <id> --add-ticket N`), and ends by the docs PR. A forming story takes more entries until human F runs `pilot.py ticket close-forming <story>`.
