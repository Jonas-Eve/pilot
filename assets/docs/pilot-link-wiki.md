# PILOT link — the project's wiki

Read by `pilot-wiki` and by the persona calls it makes (`pilot-task-wiki-lint.md`,
`pilot-task-wiki-init.md`), and by `pilot-discovery`, `pilot-spec` and `pilot-dev`
(`pilot-task-wiki-entries.md`), `pilot-review` and `pilot-qa` when the project has a `wiki/`; a project without one skips all of it, silently. The wiki is the project's source of truth for what the product
does and what is promised: **when the wiki and the code disagree, the wiki is right** and the
divergence is arbitrated by a human, never settled silently.

**Where and what.** Markdown files under `wiki/` at the project root (project-owned, never
touched by `/pilot-update`). It is functional only (architecture decisions live elsewhere), organized by functional domain: one folder per product area (`wiki/search/`), one page per topic. It says *what* — behavior, rules, vocabulary — never
*how*; technical specs stay in tickets.

**Entries.** One entry is a `##` heading with a stable id, then a machine-readable line:

```markdown
## Filter by accessibility {#search-filter}
<!-- wiki: status=specified tickets=#12,#15 verifiedAt= verifiedCommit= -->

Prose: what the product does, in the present tense.
```

`tickets` lists the tickets that own the entry (put the `type:feature` story in it too).
Create entries with `python3 .pilot/pilot.py wiki add` and change that line only with
`wiki set`, never by hand; ids never change once merged.

**Statuses a file holds:** `proposed` (validated in Discovery), `specified` (validated in
Spec), `implemented` (merged in code), `deprecated`. `in-dev`, `in-review`, `in-qa` and
`verified` are derived (`wiki status`/`wiki show`), never written: the first three from the tickets' labels, `verified` for an `implemented` entry that carries a lint stamp and whose feature story is done.
`verifiedAt` + `verifiedCommit` are written only by a lint that found the entry conforming
(`wiki set --stamp <commit>`), or by an init that found tickets and code in agreement.

**Only a PR changes the wiki.** Wiki changes go on a branch and reach `main` through a PR a
human merges; nothing is committed to `main` directly.

**A divergence between an entry and the code** is resolved by a human, one of:
- the code is wrong: a `type:bug` ticket (`/pilot-spec --bug "<description>"`), wiki untouched;
- the wiki must change: a behavior change goes back through `/pilot-discovery`; a pure
  correction is edited in the same PR once the human confirms;
- behavior present in the code and absent from the wiki: an entry is added, or the code's
  behavior is questioned.

An entry never stamped (`verifiedAt` empty) has not been checked against anything: a divergence
on it is first read as "the entry is probably wrong", the human still decides.
