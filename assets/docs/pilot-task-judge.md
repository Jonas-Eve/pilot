# PILOT task — Judge closed questions
Injected by every `judge` step into an `Agent` call without a persona. The runner calls you twice; the two answers must agree.

You receive numbered yes/no questions and the documents they are about. Nothing else is evidence.

1. Answer every question, in order, with `yes` or `no`. No third answer, no "partly": when the documents do not settle it, the answer is `no`.
2. Each answer carries a quote copied character for character from the documents: the passage that makes the answer true. For a `no` caused by absence, quote the passage that should have held it, else the closest one. A quote you cannot find in the documents invalidates the answer.
3. Say nothing beyond the quote: no explanation, no hedge, no recommendation, no reference to another question.
4. Answer from the documents only, not from what the project probably does.

Return only this JSON, one object per question, `q` being the question's index:

[{"q": 0, "answer": "yes", "quote": "…"}]
