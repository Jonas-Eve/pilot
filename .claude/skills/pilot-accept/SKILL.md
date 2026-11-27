---
name: pilot-accept
description: "Runs the accept workflow (the Recette): verifies on the deployed main, by a human or an AI, that a merged story, a technical ticket or a user flow behaves as described, optionally as a persona; leaves a record from which recetted or in-gap marks derive, and creates correction tickets for what failed."
argument-hint: "<story or ticket issue | user-flow id> [--executant human|ai] [--persona <id>] [--version <deployed version>] | --resume <issue>"
---

# PILOT — accept

Read `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md`, then run workflow `accept`. Human F (feature, user flow) or human T (tech) validates the record when the executant is the AI; with a human executant their verdict is the validation.

**Target and choices.** The story or ticket is `merged`; a user flow is `implemented`. `--version` names the deployed version to test (default: the project's `version` command). `--persona` orients the cases. `--executant` defaults to the project's (`pilot.py config get executant`) and is stored in the run data (`pilot.py run note <run> --data '{"executant":"ai"}'`); a criterion verified by `human` or `judgment` forces the human. The persona only orients how the cases are played, never the expected result.

**Specific.** The deployed version comes from the project's `version` command; it must contain the merge. The record is the run's closing comment (`pilot.py run end <run> --result ok|ko --record FILE`). For each case in failure the end creates a correction ticket (`pilot.py ticket create … --label fix`, `--status ready`, citing the failed criteria) and marks the tickets that depend on it `gap`; a story that passes goes `done` (`pilot.py set <issue> --status done`), then `pilot.py derive <parent>`.
