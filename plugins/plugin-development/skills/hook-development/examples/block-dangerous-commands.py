#!/usr/bin/env python3
"""preToolUse guardrail that denies obviously destructive shell commands.

Cross-platform: run it from both the `bash` and `powershell` fields of a hook entry so
the guardrail is present on Linux, macOS, and Windows.

Deny-list semantics: this hook prints a deny decision for a command it recognizes as
dangerous and prints *nothing at all* otherwise. Printing `{"permissionDecision": "allow"}`
for safe commands would auto-approve every shell call and bypass the user's normal
permission prompt, which is the opposite of what a guardrail should do. Empty output means
"fall through to default behavior".
"""

from __future__ import annotations

import json
import re
import sys

SHELL_TOOLS = {"bash", "Bash", "powershell", "PowerShell", "shell"}

COMMAND_KEYS = ("command", "cmd", "script")

DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (
        r"(?is)(^|[;&|])\s*rm\s+[^\n]*(?:-[^\n]*r[^\n]*f|-[^\n]*f[^\n]*r)"
        r"[^\n]*(?:\s(?:--\s*)?/(?:\s|$|\*)|\$HOME|~|\s\.\.?(?:\s|$))",
        "recursive forced removal of a broad path",
    ),
    (r"(?is)(^|[;&|])\s*(sudo\s+)?(?:mkfs|mkswap)\b", "filesystem formatting command"),
    (r"(?is)(^|[;&|])\s*dd\b[^\n]*(?:of=/dev/|of=\$)", "raw disk write with dd"),
    (r"(?is)(^|[;&|])\s*(sudo\s+)?chmod\s+-R\s+777\s+(?:/|\$HOME|~)", "broad chmod 777"),
    (
        r"(?is)(^|[;&|])\s*(sudo\s+)?chown\s+-R\b[^\n]*(?:\s/\s*$|\s/\s|\$HOME|~)",
        "broad recursive ownership change",
    ),
    (r"(?is):\s*\(\)\s*\{\s*:\s*\|\s*:\s*&\s*}\s*;\s*:", "fork bomb"),
    (
        r"(?is)\b(?:curl|wget)\b[^\n|;&]*(?:\|\s*(?:sudo\s+)?(?:sh|bash)\b)",
        "downloaded script piped to a shell",
    ),
    (
        r"(?is)(^|[;&|])\s*(?:Remove-Item|ri|rm|del)\b[^\n]*-Recurse\b[^\n]*-Force\b"
        r"[^\n]*(?:[A-Za-z]:\\\s*$|\$env:USERPROFILE|\$HOME)",
        "recursive forced removal of a broad path (PowerShell)",
    ),
    (
        r"(?is)\b(?:Invoke-WebRequest|Invoke-RestMethod|iwr|irm|curl)\b[^\n]*\|\s*(?:iex|Invoke-Expression)\b",
        "downloaded script piped to Invoke-Expression",
    ),
]


def deny(reason: str) -> None:
    json.dump({"permissionDecision": "deny", "permissionDecisionReason": reason}, sys.stdout)
    sys.stdout.write("\n")


def extract_command(payload: dict[str, object]) -> tuple[str, str]:
    """Return (tool_name, command_string) from a preToolUse payload."""
    tool = payload.get("toolName") or payload.get("tool_name") or ""
    args: object = payload.get("toolArgs", payload.get("tool_input", {}))

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return str(tool), args

    if isinstance(args, dict):
        for key in COMMAND_KEYS:
            value = args.get(key)
            if isinstance(value, str):
                return str(tool), value
    return str(tool), ""


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        deny("Blocked because the preToolUse payload was empty.")
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        deny("Blocked because the preToolUse payload was not valid JSON.")
        return 0

    if not isinstance(payload, dict):
        deny("Blocked because the preToolUse payload was not a JSON object.")
        return 0

    tool, command = extract_command(payload)

    if tool not in SHELL_TOOLS:
        return 0

    if not command.strip():
        deny("Blocked because the shell command was missing from the payload.")
        return 0

    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            deny(f"Blocked dangerous shell command: {reason}.")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
