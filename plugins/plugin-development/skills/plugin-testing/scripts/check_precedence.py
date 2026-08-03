#!/usr/bin/env python3
"""Report project or personal skills that shadow plugin skills, and list plugin agent IDs.

Skills and agents behave differently. Plugin skills share one flat namespace with project
and personal skills and lose every collision, so they need checking. Plugin agents are
registered under a `<plugin-name>:<agent-id>` namespace and cannot be shadowed, so this
script reports their qualified IDs instead of treating same-named agents as collisions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SKILL_NAME_RE = re.compile(r"^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$", re.MULTILINE)


def read_skill_name(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    match = SKILL_NAME_RE.search(text[:end])
    return match.group(1).strip() if match else None


def collect_skills(root: Path, scope: str) -> dict[str, list[dict[str, str]]]:
    found: dict[str, list[dict[str, str]]] = {}
    if not root.is_dir():
        return found
    for skill_md in sorted(root.glob("*/SKILL.md")):
        name = read_skill_name(skill_md)
        if not name:
            continue
        found.setdefault(name, []).append({"scope": scope, "path": str(skill_md.parent)})
    return found


def collect_agents(root: Path, scope: str) -> dict[str, list[dict[str, str]]]:
    found: dict[str, list[dict[str, str]]] = {}
    if not root.is_dir():
        return found
    for agent in sorted(root.glob("*.agent.md")):
        agent_id = agent.name[: -len(".agent.md")]
        found.setdefault(agent_id, []).append({"scope": scope, "path": str(agent)})
    return found


def merge(target: dict[str, list[dict[str, str]]], source: dict[str, list[dict[str, str]]]) -> None:
    for name, entries in source.items():
        target.setdefault(name, []).extend(entries)


def first_existing(paths: list[tuple[Path, str]], collector) -> dict[str, list[dict[str, str]]]:
    combined: dict[str, list[dict[str, str]]] = {}
    for path, scope in paths:
        merge(combined, collector(path, scope))
    return combined


def plugin_name(plugin: Path) -> str:
    manifest = plugin / "plugin.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            data = None
        if isinstance(data, dict) and isinstance(data.get("name"), str):
            return data["name"]
    return plugin.name


def plugin_skill_roots(plugin: Path) -> list[Path]:
    manifest = plugin / "plugin.json"
    if not manifest.is_file():
        return [plugin / "skills"]
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return [plugin / "skills"]
    value = data.get("skills", "skills/") if isinstance(data, dict) else "skills/"
    if isinstance(value, str):
        return [plugin / value]
    if isinstance(value, list):
        return [plugin / item for item in value if isinstance(item, str)]
    return [plugin / "skills"]


def plugin_agent_roots(plugin: Path) -> list[Path]:
    manifest = plugin / "plugin.json"
    if not manifest.is_file():
        return [plugin / "agents"]
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return [plugin / "agents"]
    value = data.get("agents", "agents/") if isinstance(data, dict) else "agents/"
    if isinstance(value, str):
        return [plugin / value]
    if isinstance(value, list):
        return [plugin / item for item in value if isinstance(item, str)]
    return [plugin / "agents"]


def detect(plugin: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cwd = Path.cwd()
    home = Path(os.environ.get("COPILOT_HOME", str(Path.home() / ".copilot"))).expanduser()
    name_of_plugin = plugin_name(plugin)

    project_skill_roots = [(cwd / ".github/skills", "project .github/skills")]
    project_agent_roots = [(cwd / ".github/agents", "project .github/agents")]
    user_skill_roots = [(home / "skills", "user ~/.copilot/skills")]
    user_agent_roots = [(home / "agents", "user ~/.copilot/agents")]

    higher_skills: dict[str, list[dict[str, str]]] = {}
    merge(higher_skills, first_existing(project_skill_roots, collect_skills))
    merge(higher_skills, first_existing(user_skill_roots, collect_skills))

    higher_agents: dict[str, list[dict[str, str]]] = {}
    merge(higher_agents, first_existing(project_agent_roots, collect_agents))
    merge(higher_agents, first_existing(user_agent_roots, collect_agents))

    plugin_skills: dict[str, list[dict[str, str]]] = {}
    for root in plugin_skill_roots(plugin):
        merge(plugin_skills, collect_skills(root, "plugin skills"))
    plugin_agents: dict[str, list[dict[str, str]]] = {}
    for root in plugin_agent_roots(plugin):
        merge(plugin_agents, collect_agents(root, "plugin agents"))

    collisions: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []
    for name, plugin_entries in sorted(plugin_skills.items()):
        if name in higher_skills:
            collisions.append(
                {
                    "kind": "skill",
                    "name": name,
                    "winner": higher_skills[name][0],
                    "shadowed": plugin_entries,
                    "reason": "skills are first-found-wins and plugin skills load last",
                }
            )
    for name in sorted(plugin_agents):
        if name in higher_agents:
            notes.append(
                {
                    "kind": "agent",
                    "name": name,
                    "qualified": f"{name_of_plugin}:{name}",
                    "other": higher_agents[name][0],
                    "detail": (
                        "a project or personal agent shares this bare ID, but plugin agents are "
                        "namespaced and resolve independently; both remain reachable"
                    ),
                }
            )

    inventory = {
        "plugin_name": name_of_plugin,
        "plugin_skills": plugin_skills,
        "plugin_agents": {f"{name_of_plugin}:{k}": v for k, v in plugin_agents.items()},
        "higher_priority_skills": higher_skills,
        "higher_priority_agents": higher_agents,
    }
    return collisions, notes, inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect skill and agent precedence collisions for a plugin.")
    parser.add_argument("--plugin", required=True, help="plugin directory")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit JSON")
    args = parser.parse_args(argv)

    plugin = Path(args.plugin).expanduser().resolve()
    if not plugin.is_dir():
        print(f"error: plugin directory not found: {plugin}", file=sys.stderr)
        return 1

    collisions, notes, inventory = detect(plugin)
    if args.as_json:
        print(
            json.dumps(
                {"plugin": str(plugin), "collisions": collisions, "notes": notes, "inventory": inventory},
                indent=2,
            )
        )
    else:
        print(f"Checking precedence for plugin: {plugin}")
        agent_ids = sorted(inventory["plugin_agents"])
        if agent_ids:
            print("Plugin agents are namespaced and cannot be shadowed. Invoke them as:")
            for agent_id in agent_ids:
                print(f"  --agent {agent_id}")
        if not collisions:
            print("PASS  no project or personal skill shadows this plugin")
        else:
            print(f"FAIL  {len(collisions)} skill collision(s) found")
            for collision in collisions:
                print(f"  {collision['kind']} {collision['name']!r} is shadowed")
                print(f"    winner: {collision['winner']['scope']} at {collision['winner']['path']}")
                for shadowed in collision["shadowed"]:
                    print(f"    plugin copy: {shadowed['path']}")
                print(f"    why: {collision['reason']}")
                print("    fix: remove or rename the higher-priority copy, then reinstall the plugin")
        for note in notes:
            print(f"  note  agent {note['name']!r}: {note['detail']}")
            print(f"    plugin agent remains reachable as {note['qualified']}")
    return 1 if collisions else 0


if __name__ == "__main__":
    sys.exit(main())
