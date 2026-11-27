---
name: pilot-report
description: "Runs the report workflow: a person who saw an abnormal behavior outside a recette describes it, an agent helps fill the form without guessing, and the report is qualified (gap, uncovered behavior, technical defect, conform, duplicate) and sent to the right workflow with its input prepared. Never creates a correction ticket: only a Recette does."
argument-hint: "[\"<what happened>\"] | --resume <run issue>"
---

# PILOT — report

Read `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md`, then run workflow `report`. Anyone may start it; human F (or human T for a technical defect) decides at the gate, unless the qualification is a gap whose checks and judge are green.

**Specific.** The report's run issue is the report itself. The final step does not act: it states the workflow to launch and what to give it — a gap goes to `/pilot-accept` with the cited criteria and the version seen; an uncovered behavior to `/pilot-need --from-report N`; a technical defect to `/pilot-plan "<defect>"`. A conform report or a duplicate is answered with its citation, then closed (`pilot.py run end <run> --result conform|duplicate`).
