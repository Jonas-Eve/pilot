# PILOT v3 — modules (design proposal)

Status: **proposal; only the `wiki` module and the switch it introduced exist so far**.
Human-only document: no skill or agent reads it, and it is not copied into consuming projects. Once
validated, each module's contract moves into `assets/docs/` and this file is removed.

## 1. Goal

A small **core** that is always on, and **modules** a project switches on one by one, initializing each
when it needs it.

## 2. Principles

1. **Core is the ticket process.** The five phases, `pilot-auto`, `pilot-help`, `pilot-init`,
   `pilot-update`. Nothing else is assumed.
2. **A module is on or off, in one place.** `.pilot/state.json` → `"modules": {"wiki": true, …}`; absent
   means off. Phases, skills and the dashboard read that one field; none guesses from a folder.
3. **A module that is off changes nothing.** Every step that names it is skipped; its skills refuse to run
   except to turn it on.
4. **Initialization is per module and on demand.** At `/pilot-init` (asked, or `--modules …`), or later,
   the first time the module is used.
5. **Modules declare what they need.** A module may require another (design and proto write into the
   dashboard's database); enabling it checks, and offers to enable the prerequisite.
6. **The switch rule is written once** (`pilot-process.md` §8, now the list of modules); skills point to
   it instead of restating it.

## 3. The modules

| Module | Skills | Requires | `doctor` checks | Content / data | Initialization |
|---|---|---|---|---|---|
| `wiki` | `/pilot-wiki` | — | `wiki/` | functional wiki, one folder per domain (`wiki-design.md`) | `/pilot-wiki --init` |
| `architecture` | `/pilot-architecture` | — | `architecture/` | overview, technical guidelines, ADR (§6) | `/pilot-architecture --init` |
| `dashboard` | `/pilot-dashboard` | — | `dashboardUrl` set | the team page and its database | `/pilot-dashboard` |
| `design` | `/pilot-design` | `dashboard` | — | design system and charter (dashboard database) | `/pilot-design` |
| `proto` | `/pilot-proto` | `dashboard` | — | prototypes (dashboard database) | `/pilot-proto` |

`pilot-init-archi` disappears: its job is the `architecture` module's.

## 4. State, commands and existing projects

- `pilot.py module list` prints each module with `enabled`, `requires`, its skills and its init command
  (one registry in the script, extended by adding a module). `module enable <name>` refuses when a
  prerequisite is off (`--with-requires` enables it too); `module disable <name>` refuses while an
  enabled module requires it. Both write only the `modules` field.
- `pilot.py doctor` runs the check of each **enabled** module only.
- **Existing projects** (`/pilot-update` on a project from before modules): `dashboardUrl` present → `dashboard`, `design` and `proto` on
  (they only worked with it); `archInitialized: true` → `architecture` stays off, with an offer to
  run `/pilot-architecture --init`, which reads the existing `apps/`; `wiki` off. Nothing is switched on
  without the human's answer except that continuity case, which only mirrors what already works.

## 5. Module skills when the module is off

Running a module's skill while it is off says so and proposes: enable it (and its prerequisites), run
its initialization, then continue with what was asked. `--init` is the explicit form. Everything else
that names the module — a phase step, a dashboard tab, `pilot-help`'s list — is skipped or hidden.
`/pilot-init` asks which modules to enable (or takes `--modules wiki,architecture`, `--no-modules`);
`/pilot-update` lists them and offers, never enables; `/pilot-help` shows each one's state.

**Dashboard.** Its tabs follow the modules (Design, Prototypes, Wiki, and an Architecture tab once that
module exists). The ticket snapshot document carries the enabled modules; a snapshot without the field
shows today's tabs.

## 6. The `architecture` module

What `/pilot-init-archi` did once, as living content under `architecture/` at the project root, owned
by the project and changed only by pull requests:

- `overview.md` — the apps or services, each one's purpose and stack, how they relate, the per-app
  commands. Replaces the `PILOT:ARCHITECTURE` and `PILOT:COMMANDS` blocks of `CLAUDE.md`/`README.md`,
  which become a pointer. The `apps` array stays in `state.json` for the personas that read it.
- `guidelines/*.md` — the technical rules AIs and developers must respect (layering, testing, security,
  naming, dependencies). The dev and tech lead receive them in their prompts instead of a copy in
  `CLAUDE.md`; the tech lead's review checks conformance, the way it checks the wiki.
- `adr/NNNN-title.md` — architecture decision records: context, decision, alternatives rejected,
  consequences, status (`proposed`, `accepted`, `deprecated`, `superseded`), and the ADR it supersedes.
  An ADR is never edited once accepted: a later one supersedes it.
- Scaffolding the apps (`apps/<name>/`, pinned latest compatible versions) stays, as `--scaffold`.

**Where an ADR sits.** The wiki says *what* the product does; the guidelines say *how* we build; an ADR
says *why* a choice was made. A decision belongs in an ADR when it outlives a ticket and someone could
be tempted to reverse it ("the catalog is stored, not computed", "the CLI never reads the network").
When it was forced by a product rule, the ADR cites the wiki entry; a wiki entry never carries the
reasoning.

**Who writes and reads.** The architect proposes an ADR in Discovery or Spec when a decision meets that
bar, a human validates, and it reaches `main` in a PR (the spec's PR for a decision a story forced).
Review: a PR that breaks a guideline is a `change`; one that needs to break it is a `decision`.

The module's mechanics (parsing, `index`, `add`, `lint`) reuse the wiki's engine rather than a second
one; its own design is detailed when this module starts.

## 7. Delivery

Each step is backward compatible; the last one is the break.

1. **Done.** The switch (`modules`, `pilot.py module`, `doctor`), the `wiki` module, review/QA criteria,
   the dashboard Wiki tab.
2. The registry with `requires`, `module list` as above, the dependency checks.
3. `dashboard`, `design`, `proto` under the switch: their skills' first-use flow, the dashboard tabs
   following the modules, `/pilot-init --modules`, the `/pilot-update` migration, `/pilot-help` status.
4. The `architecture` module, built beside the old skill: layout, ADR, guidelines in the dev and review
   prompts, `--init` from an existing `apps/`, `--scaffold`, the dashboard tab.
5. **v3**: `pilot-init-archi` removed, `archInitialized` and the `PILOT:ARCHITECTURE`/`PILOT:COMMANDS`
   blocks replaced by the module's pointer, `/pilot-update` migrating each project (§4).

## 8. Open points

- The ADR mechanics: one file per ADR with the wiki's meta-line convention, or its own front matter.
- Whether `guidelines/` entries carry stamps like wiki entries (verified against the code by a lint) or
  stay plain prose.
- Whether a module may be disabled once it holds content (kept on disk, ignored), and what `doctor`
  says about a disabled module's leftover folder.
