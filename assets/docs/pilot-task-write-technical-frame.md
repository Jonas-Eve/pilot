# PILOT task — Write a technical guideline

Injected by the `write` step of the technical-frame workflow into the `pilot-architect` persona's `Agent` call.

You receive the human's technical intention, the audit's delta and the proposed technical scope. Write one guideline in the `frame` format. It is not an ADR: it
states how the code is always built, not a choice between options.

Creating or changing:
- A new guideline is a file created at `guidelines/<id>.md` (`arch add`, one rule per file; `apps/<app>/guidelines/<id>.md` in a monorepo for a rule of one app), an id in lowercase words
  that no entry has, status `accepted`: the run's gates are its acceptance and it takes force at the merge of the PR.
- A change (`--edit <id>`) is that same file, same id; edit only what the intention changes. An accepted ADR is never edited.

Do:
- Source: S1, S2… the intention in sentences, one idea each, with its reason in the human's words.
- Statements E1, E2…: one rule per statement, imperative, with the thing it applies to. Each cites its source and has `by`. A statement that a linter, a test,
  a build step or a script can check is `rule`; only what needs reading is `judgment`. Try `rule` first and say in the statement how it is checked (the command, the
  pattern, the tool).
- Examples X<n>: for every `rule` statement, at least one `pass` and one `fail` case, concrete (a snippet, a path, a command output). The `fail` case is a
  violation the rule must detect; the `pass` case is a near miss it must accept. For a `judgment` statement, one pair when it removes an ambiguity.
- Scope: terms of the technical scopes only, from the proposed scope.
- Say what the guideline replaces or narrows, by guideline or ADR id, in the Source section as a sentence. A rule that conflicts with an accepted ADR or guideline is
  named, with both texts quoted, in an `ASSUMPTION:` with the default you took.
- Ground each statement in the code as it is: cite a path that already follows it, or one that breaks it. Say what you did not check.

Never:
- Write an ADR, a ticket, a migration plan or an implementation.
- Write a statement without its source sentence, or with `by: rule` when you cannot say how a program would check it.
- Write an example that does not match its statement.
- Rewrite an existing guideline to fit: write yours and signal the divergence.
- Add a dependency or a tool the project does not have without a `QUESTION:` giving options, cost and your recommendation.
