# PILOT link — reading the project's knowledge

Read by every agent a phase gives a knowledge bundle to, and by `pilot-wiki` and `pilot-architecture`, when the
`wiki` or the `architecture` module is enabled. The bundles are `wiki/` (what the product does) and
`architecture/` (how it is built and why); the commands are the same for both, `python3 .pilot/pilot.py wiki …` or
`python3 .pilot/pilot.py arch …` (`<b>` below). Their format and rules are `.pilot/pilot-link-wiki.md` and
`.pilot/pilot-link-architecture.md`.

**Read through the commands, never through the files.** Do not list the folders, open files, or carry whole
entries into a prompt: a bundle can be large and its size must not reach your context. Go from the general to the
particular and stop as soon as you have what the task needs:

1. **First look:** `<b> index --depth 1` — the sub-folders, each with its one-sentence description and how many
   entries it holds, and the entries sitting directly at that level. Descend with `--under <folder>`.
2. **Narrow:** descend into the folder that fits, or `<b> search "<the task's own words>"` — the best entries
   first, each with one line of extract (`--under` restricts it, `--limit` bounds it).
3. **Open:** `<b> show <id>` only for the few entries that bear on the task. `show` also lists what the entry
   cites (`links`) and what cites it (`backlinks`): follow them instead of searching again.
4. **A listing of what is in force:** `<b> index --active` (history left out) when you need the rows themselves; add
   `--ticket <n>` for the entries a ticket owns.

**What you read.** Where the bundle is silent, say it is not covered; do not fill the gap from the code. A
`proposed` or `specified` entry is a promise, not behavior; a `deprecated` or `superseded` one is history, read only
to follow `supersededBy`. When the bundle and the code disagree, the bundle is right and a human arbitrates.

**Shapes you can rely on.** `index` and `search` rows carry `id`, `path`, `description`, `status` (`search` also
`score` and `snippet`); `index --depth 1` returns `folders` (`path`, `description`, `entries`) and `entries`; `show`
returns the entry's fields, its `text`, `links`, `backlinks` and `external`. Fields may be added, never removed.
