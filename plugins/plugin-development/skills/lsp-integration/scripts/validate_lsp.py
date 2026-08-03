#!/usr/bin/env python3
"""Validate GitHub Copilot CLI LSP server configuration files.

Pass either an LSP JSON file or a plugin directory. For a plugin directory, the validator
checks default LSP locations and the plugin.json lspServers field when present.

Exit codes:
    0  no validation errors
    1  validation errors, or warnings with --warnings-as-errors
    2  bad invocation or unreadable path
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

LAUNCH_FIELDS = ("command", "bash", "powershell")
PLUGIN_ROOT_RE = re.compile(r"\$\{PLUGIN_ROOT\}(/[^\s'\"]+)")


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


def find_plugin_root(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if find_plugin_manifest(candidate):
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
        return [Source(str(path), path, data, find_plugin_root(path), duplicates)], messages, True
    if not path.is_dir():
        return [], [Message("error", str(path), "path is neither a file nor a directory")], False

    sources: list[Source] = []
    seen_files: set[Path] = set()
    for rel in ("lsp.json", ".github/lsp.json", "lsp-config/servers.json"):
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
        elif isinstance(data, dict) and "lspServers" in data:
            field_value = data["lspServers"]
            if isinstance(field_value, str):
                target = (manifest.parent / field_value).resolve()
                if target in seen_files:
                    messages.append(
                        Message("note", str(manifest), f"lspServers points to already validated {field_value}")
                    )
                elif target.is_file():
                    target_data, target_duplicates, target_error = load_json(target)
                    if target_error:
                        messages.append(Message("error", str(target), target_error))
                    else:
                        sources.append(
                            Source(
                                f"plugin.json lspServers path {field_value}",
                                target,
                                target_data,
                                path,
                                target_duplicates,
                            )
                        )
                        seen_files.add(target)
                else:
                    messages.append(Message("error", str(manifest), f"lspServers path does not exist: {field_value}"))
            elif isinstance(field_value, dict):
                sources.append(
                    Source("plugin.json lspServers", manifest, {"lspServers": field_value}, path, duplicates)
                )
            else:
                messages.append(Message("error", str(manifest), "lspServers must be a path string or object"))

    if not sources and not messages:
        messages.append(
            Message(
                "error",
                str(path),
                "no LSP config found (lsp.json, .github/lsp.json, lsp-config/servers.json, or plugin.json lspServers)",
            )
        )
    return sources, messages, True


def shape_servers(source: Source, messages: list[Message]) -> dict[str, Any] | None:
    data = source.data
    if not isinstance(data, dict):
        messages.append(Message("error", source.label, "top-level JSON value must be an object"))
        return None
    if "lspServers" in data:
        servers = data["lspServers"]
        messages.append(Message("note", source.label, "detected lspServers object shape"))
    else:
        servers = data
        messages.append(Message("note", source.label, "detected bare top-level LSP server map shape"))
    if not isinstance(servers, dict):
        messages.append(Message("error", source.label, "LSP servers must be an object/map"))
        return None
    return servers


def is_abs_not_plugin(value: str) -> bool:
    return PurePosixPath(value).is_absolute() and not value.startswith("${PLUGIN_ROOT}")


def warn_absolute(source: str, server_name: str, field_name: str, value: Any, messages: list[Message]) -> None:
    values: list[str] = []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [item for item in value if isinstance(item, str)]
    for item in values:
        first = shlex.split(item)[0] if field_name in {"bash", "powershell"} else item
        if is_abs_not_plugin(first):
            messages.append(
                Message(
                    "warning",
                    source,
                    f"{server_name}.{field_name} uses an absolute path not rooted at ${{PLUGIN_ROOT}}",
                )
            )


def check_plugin_root_scripts(
    source: Source, server_name: str, field_name: str, value: Any, messages: list[Message]
) -> None:
    if source.plugin_root is None or not isinstance(value, str):
        return
    for match in PLUGIN_ROOT_RE.finditer(value):
        rel = match.group(1).lstrip("/")
        candidate = source.plugin_root / rel
        if not candidate.exists():
            messages.append(
                Message(
                    "note",
                    source.label,
                    f"{server_name}.{field_name} references ${{PLUGIN_ROOT}}/{rel}, which does not "
                    f"exist relative to {source.plugin_root}",
                )
            )


def validate_file_extensions(
    source: str, server_name: str, value: Any, messages: list[Message], extension_owners: dict[str, str]
) -> None:
    if value is None:
        messages.append(Message("error", source, f"{server_name}.fileExtensions is required"))
        return
    if not isinstance(value, dict) or not value:
        messages.append(
            Message(
                "error",
                source,
                f"{server_name}.fileExtensions must be a non-empty object mapping extensions to language IDs",
            )
        )
        return
    dotted = 0
    undotted = 0
    for ext, language_id in value.items():
        if not isinstance(ext, str) or not isinstance(language_id, str):
            messages.append(
                Message(
                    "error",
                    source,
                    f"{server_name}.fileExtensions entries must map string extensions to string language IDs",
                )
            )
            continue
        if ext.startswith("."):
            dotted += 1
        else:
            undotted += 1
        if ext in extension_owners:
            messages.append(
                Message(
                    "warning", source, f"extension {ext!r} is claimed by both {extension_owners[ext]} and {server_name}"
                )
            )
        else:
            extension_owners[ext] = server_name
    if dotted and undotted:
        messages.append(
            Message("warning", source, f"{server_name}.fileExtensions mixes leading-dot and no-dot extensions")
        )


def validate_server(
    source: Source, name: str, server: Any, messages: list[Message], extension_owners: dict[str, str]
) -> None:
    if not isinstance(name, str) or not name:
        messages.append(Message("error", source.label, "server names must be non-empty strings"))
        return
    if not isinstance(server, dict):
        messages.append(Message("error", source.label, f"{name} must be an object"))
        return

    validate_file_extensions(source.label, name, server.get("fileExtensions"), messages, extension_owners)

    present = [name_ for name_ in LAUNCH_FIELDS if server.get(name_)]
    if not present:
        messages.append(Message("error", source.label, f"{name} must define one of command, bash, or powershell"))
    elif len(present) > 1:
        messages.append(
            Message(
                "error", source.label, f"{name} defines multiple launch forms {present}; use one for this plugin config"
            )
        )
    for launch_field in present:
        if not isinstance(server[launch_field], str) or not server[launch_field].strip():
            messages.append(Message("error", source.label, f"{name}.{launch_field} must be a non-empty string"))
        warn_absolute(source.label, name, launch_field, server[launch_field], messages)
        check_plugin_root_scripts(source, name, launch_field, server[launch_field], messages)

    args = server.get("args")
    if args is not None:
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            messages.append(Message("error", source.label, f"{name}.args must be a list of strings"))
        if any(field in present for field in ("bash", "powershell")):
            messages.append(
                Message("warning", source.label, f"{name}.args is set with bash/powershell and will be ignored")
            )
        warn_absolute(source.label, name, "args", args, messages)

    env = server.get("env")
    if env is not None and not isinstance(env, dict):
        messages.append(Message("error", source.label, f"{name}.env must be an object"))
    cwd = server.get("cwd")
    if cwd is not None:
        if not isinstance(cwd, str):
            messages.append(Message("error", source.label, f"{name}.cwd must be a string"))
        else:
            warn_absolute(source.label, name, "cwd", cwd, messages)


def validate_sources(sources: list[Source], initial_messages: list[Message]) -> list[Message]:
    messages = list(initial_messages)
    extension_owners: dict[str, str] = {}
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
                        f"duplicate LSP server name {name!r}; previous definition came from {seen_server_names[name]}",
                    )
                )
            seen_server_names[name] = source.label
            validate_server(source, name, server, messages, extension_owners)
    return messages


def render_text(messages: list[Message], quiet: bool) -> None:
    if quiet and not any(m.level == "error" for m in messages):
        return
    for message in messages:
        if quiet and message.level in {"note", "warning"}:
            continue
        print(f"{message.level.upper():7} {message.source}: {message.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Copilot CLI LSP server JSON.")
    parser.add_argument("path", help="LSP JSON file or plugin directory")
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
