# What PILOT still tolerates, and when it stops

Human-facing; no skill or agent reads it. A change that renames or removes something keeps the old form working for one release
so a project is never broken by `/pilot-update`; each tolerance is listed here with the version that removes it, so it does not
become permanent. A tolerance is removed by the PR that bumps the major version named here, which also deletes its line.

| Tolerance | Since | Removed in | What to do before |
|---|---|---|---|
| `--deprecate <id>` accepted as an alias of `--remove` in `/pilot-wiki`, `/pilot-architecture` and `/pilot-flow` | 4.2.0 | 5.0.0 | Use `--remove` in your own scripts and notes |
| An entry whose `pilot.status` is `deprecated` is still read (wiki and architecture); `lint` warns `legacy-status` | 4.2.0 | 5.0.0 | Delete such entries: `/pilot-wiki --remove <id>`, `/pilot-architecture --remove <id>` (the cockpit offers `Retirer` on each) |
| A Vision or a Persona written with `status: implemented` (before they carried none) is still read | 4.2.0 | 5.0.0 | Nothing: edit the entry once and the status is dropped |

`/pilot-update` reports what is still tolerated in the project (step 7), so the list is visible where the project can act on it.
