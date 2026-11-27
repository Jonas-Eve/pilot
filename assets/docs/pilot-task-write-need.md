# PILOT task — Write a need entry

Injected by the `write` step of the need workflow into the `pilot-pm` persona's `Agent` call (the lead, after the audit).

You receive the need, the audit's delta, the proposed scope, the accepted prototype if there is one, and, on later turns, the human's answers or the gate's
returns. Write or modify one entry in the `need-entry` format.

Do:
- Write the Need as short sentences S1, S2… in the user's words: who, what, why. One idea per sentence; no solution, no screen, no technology.
- Write the criteria C1, C2…: `when` is an action the user takes, `then` is what the user sees or obtains, `by` is who verifies it (`e2e`, `test`, `human`,
  `judgment`), `source` is the sentence it comes from. Every sentence has at least one criterion; every criterion cites its sentence.
- Make each `then` observable and decidable: a number, a visible text, a state. No word from the format's `ambiguous` list.
- Set `flow` on a criterion only when it is a step of a user flow you were given.
- Set `pilot.scope` with terms of the vocabulary only, from the proposed scope; change it only to correct it, and say why in an `ASSUMPTION:`.
- Start from the delta: the entry or criterion it says is contradicted, overlapped or duplicated is dealt with explicitly (extend, replace, or leave
  alone), never silently.
- With a prototype: criteria describe what the human accepted in it; anything the prototype does not show is not a criterion.
- On a modified entry, add one Journal line J<n> (today's date, origin, the decision, the alternatives discarded, the reason). Never edit or delete an
  existing line, nor a criterion's id; a criterion that no longer holds is replaced by a new id and the Journal says so.
- A criterion that came from a candidate request of a user flow keeps that flow in `flow`.
- A criterion you cannot make verifiable without a choice of the human's goes to `QUESTION:`; a choice of wording, grain or order goes to `ASSUMPTION:`.
- On a later turn, apply the human's answer or the gate's return to the same entry and change nothing else.

Never:
- Write a technical decision, a ticket, a split into stories or an estimate: that is not this duty.
- Invent a fact about the existing product: cite the entry id you rely on, or say you did not check.
- Reopen what the human already answered.
- Leave a criterion without `by`, or put `by: judgment` on one a test or the human could check.
