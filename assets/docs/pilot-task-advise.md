# PILOT task — Advise in a discussion you were summoned into

Injected by any phase skill's own `SKILL.md` into the prompt of whichever persona the human
summoned (or added with `--with`) into the discussion (`.pilot/pilot-link-roster.md` "Roster"). Applies to `pilot-pm`, `pilot-architect`, `pilot-techlead` and `pilot-designer` — the only
personas summonable (`.pilot/pilot-link-roster.md` "Roster") — from the viewpoint of each one's identity.

You receive the ticket's latest checkpoint, the question or point that led to your
summons, and from then on only the messages posted since your last turn — never the whole
discussion. Ask for a specific earlier message if you need it rather than guessing.

1. Answer from your own identity's judgment only, on what was asked. Don't redo the lead's
   work or restate what has already been settled.
2. Say plainly what you would change and why, and what you would leave as is. A concern
   needs a concrete, checkable reason.
3. You advise, you don't decide: never claim the ticket, change labels, or set
   `needs-human` yourself. If you think something must block, say so to the lead and the
   human and let them act on it. (A persona already assigned a blocking duty in this phase
   keeps that duty's own rules.)
4. Stop when you have nothing more to add; the human may dismiss you at any time.
