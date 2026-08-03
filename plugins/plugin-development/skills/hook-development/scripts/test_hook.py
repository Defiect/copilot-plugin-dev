#!/usr/bin/env python3
"""Run a hook handler locally with a synthetic or custom payload."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SAMPLE_PAYLOADS: dict[str, dict[str, Any]] = {
    "preToolUse": {
        "sessionId": "sample-session",
        "timestamp": 1760000000000,
        "cwd": ".",
        "toolName": "bash",
        "toolArgs": {"command": "git status --short"},
    },
    "postToolUse": {
        "sessionId": "sample-session",
        "timestamp": 1760000000000,
        "cwd": ".",
        "toolName": "edit",
        "toolArgs": {"file_path": "example.py"},
        "toolResult": {"resultType": "success", "textResultForLlm": "edited example.py"},
    },
    "sessionStart": {
        "sessionId": "sample-session",
        "timestamp": 1760000000000,
        "cwd": ".",
        "source": "new",
        "initialPrompt": "Help with this repository.",
    },
    "userPromptSubmitted": {
        "sessionId": "sample-session",
        "timestamp": 1760000000000,
        "cwd": ".",
        "prompt": "Please inspect the project.",
    },
    "permissionRequest": {
        "sessionId": "sample-session",
        "timestamp": 1760000000000,
        "cwd": ".",
        "toolName": "bash",
        "toolArgs": {"command": "git status --short"},
    },
}


def load_payload(args: argparse.Namespace) -> str:
    if args.payload == "-":
        return sys.stdin.read()
    if args.payload:
        return Path(args.payload).read_text(encoding="utf-8")
    payload = SAMPLE_PAYLOADS.get(args.event)
    if payload is None:
        raise SystemExit(f"no built-in sample payload for event {args.event!r}; use --payload")
    return json.dumps(payload, separators=(",", ":"))


def parse_stdout(text: str) -> tuple[Any | None, str | None]:
    stripped = text.strip()
    if not stripped:
        return None, "stdout is empty"
    preserved: list[str] = []
    for line in text.splitlines():
        candidate = line.strip()
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            preserved.append(line)
            continue
        if isinstance(obj, dict) and obj.get("type") == "progress":
            continue
        preserved.append(line)
    final = "\n".join(preserved).strip()
    if not final:
        return None, "stdout contained only progress messages"
    try:
        return json.loads(final), None
    except json.JSONDecodeError as exc:
        return None, f"stdout is not final JSON: {exc.msg}"


def interpret(event: str, returncode: int | None, timed_out: bool, output: Any | None) -> str:
    if timed_out:
        return "TIMEOUT: this hook would fail open; timeouts do not block tool calls."
    if event == "preToolUse":
        if returncode and returncode != 0:
            return "BLOCK: preToolUse command hooks fail closed on non-zero exit."
        if isinstance(output, dict):
            decision = output.get("permissionDecision")
            if decision == "deny":
                return "BLOCK: permissionDecision is deny."
            if decision == "ask":
                return "ASK: Copilot would ask the user; cloud agent treats ask as deny."
            if decision == "allow":
                return "ALLOW: permissionDecision is allow."
        return "DEFAULT: no preToolUse decision; normal permission flow applies."
    if event == "permissionRequest":
        if returncode == 2:
            return "DENY: permissionRequest exit code 2 is treated as deny."
        if isinstance(output, dict) and output.get("behavior") in {"allow", "deny"}:
            return f"{str(output['behavior']).upper()}: permissionRequest behavior is {output['behavior']}."
        return "DEFAULT: normal permission handling applies."
    if event in {"agentStop", "subagentStop"} and isinstance(output, dict) and output.get("decision") == "block":
        return "BLOCK: the agent would be forced to continue."
    if (
        event == "postToolUse"
        and isinstance(output, dict)
        and ("modifiedResult" in output or "additionalContext" in output)
    ):
        return "MODIFY: postToolUse output would change or augment the tool result."
    if event == "sessionStart" and isinstance(output, dict) and "additionalContext" in output:
        return "CONTEXT: additionalContext would be injected into the session."
    return "NO CONTROL DECISION: output has no blocking effect for this event."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a hook handler with a sample payload.")
    parser.add_argument("--event", default="preToolUse", help="event name for built-in payload and interpretation")
    parser.add_argument("--payload", help="payload JSON file, or - for stdin")
    parser.add_argument("--timeout", type=float, default=30.0, help="timeout in seconds")
    parser.add_argument("handler", nargs=argparse.REMAINDER, help="handler command to run")
    args = parser.parse_args(argv)

    if not args.handler:
        parser.error("handler command is required")
    if args.handler and args.handler[0] == "--":
        args.handler = args.handler[1:]
    if not args.handler:
        parser.error("handler command is required")

    payload = load_payload(args)
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            args.handler,
            input=payload,
            text=True,
            capture_output=True,
            timeout=args.timeout,
            check=False,
        )
        returncode: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="replace")

    elapsed = time.monotonic() - started
    parsed, parse_error = parse_stdout(stdout)

    print(f"event: {args.event}")
    print(f"command: {' '.join(args.handler)}")
    print(f"elapsedSec: {elapsed:.3f}")
    print(f"exitCode: {'timeout' if timed_out else returncode}")
    print("stdout:")
    print(stdout if stdout else "(empty)")
    print("stderr:")
    print(stderr if stderr else "(empty)")
    if parse_error:
        print(f"stdoutJson: no ({parse_error})")
    else:
        print(f"stdoutJson: yes ({json.dumps(parsed, separators=(',', ':'))})")
    print(f"interpretation: {interpret(args.event, returncode, timed_out, parsed)}")
    if timed_out:
        print("warning: hook exceeded the configured timeout; Copilot hook timeouts fail open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
