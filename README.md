# copilot-plugin-dev

A [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli) plugin marketplace for building Copilot CLI extensions.

Copilot CLI ships no built-in guidance for authoring plugins. This marketplace fills that gap with **`plugin-development`** — a plugin that teaches an agent everything needed to build, validate, test, and publish Copilot CLI plugins, with executable tooling for the parts that should never be done by hand.

## Install

```bash
copilot plugin marketplace add Defiect/copilot-plugin-dev
copilot plugin install plugin-development@copilot-plugin-dev
```

The `@marketplace` suffix is required. A bare `copilot plugin install plugin-development`
fails with `Invalid plugin spec`. Direct installs from a repo, URL, or local path still work
but are deprecated — the CLI warns that only `plugin@marketplace` installs will be supported
in a future release.

Verify it loaded:

```bash
copilot skill list          # 8 skills appear under "Plugin skills"
copilot plugin list         # shows plugin-development@copilot-plugin-dev (v1.0.0)
```

Agents shipped by a plugin are namespaced, so invoke them with the plugin prefix:

```bash
copilot --agent plugin-development:plugin-validator -p "Review ./my-plugin"
```

## What's inside

The `plugin-development` plugin ships **8 skills**, **3 custom agents**, and **15 executable scripts**.

### Skills

| Skill | Covers |
| --- | --- |
| `plugin-development` | `plugin.json`, manifest discovery order, directory layout, component wiring |
| `skill-development` | Authoring `SKILL.md`, frontmatter, progressive disclosure, description triggers |
| `agent-development` | Custom agents, `.agent.md` frontmatter, tool allowlists, delegation design |
| `hook-development` | All hook events, `hooks.json`, payload/output schemas, matchers, exit-code semantics |
| `mcp-integration` | Bundling MCP servers, server types, transports, secrets, `${PLUGIN_ROOT}` |
| `lsp-integration` | Language server config, `fileExtensions` maps, bundled wrappers |
| `marketplace-development` | `marketplace.json`, plugin entries, versioning, publishing |
| `plugin-testing` | The local dev loop, cache behavior, precedence debugging, smoke tests |

### Agents

| Agent | Purpose |
| --- | --- |
| `plugin-validator` | Full-plugin conformance review against the spec |
| `skill-reviewer` | Deep quality review of a single `SKILL.md` |
| `agent-architect` | Designs custom agents from a described need |

### Scripts

Scaffolding (`init_plugin.py`, `init_skill.py`, `init_marketplace.py`) and validation (`validate_plugin.py`, `validate_skill.py`, `validate_agent.py`, `validate_hooks.py`, `validate_mcp.py`, `validate_lsp.py`, `validate_marketplace.py`), plus `test_hook.py`, `check_precedence.py`, `add_plugin.py`, `bump_version.py`, and `smoke_test_plugin.sh`.

Every script runs standalone with `python3` and no required third-party dependencies. PyYAML is used when available; otherwise a built-in fallback parser handles frontmatter.

## Design principle

The guiding standard is **informational self-sufficiency**: an agent with this plugin installed, and no network access, should be able to build any spec-conformant Copilot CLI plugin without consulting the docs.

Scope is the **authoring surface** — anything written into a file, plus the local development loop. End-user actions (installing, enabling, and managing plugins) are deliberately out of scope, the same way a guide to writing Rust programs documents `cargo build` but not how a user double-clicks an installer.

## Repository layout

```
.
├── .github/
│   ├── plugin/marketplace.json     # Marketplace manifest
│   └── workflows/validate.yml      # CI: validators + ruff + ty
├── plugins/
│   └── plugin-development/
│       ├── plugin.json
│       ├── agents/                 # 3 custom agents
│       └── skills/                 # 8 skills, each with references/, examples/, scripts/
├── scripts/validate-all.sh         # Run every validator
├── AGENTS.md                       # Operating guide for agents working on this repo
└── ruff.toml
```

## Development

```bash
./scripts/validate-all.sh     # all validators, warnings treated as errors
ruff check plugins/ && ruff format --check plugins/
ty check plugins/
```

To test changes against a real session, load the plugin straight from the working tree:

```bash
copilot --plugin-dir ./plugins/plugin-development
```

Nothing is copied, so there is no reinstall step and no stale cache. One quirk: `copilot skill
list` does **not** report `--plugin-dir` skills even though they load correctly — use `/skills
list` and `/agent` inside the session instead.

Use `copilot plugin install ./plugins/plugin-development` only for a final check of the
installed layout. It caches contents at install time, so it must be re-run after every edit,
and it now prints a deprecation warning.

## Gotchas worth knowing

These were confirmed by experiment against Copilot CLI v1.0.78, and some contradict the
published docs. The plugin's own reference files cover them in full.

- **Personal skills shadow plugin skills** of the same name — yours silently disappears from
  the list. Custom agents behave the opposite way: they are always namespaced
  `<plugin>:<agent>`, so they can neither shadow nor be shadowed.
- **Skill names are only qualified on collision**, and the separator is a colon
  (`plugin-a:shared-name`), not the slash the docs show.
- **Installing the same plugin twice** (once from a marketplace, once from a local path) leaves
  both entries in `copilot plugin list`, but the skills are silently deduplicated. A bare
  `copilot plugin uninstall <name>` then removes the *marketplace* copy first.
- **`copilot plugins` (plural) is unavailable** in current builds. Use `copilot plugin list`
  and `copilot skill list --json`.
- **In `preToolUse` hooks, returning `allow` bypasses the permission prompt entirely.** For a
  denylist, deny explicitly or emit nothing at all.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

[MIT](LICENSE)
