#!/usr/bin/env python3
"""Throwaway: appends one JSON line per hook call to /tmp/hooktrace.log."""
import json, os, sys
p = json.load(sys.stdin)
with open("/tmp/hooktrace.log", "a") as f:
    f.write(json.dumps({"tag": sys.argv[1], "session_id": p.get("session_id"), "event": p.get("hook_event_name"), "tool": p.get("tool_name"),
                        "agent_id": p.get("agent_id"), "agent_type": p.get("agent_type"),
                        "cmd": (p.get("tool_input") or {}).get("command", "")[:60],
                        "proj": os.environ.get("CLAUDE_PROJECT_DIR"), "remote": os.environ.get("CLAUDE_CODE_REMOTE")}) + "\n")
