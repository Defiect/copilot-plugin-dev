#!/usr/bin/env python3
"""Scaffold a GitHub Copilot CLI plugin marketplace repository."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_LOCATIONS = (
    "marketplace.json",
    ".plugin/marketplace.json",
    ".github/plugin/marketplace.json",
    ".claude-plugin/marketplace.json",
)
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def marketplace_manifest(name: str, owner: str, email: str | None, layout: str) -> dict[str, Any]:
    owner_obj: dict[str, str] = {"name": owner}
    if email:
        owner_obj["email"] = email
    metadata: dict[str, str] = {
        "description": f"Curated GitHub Copilot CLI plugins for {owner}.",
        "version": "0.1.0",
    }
    if layout == "monorepo":
        metadata["pluginRoot"] = "plugins"
    return {
        "name": name,
        "owner": owner_obj,
        "metadata": metadata,
        "plugins": [],
    }


def readme(name: str) -> str:
    return f"""# {name}

This repository is a GitHub Copilot CLI plugin marketplace.

## Install

```bash
copilot plugin marketplace add /absolute/path/to/this/repository
copilot plugin install example-plugin@{name}
```

Add plugin entries to `.github/plugin/marketplace.json` before publishing.
"""


def mit_license(author: str) -> str:
    year = datetime.now(tz=timezone.utc).year
    return f"""MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a Copilot CLI plugin marketplace repository.")
    parser.add_argument("--name", required=True, help="kebab-case marketplace name")
    parser.add_argument("--owner", required=True, help="owner or maintainer name")
    parser.add_argument("--email", help="owner contact email")
    parser.add_argument("--layout", choices=("single", "monorepo", "index"), default="monorepo")
    parser.add_argument(
        "--manifest-location",
        default=".github/plugin/marketplace.json",
        help="manifest path to create (default: .github/plugin/marketplace.json)",
    )
    parser.add_argument("--dir", default=".", help="directory to create or update")
    parser.add_argument("--author", default=None, help="copyright holder for the MIT LICENSE")
    parser.add_argument("--force", action="store_true", help="overwrite existing scaffold files")
    args = parser.parse_args(argv)

    if not NAME_RE.match(args.name):
        print(f"error: --name must be kebab-case: {args.name!r}", file=sys.stderr)
        return 2
    if args.manifest_location not in MANIFEST_LOCATIONS:
        print(
            "error: --manifest-location must be one of: " + ", ".join(MANIFEST_LOCATIONS),
            file=sys.stderr,
        )
        return 2

    root = Path(args.dir).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        manifest = marketplace_manifest(args.name, args.owner, args.email, args.layout)
        write_file(root / args.manifest_location, json.dumps(manifest, indent=2) + "\n", args.force)
        (root / "plugins").mkdir(exist_ok=True)
        write_file(root / "README.md", readme(args.name), args.force)
        write_file(root / "LICENSE", mit_license(args.author or args.owner), args.force)
        write_file(root / ".gitignore", ".DS_Store\n*.log\n__pycache__/\n", args.force)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: could not create marketplace: {exc}", file=sys.stderr)
        return 1

    print(f"Created marketplace scaffold at {root}")
    print()
    print("Next steps:")
    print("1. Add a real plugin with add_plugin.py or by editing the plugins array.")
    print("2. Run scripts/validate_marketplace.py on the created manifest.")
    print("3. Add the marketplace locally:")
    print(f"   copilot plugin marketplace add {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
