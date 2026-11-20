# Throwaway: do agent frontmatter hooks fire?

1. `rm -f /tmp/hooktrace.log /tmp/hook-agent-touch`
2. Run `echo MAIN` with Bash in the main session (control: a project settings.json hook should log `settings-control`).
3. Spawn the `zz-hooktest` agent (subagent_type "zz-hooktest") and have it run `echo A`.
4. Report `cat /tmp/hooktrace.log` and `ls /tmp/hook-agent-touch`.
Expected: `settings-control` for MAIN and for A (settings hooks also run in subagents); `agent-pre-var`,
`agent-pre-rel`, the touch file, and `agent-stop` if frontmatter hooks fire.
