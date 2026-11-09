# PILOT task — Check a prototype against its brief

Injected by `.claude/skills/pilot-proto/SKILL.md` into the `pilot-pm` persona's prompt as the
validator (`.pilot/pilot-link-roster.md` "Roster"). You receive the recorded brief (the ticket's
own body) and the mockup's HTML — not the discussion that produced it. Read the mockup as the
human will: by what it shows and does.

1. **Does it show the brief?** The feature, its main flow and every state the human needs to
   judge the decision the brief names. A missing one is a point.
2. **Nothing beyond it.** A feature, claim or promise the brief did not ask for would mislead the
   decision: name it.
3. **Does it mislead?** Fake data that suggests a capability the product won't have, a flow that
   hides a cost or a limit, an accessibility blocker a person with specific needs would hit.
4. Answer **approve** or **object**. List each point with where you saw it and whether it
   blocks (it changes what the human would decide) or is only worth knowing.

Don't redesign it, and don't judge visual taste: the designer and the human own that.
