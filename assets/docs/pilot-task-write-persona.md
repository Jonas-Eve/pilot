# PILOT task — Write a persona

Injected by the `write` step of the persona workflow into the `pilot-designer` persona's `Agent` call.

You receive the human's intention, the audit's delta and the proposed scope. Write one persona in the `persona` format.

Do:
- Describe a person, not a segment: goals, skills, constraints, vocabulary, context of use, and the `Usage` lines U1, U2… that say how this person uses the product (device,
  input mode, assistive technology, accessibility needs). One fact per line.
- Never prescribe behavior ("the persona clicks…") or a feature, and never write a trait that cannot be observed when playing the persona. Take facts from the
  intention; mark each guess in an `ASSUMPTION:`. No stereotype beyond what the human said.
- A new persona is a file created at `persona/<id>.md` (`wiki add`, no status); a change (`--edit <id>`) is that same file, same id. Reuse an existing persona when one fits.

Never: write a criterion, a user flow or a ticket; ask about wording or order (take a default and record an `ASSUMPTION:`).
