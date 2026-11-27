---
name: pilot-proto
description: "Builds a clickable prototype of a feature with a human, to decide whether to build it, before any need: runs the `proto` workflow (the designer builds the mockup shown in the dashboard's Prototypes tab, validator, checks, judge, an acceptance gate). If the design system lacks something the prototype needs, the run waits in pause. Its decision, accepted or rejected, is the closing comment of its run. Works no ticket. --resume continues a paused run."
argument-hint: "<feature idea in free text> | --from-artifact <artifact url> [note] | --resume <run issue number> | <run issue number> --reject [reason]"
disable-model-invocation: true
---

# PILOT proto — `pilot-proto`

Read `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md` first: the runner file says how any workflow runs. This skill runs the **`proto`** workflow and adds only what is specific to it.

- **Module.** `python3 .pilot/pilot.py module list`: with `proto` off, say so and propose `python3 .pilot/pilot.py module enable proto --with-requires`; on a yes go on, on a no stop.
- **Idea.** The `idee` step takes the idea from the argument, else asks for it. A technical need or a bug is not a prototype: point at `/pilot-need`. `--from-artifact <url> [note]` imports a Claude artifact as the mockup: `Artifact read` the url without its `?…` query; only the human's own single-page artifact comes back as HTML, anything else (several files, a type) → say so and stop. Keep the page in a temporary file; the note is the idea.
- **Run.** `python3 .pilot/pilot.py run start proto`; `--resume <run issue>` is `run resume <issue>`. The build step returns the mockup as one self-contained HTML file: write it to a temporary file and pack it for the cockpit with `python3 .pilot/pilot.py proto-pack <run issue> --html FILE --out DIR` at every revision. A refusal's `problems` go back to the designer (to the human for an imported artifact). Push the documents it writes as `.pilot/pilot-link-dashboard.md` says, and give the human the dashboard's Prototypes tab to open.
- **Wait.** At `attente-du-design-system` the run stops when the design system lacks something the gate decided to integrate: say what is missing and that `/pilot-design` produces it, then `/pilot-proto --resume <run issue>` once it is merged.
- **Decision.** The gate's outcome ends the run: `python3 .pilot/pilot.py run end <run issue> --result accepted` or `--result rejected` (a rejection takes a reason, asked in one question when absent; it is the run's closing comment). `<run issue> --reject [reason]` is that same close, for a prototype left at its gate. The `need` workflow reads the decision.
- **Report.** The run issue, its state, where to see the prototype, what is unverified.
