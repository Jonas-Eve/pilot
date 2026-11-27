---
name: pilot-help
description: "Read-only help over the installed PILOT skills and agents; never claims a ticket or invokes another skill. No argument lists every command; a command name gives its modes, flags and examples; an agent name gives that persona's identity and duties; a flag (--resume, --rework, …) says which commands accept it; free text describing a goal returns the exact command to run, or the persona responsible for a kind of judgment. Everything is re-derived from the current skill and agent files, so it cannot drift. Use to find out what exists, what a command or flag does, or which command fits a goal."
argument-hint: "[<command name, with or without pilot-/leading slash>] | [agent] <persona name, with or without pilot-/leading slash> | [--<flag name, dashes optional>] | <free text describing what you're trying to do> — omit for the full command list"
---

# PILOT — Help

Purely informational: reads PILOT's installed files and explains them. Never invokes the `Skill` or `Agent` tool, never touches a GitHub issue/PR, never claims or advances a ticket. If what is wanted is running something, name the command and stop.

Every answer is derived live from this project's installed files, never from memory:

- `.claude/skills/pilot-*/SKILL.md` (including this one): frontmatter (`description`, `argument-hint`) for the summary and flags, body for detail.
- `.claude/agents/pilot-*.md`: identity, and the trailing task-doc list for the persona's duties.
- `.pilot/pilot-process.md`: the vocabulary and cross-cutting flags shared by every workflow; `.pilot/pilot-link-*.md`: mechanics shared by some (`pilot-link-runner.md`: how a workflow runs).
- `python3 .pilot/pilot.py workflow list` / `workflow show <id>`: a workflow's steps, actors, gates and contract.

If `.claude/skills/pilot-*/` is absent, PILOT is not installed: point at `/pilot-init`.

## Determining the mode

**No argument → list mode.** Read every installed skill's frontmatter and report them in these categories, one line each (name, one-sentence summary in plain words, `/pilot-help <name>` for more); skip any not installed, and mention a `pilot-*` skill outside this list as project-local:

1. Run workflows: `pilot-need`, `pilot-plan`, `pilot-build`, `pilot-accept`, `pilot-report`, `pilot-express`.
2. Frames and design (modules): `pilot-architecture`, `pilot-wiki`, `pilot-design`, `pilot-proto`, `pilot-flow`.
3. Bootstrap and maintenance: `pilot-init`, `pilot-update`, `pilot-dashboard`, `pilot-help`.

Then the optional modules: run `python3 .pilot/pilot.py module list` and give each module's name, whether it is on, its `use` command and its `bootstrap` when it has one. Close with one line naming the seven personas (`pilot-pm`, `pilot-architect`, `pilot-techlead`, `pilot-dev`, `pilot-e2e`, `pilot-qa`, `pilot-designer`) and `/pilot-help agent <name>`; they are not commands.

**A command name → detail mode.** Normalize (strip a leading `/`, add a missing `pilot-`) and match an installed skill directory. No match → say so and suggest bare `/pilot-help`. On a match read its whole `SKILL.md` and answer with:
- what it does and when to use it, and which workflow it runs; for its steps, actors and gates, give `python3 .pilot/pilot.py workflow show <id>` rather than restating them;
- every flag and argument form, one line each; a shared flag (`--resume`) is explained from the doc that owns it;
- resume behavior specific to it, if any;
- two or three example invocations built from its `argument-hint`.

**An agent name → agent mode.** Normalize the same way and match the installed `.claude/agents/pilot-*.md`. `dev` and `qa` also name commands: a bare match means the command; a leading `agent` token (`agent dev`) means the persona, and is accepted on any persona. On a match read the file and answer with:
- its stable identity: the judgment it brings;
- its duties, one line each: for every task doc in its trailing list, the duty and which workflow step injects it (grep `.pilot/workflows/*.json` and the skills, never guess), and whether the persona is lead, validator or reviewer there;
- a pointer to `/pilot-help <command>` for how a duty runs.
The judge is a script-driven step with no persona.

**A flag → flag mode.** Normalize (dashes optional) and search every installed `SKILL.md` for it, plus the `.pilot/pilot-link-*.md` or `pilot-process.md` section that documents it. Answer with the commands that accept it, what it does on each (calling out real differences), and any documented incompatibility with another flag. No match → not a recognized PILOT flag.

**Anything else → recommend mode.** A goal, situation or question in prose. Match the ask:
- "What do I run for X" → read the commands' descriptions and argument-hints and answer with the exact command line (real flags, placeholder issue numbers marked as such) and a short why drawn from that command's documented behavior.
- "Who judges X" → read the agents' files and name the persona(s), pointing at `/pilot-help agent <name>`.
Genuinely ambiguous between materially different commands → ask which; an answer that any single command already covers needs no question.

## Report

Mention the mode only if not obvious from the answer's shape.
