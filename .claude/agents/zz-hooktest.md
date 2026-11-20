---
name: zz-hooktest
description: Throwaway test agent for frontmatter hooks. Use only when explicitly asked to test hooks.
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: 'python3 "${CLAUDE_PROJECT_DIR}/scripts/hooks/trace.py" agent-pre-var'
        - type: command
          command: 'python3 scripts/hooks/trace.py agent-pre-rel'
        - type: command
          command: 'touch /tmp/hook-agent-touch'
  Stop:
    - hooks:
        - type: command
          command: 'python3 "${CLAUDE_PROJECT_DIR}/scripts/hooks/trace.py" agent-stop'
---
You run exactly what the prompt asks, nothing more.
