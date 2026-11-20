---
name: zz-hooktest
description: Throwaway test agent for frontmatter hooks. Use only when explicitly asked to test hooks.
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: '"${CLAUDE_PROJECT_DIR}"/scripts/hooks/trace.py agent-pre'
  Stop:
    - hooks:
        - type: command
          command: '"${CLAUDE_PROJECT_DIR}"/scripts/hooks/trace.py agent-stop'
---
You run exactly what the prompt asks, nothing more.
