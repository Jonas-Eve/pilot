# Testing a user flow as a persona — design

Human-facing; no skill or agent reads it. The command is `/pilot-flow` (`.claude/skills/pilot-flow/SKILL.md`).

## Why not a ticket

`/pilot-qa` checks one story's acceptance criteria. A journey (book a trip, change it, get help on the way) crosses stories, and what a person with a constraint lives in it is not in any criterion. The flow is therefore
a wiki entry, not a ticket: nothing is claimed, no status moves, and a run never stamps it.

## The two folders

`wiki/persona/<id>.md` — `type: Persona`, `--status implemented`, no ticket. The prose says who the person is, what they need and the constraints a test must reproduce (device, assistive technology, language, ease with
digital tools), and names the test account by a label. Credentials never live in the wiki: `PILOT_ACCOUNT_<ID>_USER` / `PILOT_ACCOUNT_<ID>_PASSWORD` in the environment (`<ID>` the persona id in capitals, dashes as underscores),
or given by the human at run time.

`wiki/user-flow/<id>.md` — `type: UserFlow`, same status. The prose gives the journey's goal, a `Personas:` line (ids), where it starts, then numbered steps, each `do → expect`.

```
wiki add persona/marie-senior.md --type Persona --status implemented --title "Marie, 74, low vision" --description "Senior, uses the phone at 200 % zoom, wary of forms." --body "…"
wiki add user-flow/book-assisted-trip.md --type UserFlow --status implemented --title "Book an assisted trip" --description "From search to confirmation with assistance requested." --body "…"
```

`persona/` and `user-flow/` are not functional domains: `/pilot-wiki --lint` and `--bootstrap` and the entries a story writes leave them out (`assets/docs/pilot-link-wiki.md`). A flow is up to 800 words, a persona 400.

## Independent sessions

Two tabs of one browser share cookies, so two accounts cannot run side by side in them. Each persona gets its own browser context (Playwright `browser.newContext()`), which is why the runs go in parallel only when that
isolation is available; with a single shared profile they run one after the other.

## Not done yet

Writing personas and flows is by hand today. A drafting mode (`/pilot-flow --draft`, from the wiki's behaviors and the vision, with a human) and flows where two personas interact (a carer and the person they assist) are
the natural next steps.
