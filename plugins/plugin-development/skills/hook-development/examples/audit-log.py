#!/usr/bin/env python3
"""Append userPromptSubmitted hook payloads to COPILOT_PLUGIN_DATA as JSONL."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def load_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {"_parse_error": "empty stdin"}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"_parse_error": f"invalid JSON: {exc.msg}"}
    return payload if isinstance(payload, dict) else {"_parse_error": "payload is not an object"}


def main() -> int:
    data_dir = os.environ.get("COPILOT_PLUGIN_DATA")
    if not data_dir:
        return 0

    payload = load_payload()
    raw_prompt = payload.get("prompt")
    prompt = raw_prompt if isinstance(raw_prompt, str) else ""
    record = {
        "recordedAt": int(time.time() * 1000),
        "event": payload.get("hook_event_name") or "userPromptSubmitted",
        "sessionId": payload.get("sessionId") or payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "prompt": prompt,
        "promptLength": len(prompt),
    }
    if "_parse_error" in payload:
        record["parseError"] = payload["_parse_error"]

    try:
        root = Path(data_dir).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        with (root / "audit-log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as exc:
        print(f"audit-log hook skipped: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
