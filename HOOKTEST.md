# Throwaway: do agent frontmatter hooks fire?

In a fresh session on this branch (the agent must exist at session start):
1. `rm -f /tmp/hooktrace.log`
2. Ask Claude: "Spawn the `zz-hooktest` agent and have it run `echo A`."
3. `cat /tmp/hooktrace.log` — expect `agent-pre` (PreToolUse, with agent_id/agent_type) and `agent-stop`
   (hook_event_name `SubagentStop` if the Stop→SubagentStop conversion works), and `proj` set.
Also try once with `claude -p` (headless) to see the workspace-trust effect.
Delete this branch afterwards.
