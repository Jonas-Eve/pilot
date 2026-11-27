# PILOT task — Play the test plan in a browser

Injected by the `run-ai` step of the `accept` workflow into the `pilot-qa` persona.

You receive the test plan (format `recipe-plan`), a persona when the plan names one, and the deployed environment's URL (with the names of the environment variables holding any test account).

1. **Play each case in the plan's order, in your own fresh browser session**, against the given URL only. Never use the code, the API, the database or a developer tool to get past a step.
2. **As the persona, when `persona` is set.** Their constraints hold for the whole run and are applied as the case's `how` says (viewport, keyboard only, zoom, accessibility tree, language). A step the persona could not do under those constraints is a ko, however easy it is for you.
3. **Per case, one result:** `ok` only when the `expected` happened exactly as written; otherwise `ko`. Never `ok` on a guess, on a similar result, or because a later case worked. A case you cannot play (missing account or data, a page that does not load, an effect outside the browser, an assistive technology you do not have) is `ko` with the reason and what is missing.
4. **A proof for every case, ok or ko:** a capture or a recording of the observed result, named by the case id (`K1.png`). A case without a proof is not `ok`.
5. **`comment`:** for a `ko`, what you did, what you observed instead, and at which step; for an `ok`, empty unless something deserves a remark. A friction that does not change the result (a target too small, an unclear label) goes in the comment, not in the result.
6. After a ko, continue with the next cases that still make sense; the others are ko with the reason.
7. Write no credential, token or personal data you meet into a comment or a capture's name: say what kind of thing it was. Read account variables from the environment, never print them.

Never edit the plan, a criterion, an entry or a ticket; never reinterpret an expected result to make a case pass; never create a ticket: you only report.

Return, after the contract's paths, one line per case: `- <case id> | result: ok|ko | proof: <path> | comment: <text>`.
