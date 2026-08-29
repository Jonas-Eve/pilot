# CLAUDE CODE GUIDE & DIRECTIVES — `pilot` PLUGIN REPO

## 1. WHAT THIS REPO IS
This repo **is** a Claude Code plugin (`.claude-plugin/plugin.json` +
`.claude-plugin/marketplace.json` at the root) that packages PILOT — a 5-phase
ticket-process framework — for reuse across projects. It is not itself an application;
there is no "functional scope" here beyond the plugin's own behavior.

The canonical, always-up-to-date spec for the process this plugin implements lives at
`assets/docs/pilot-process.md`. Read it before changing any skill, agent, or label —
those files must never drift from what it describes. It is genericized on purpose (no
references to any one consuming project); when porting a change from a project that
forked PILOT, strip project-specific details the same way.

## 2. STRUCTURE
- `skills/<name>/SKILL.md` — one per slash command, auto-discovered by Claude Code.
  `init`, `init-archi`, `update` are this plugin's own bootstrap/maintenance commands
  (no `pilot-` prefix — the plugin namespace already provides it, so `/pilot:init` etc.
  would otherwise stutter); `story`, `scope`, `spec`, `dev`, `review` are the five PILOT
  phases, same reasoning.
- `agents/<name>.md` — the four personas (`pilot-pm`, `pilot-architect`,
  `pilot-techlead`, `pilot-dev`) the phase skills delegate to via the `Agent` tool.
- `assets/docs/pilot-process.md` — canonical process spec, copied verbatim into a
  consuming project as `docs/pilot-process.md` by `/pilot:init` and re-synced by
  `/pilot:update`.
- `assets/templates/*.tmpl` — doc skeletons `/pilot:init` renders with `{{PLACEHOLDER}}`
  substitution.
- `scripts/setup-github-labels.sh` — idempotent GitHub label provisioning, run by both
  `/pilot:init` and `/pilot:update`.

Within a skill or agent file, reference this plugin's own assets via
`${CLAUDE_PLUGIN_ROOT}` (e.g. `${CLAUDE_PLUGIN_ROOT}/scripts/setup-github-labels.sh`),
never a hardcoded path — the plugin installs at a different absolute path per consumer.

## 3. CHANGE DISCIPLINE
- **Mechanism vs. wording:** the phase names, label taxonomy, claim protocol, and
  skill-to-agent mapping in `assets/docs/pilot-process.md` are the actual product. Don't
  change them casually; a mechanism change here affects every project that has installed
  this plugin, not just one.
- **Cross-reference check:** `assets/docs/pilot-process.md`, every `skills/*/SKILL.md`,
  every `agents/pilot-*.md`, and the PILOT mentions in this file and `README.md` are
  tightly cross-referenced. After editing any of them, `grep` the exact term(s) you
  changed (a renamed label, a moved section heading) across that whole family and fix
  what turns up, rather than re-reading every file end to end.
- **Version bump:** bump `version` in both `.claude-plugin/plugin.json` and the matching
  entry in `.claude-plugin/marketplace.json` whenever a change to a shipped file
  (skill, agent, script, template, or the process doc) would be visible to a consuming
  project — that's what lets `/pilot:update` and the plugin update flow report something
  meaningful changed.

## 4. GIT WORKFLOW
- **Commit Freely On A Work Branch, Never On `main`:** on a short-lived work branch,
  committing and pushing completed work is authorized by default. On `main`, never
  commit or push without the user explicitly asking in the current task.
- **Amend, Don't Stack, Within The Same Not-Yet-Merged Context:** if a new commit only
  fixes or completes the change the immediately preceding, not-yet-merged commit made,
  amend that commit instead of stacking a separate one. Once merged into `main`, or once
  another branch depends on it, it's shared history — never amend or force-push it.
- **Trunk-Based Development:** `main` is the single trunk; short-lived branches merge
  back quickly, no long-lived feature branches.
- **Conventional Commits:** `type(scope): description` (e.g.
  `feat(skills): add init-archi scaffold for Expo mobile`). `scope` is typically the
  affected top-level dir (`skills`, `agents`, `scripts`, `docs`) or omitted for
  repo-wide changes.
- **Rebase Merge Only:** PRs merge into `main` via rebase merge, keeping history linear.
  Never force-push `main`.
