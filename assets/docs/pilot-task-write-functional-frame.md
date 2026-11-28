# PILOT task — Write a functional frame

Injected by the `write` step of the functional-frame workflow into the `pilot-pm` persona's `Agent` call.

You receive the human's functional intention, the audit's delta and the proposed scope. Write one entry in the `frame` format: a product principle, the vision, or
vocabulary terms. The functional frame is what the product does in shared terms, never how it is built.

Creating or changing:
- A new entry is a file created at `<domain>/<id>.md` (`wiki add`): a domain folder that `wiki index --depth 1` lists or the proposed scope names, an id in lowercase words that no entry
  has, status `specified`. Vocabulary terms go into the existing `vocabulary.md` entry, never into a second one.
- A change (`--edit <id>`) is that same file, same id; edit only what the intention changes.

Do:
- Source: put the human's intention in sentences S1, S2…, as they said it, one idea each.
- Statements E1, E2…: what the product always or never does, from the user's side. Each cites its source sentence and has `by: judgment` unless a
  rule over the product's text or behavior can check it, then `rule`.
- Examples X<n> only when they remove an ambiguity: a `pass` and a `fail` case of a statement, concrete.
- Vision: who it is for, what changes for them, what the product refuses to be. Principles: the lasting choices a feature must respect. Vocabulary: one meaning per
  term, written for the user, never a synonym of an existing term.
- Scope: terms of the vocabulary, taken from the proposed scope. A new term goes into the vocabulary entry, with its meaning.
- Say what the entry replaces or narrows, by entry id, in the Source section, as a sentence.
- A contradiction between the intention and an existing frame, or an overlap with one, is signalled: name the entry and the statement, quote both, and
  write the entry as the human intended. Never block on it, never soften the statement to avoid it. Put it in an `ASSUMPTION:` with the default you took.

Never:
- Write a criterion, a feature, a ticket, a screen or a technology.
- Write a statement no one could ever see violated ("be user-friendly"); no word from the format's `ambiguous` list.
- Edit another entry: you write one, and signal the rest.
- Ask a question about wording or order; take a default. When two readings of the intention lead to opposite statements, take one and record the other in an `ASSUMPTION:` (the gate shows it).
