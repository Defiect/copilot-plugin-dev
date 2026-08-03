#!/usr/bin/env python3
"""Validate GitHub Copilot CLI MCP server configuration files.

Pass either an MCP JSON file or a plugin directory. For a plugin directory, the validator
checks default MCP locations and the plugin.json mcpServers field when present.

Exit codes:
    0  no validation errors
    1  validation errors, or warnings with --warnings-as-errors
    2  bad invocation or unreadable path
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

VALID_TYPES = {"local", "stdio", "http", "sse", "streamable-http"}
LOCAL_TYPES = {"local", "stdio"}
REMOTE_TYPES = {"http", "sse"}
SECRET_VALUE_RE = re.compile(
    r"(ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|"
    r"\b[0-9a-fA-F]{40,}\b|\b[A-Za-z0-9+/]{40,}={0,2}\b)"
)
SECRET_KEY_RE = re.compile(r"(token|secret|password|api[_-]?key)", re.IGNORECASE)
VAR_REF_RE = re.compile(r"\$(?:\{[A-Za-z_][A-Za-z0-9_]*(?::-[^}]*)?\}|[A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class Message:
    level: str
    source: str
    message: str


@dataclass
class Source:
    label: str
    path: Path | None
    data: Any
    plugin_root: Path | None = None
    duplicate_keys: list[str] = field(default_factory=list)


class DuplicateTrackingDecoder(json.JSONDecoder):
    def __init__(self) -> None:
        self.duplicates: list[str] = []
        super().__init__(object_pairs_hook=self._pairs)

    def _pairs(self, pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                self.duplicates.append(key)
            seen.add(key)
            result[key] = value
        return result


def load_json(path: Path) -> tuple[Any | None, list[str], str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [], f"cannot read file: {exc}"
    decoder = DuplicateTrackingDecoder()
    try:
        data = decoder.decode(text)
    except json.JSONDecodeError as exc:
        return None, decoder.duplicates, f"invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"
    return data, decoder.duplicates, None


def find_plugin_manifest(plugin_dir: Path) -> Path | None:
    for rel in (".plugin/plugin.json", "plugin.json", ".github/plugin/plugin.json", ".claude-plugin/plugin.json"):
        candidate = plugin_dir / rel
        if candidate.is_file():
            return candidate
    return None


def discover_sources(path: Path) -> tuple[list[Source], list[Message], bool]:
    messages: list[Message] = []
    if not path.exists():
        return [], [Message("error", str(path), "path does not exist")], False
    if path.is_file():
        data, duplicates, error = load_json(path)
        if error:
            return [], [Message("error", str(path), error)], False
        return [Source(str(path), path, data, path.parent, duplicates)], messages, True
    if not path.is_dir():
        return [], [Message("error", str(path), "path is neither a file nor a directory")], False

    sources: list[Source] = []
    seen_files: set[Path] = set()
    for rel in (".mcp.json", ".github/mcp.json"):
        candidate = path / rel
        if candidate.is_file():
            data, duplicates, error = load_json(candidate)
            if error:
                messages.append(Message("error", str(candidate), error))
            else:
                sources.append(Source(rel, candidate, data, path, duplicates))
                seen_files.add(candidate.resolve())

    manifest = find_plugin_manifest(path)
    if manifest:
        data, duplicates, error = load_json(manifest)
        if error:
            messages.append(Message("error", str(manifest), error))
        elif isinstance(data, dict) and "mcpServers" in data:
            field_value = data["mcpServers"]
            if isinstance(field_value, str):
                target = (manifest.parent / field_value).resolve()
                if target in seen_files:
                    messages.append(
                        Message("note", str(manifest), f"mcpServers points to already validated {field_value}")
                    )
                elif target.is_file():
                    target_data, target_duplicates, target_error = load_json(target)
                    if target_error:
                        messages.append(Message("error", str(target), target_error))
                    else:
                        sources.append(
                            Source(
                                f"plugin.json mcpServers path {field_value}",
                                target,
                                target_data,
                                path,
                                target_duplicates,
                            )
                        )
                        seen_files.add(target)
                else:
                    messages.append(Message("error", str(manifest), f"mcpServers path does not exist: {field_value}"))
            elif isinstance(field_value, dict):
                sources.append(
                    Source("plugin.json mcpServers", manifest, {"mcpServers": field_value}, path, duplicates)
                )
            else:
                messages.append(Message("error", str(manifest), "mcpServers must be a path string or object"))

    if not sources and not messages:
        messages.append(
            Message("error", str(path), "no MCP config found (.mcp.json, .github/mcp.json, or plugin.json mcpServers)")
        )
    return sources, messages, True


def shape_servers(source: Source, messages: list[Message]) -> dict[str, Any] | None:
    data = source.data
    if not isinstance(data, dict):
        messages.append(Message("error", source.label, "top-level JSON value must be an object"))
        return None
    if "servers" in data:
        messages.append(
            Message(
                "error",
                source.label,
                "uses VS Code top-level 'servers'; Copilot CLI reads 'mcpServers' or a bare project-level map",
            )
        )
    if "mcpServers" in data:
        servers = data["mcpServers"]
        messages.append(Message("note", source.label, "detected mcpServers object shape"))
    else:
        servers = data
        messages.append(Message("note", source.label, "detected bare top-level server map shape"))
    if not isinstance(servers, dict):
        messages.append(Message("error", source.label, "MCP servers must be an object/map"))
        return None
    return servers


def is_var_reference(value: str) -> bool:
    return bool(VAR_REF_RE.search(value))


def check_secret(source: str, path: str, key: str, value: Any, messages: list[Message]) -> None:
    if not isinstance(value, str):
        return
    if is_var_reference(value):
        return
    if SECRET_VALUE_RE.search(value):
        messages.append(Message("error", source, f"{path} contains a value that looks like a literal secret"))
        return
    if SECRET_KEY_RE.search(key) and value:
        messages.append(
            Message(
                "error",
                source,
                f"{path} key name looks secret-bearing but value is a literal; use an environment-variable reference",
            )
        )


def check_string_map(source: str, server_name: str, field_name: str, value: Any, messages: list[Message]) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        messages.append(Message("error", source, f"{server_name}.{field_name} must be an object"))
        return
    for key, item in value.items():
        if not isinstance(key, str):
            messages.append(Message("error", source, f"{server_name}.{field_name} contains a non-string key"))
            continue
        if not isinstance(item, str):
            messages.append(Message("error", source, f"{server_name}.{field_name}.{key} must be a string"))
            continue
        check_secret(source, f"{server_name}.{field_name}.{key}", key, item, messages)


def warn_plugin_root_absolute(
    source: str, server_name: str, field_name: str, value: Any, messages: list[Message]
) -> None:
    values: list[str] = []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [item for item in value if isinstance(item, str)]
    for item in values:
        if "${PLUGIN_ROOT}" in item and item.startswith(os.sep):
            messages.append(
                Message(
                    "warning",
                    source,
                    f"{server_name}.{field_name} combines an absolute path with ${{PLUGIN_ROOT}}; "
                    "use ${PLUGIN_ROOT}/... directly",
                )
            )


def infer_type(server: dict[str, Any]) -> str | None:
    if isinstance(server.get("command"), str):
        return "stdio"
    if isinstance(server.get("url"), str):
        url = server["url"].lower()
        return "sse" if url.endswith("/sse") or "sse" in url else "http"
    return None


def validate_server(source: Source, name: str, server: Any, messages: list[Message]) -> None:
    if not isinstance(name, str) or not name:
        messages.append(Message("error", source.label, "server names must be non-empty strings"))
        return
    if not isinstance(server, dict):
        messages.append(Message("error", source.label, f"{name} must be an object"))
        return

    raw_type = server.get("type")
    if raw_type is None:
        inferred = infer_type(server)
        if inferred:
            messages.append(
                Message("warning", source.label, f"{name} omits type; inferred {inferred}. Write type explicitly.")
            )
            server_type = inferred
        else:
            messages.append(
                Message("error", source.label, f"{name}.type is required and must be one of {sorted(VALID_TYPES)}")
            )
            return
    elif not isinstance(raw_type, str) or raw_type not in VALID_TYPES:
        messages.append(Message("error", source.label, f"{name}.type must be one of {sorted(VALID_TYPES)}"))
        return
    else:
        server_type = raw_type

    tools = server.get("tools")
    if tools is not None and (not isinstance(tools, list) or not all(isinstance(item, str) for item in tools)):
        messages.append(Message("error", source.label, f"{name}.tools must be a list of strings"))

    if server_type in LOCAL_TYPES:
        command = server.get("command")
        args = server.get("args")
        if not isinstance(command, str) or not command:
            messages.append(Message("error", source.label, f"{name}.command is required for {server_type} servers"))
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            messages.append(
                Message(
                    "error",
                    source.label,
                    f"{name}.args is required for {server_type} servers and must be a list of strings",
                )
            )
        check_string_map(source.label, name, "env", server.get("env"), messages)
        warn_plugin_root_absolute(source.label, name, "command", command, messages)
        warn_plugin_root_absolute(source.label, name, "args", args, messages)
    elif server_type in REMOTE_TYPES:
        url = server.get("url")
        if not isinstance(url, str) or not url:
            messages.append(Message("error", source.label, f"{name}.url is required for {server_type} servers"))
        else:
            parsed = urlparse(url)
            if parsed.scheme == "http":
                messages.append(
                    Message("warning", source.label, f"{name}.url uses http://; use https:// for committed configs")
                )
            elif parsed.scheme != "https":
                messages.append(
                    Message("error", source.label, f"{name}.url must use https:// for {server_type} servers")
                )
        check_string_map(source.label, name, "headers", server.get("headers"), messages)


def validate_sources(sources: list[Source], initial_messages: list[Message]) -> list[Message]:
    messages = list(initial_messages)
    seen_server_names: dict[str, str] = {}
    for source in sources:
        for dup in source.duplicate_keys:
            messages.append(Message("error", source.label, f"duplicate JSON key: {dup}"))
        servers = shape_servers(source, messages)
        if servers is None:
            continue
        for name, server in servers.items():
            if name in seen_server_names:
                messages.append(
                    Message(
                        "warning",
                        source.label,
                        f"duplicate server name {name!r}; previous definition came from "
                        f"{seen_server_names[name]} and MCP uses last-wins",
                    )
                )
            seen_server_names[name] = source.label
            validate_server(source, name, server, messages)
    return messages


def render_text(messages: list[Message], quiet: bool) -> None:
    if quiet and not any(m.level == "error" for m in messages):
        return
    for message in messages:
        if quiet and message.level in {"note", "warning"}:
            continue
        print(f"{message.level.upper():7} {message.source}: {message.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Copilot CLI MCP server JSON.")
    parser.add_argument("path", help="MCP JSON file or plugin directory")
    parser.add_argument("--json", dest="as_json", action="store_true", help="emit JSON report")
    parser.add_argument("--quiet", action="store_true", help="suppress notes and warnings")
    parser.add_argument("--warnings-as-errors", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    path = Path(args.path).expanduser()
    sources, messages, ok_invocation = discover_sources(path)
    if ok_invocation:
        messages = validate_sources(sources, messages)

    errors = sum(1 for message in messages if message.level == "error")
    warnings = sum(1 for message in messages if message.level == "warning")
    exit_code = 2 if not ok_invocation else 1 if errors or (args.warnings_as_errors and warnings) else 0

    if args.as_json:
        print(
            json.dumps(
                {
                    "messages": [message.__dict__ for message in messages],
                    "errors": errors,
                    "warnings": warnings,
                    "exit_code": exit_code,
                },
                indent=2,
            )
        )
    else:
        render_text(messages, args.quiet)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
