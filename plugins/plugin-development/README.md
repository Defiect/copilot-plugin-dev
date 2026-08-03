# plugin-development

Build, validate, test, and publish GitHub Copilot CLI plugins.

This plugin makes an agent self-sufficient at plugin authoring. It documents the complete authoring surface — manifests, skills, custom agents, hooks, MCP servers, LSP servers, and marketplaces — and ships executable scaffolding and validation tooling for each.

## Install

```bash
copilot plugin marketplace add Defiect/copilot-plugin-dev
copilot plugin install plugin-development
```

Or run it straight from a local checkout without installing:

```bash
copilot --plugin-dir ./plugins/plugin-development
```

## Usage

The skills activate automatically from natural requests. No commands to memorize:

- *"Create a Copilot CLI plugin that bundles an MCP server"* → `plugin-development` + `mcp-integration`
- *"Write a skill for our deployment runbook"* → `skill-development`
- *"Add a hook that blocks dangerous shell commands"* → `hook-development`
- *"Review my plugin before I publish it"* → `plugin-validator` agent
- *"Why isn't my skill loading?"* → `plugin-testing`

## Skills

| Skill | Covers |
| --- | --- |
| `plugin-development` | `plugin.json` fields, manifest discovery order, directory layout, component wiring, `${PLUGIN_ROOT}` |
| `skill-development` | `SKILL.md` frontmatter, description triggers, progressive disclosure, reference and script layout |
| `agent-development` | `.agent.md` frontmatter, tool allowlists, model selection, delegation boundaries, the 30,000-char body cap |
| `hook-development` | Every hook event, `hooks.json` structure, entry types, matcher anchoring, payload and output schemas, exit-code and timeout semantics |
| `mcp-integration` | Server types and transports, `mcpServers` config, environment and secret handling, bundled server paths |
| `lsp-integration` | `lspServers` config, `fileExtensions` object maps, bundled launcher wrappers |
| `marketplace-development` | `marketplace.json` schema, plugin entries, source forms, versioning and release flow |
| `plugin-testing` | Local install loop, install-time caching, precedence and first-found-wins debugging, smoke tests |

Each skill keeps `SKILL.md` short and moves detail into `references/`, with runnable `examples/` and `scripts/`.

## Agents

| Agent | Purpose |
| --- | --- |
| `plugin-validator` | Reviews a whole plugin for spec conformance and reports errors, warnings, and notes |
| `skill-reviewer` | Deep quality review of one `SKILL.md`, with a graded verdict |
| `agent-architect` | Designs and writes a custom agent from a described need |

## Scripts

All scripts run with `python3` (3.10+) and require no third-party packages. PyYAML is used when present; otherwise a built-in fallback frontmatter parser is used. Every script supports `--help`.

**Scaffolding**

| Script | Purpose |
| --- | --- |
| `plugin-development/scripts/init_plugin.py` | Generate a complete plugin skeleton |
| `skill-development/scripts/init_skill.py` | Generate a `SKILL.md` skeleton |
| `marketplace-development/scripts/init_marketplace.py` | Generate a marketplace repository |

**Validation**

| Script | Purpose |
| --- | --- |
| `plugin-development/scripts/validate_plugin.py` | Whole-plugin conformance check |
| `skill-development/scripts/validate_skill.py` | Skill quality and conformance, with graded verdicts |
| `agent-development/scripts/validate_agent.py` | Agent frontmatter and body checks |
| `hook-development/scripts/validate_hooks.py` | `hooks.json` schema, events, and matchers |
| `mcp-integration/scripts/validate_mcp.py` | MCP server configuration |
| `lsp-integration/scripts/validate_lsp.py` | LSP server configuration |
| `marketplace-development/scripts/validate_marketplace.py` | `marketplace.json` and referenced plugins |

**Testing and maintenance**

| Script | Purpose |
| --- | --- |
| `hook-development/scripts/test_hook.py` | Feed a synthetic payload to a hook and explain its control decision |
| `plugin-testing/scripts/check_precedence.py` | Show which component wins when names collide |
| `plugin-testing/scripts/smoke_test_plugin.sh` | End-to-end structural smoke test |
| `marketplace-development/scripts/add_plugin.py` | Add a plugin entry to a marketplace |
| `marketplace-development/scripts/bump_version.py` | Bump a plugin version and sync marketplace entries |

Example, validating a plugin in CI:

```bash
python3 skills/plugin-development/scripts/validate_plugin.py ./my-plugin --warnings-as-errors
```

## Development loop

Develop with `--plugin-dir`, which loads the plugin from the working tree with no copy and no cache:

```bash
copilot --plugin-dir ./plugins/plugin-development
```

Inside the session, `/skills list` and `/agent` show what loaded. (`copilot skill list` does not report `--plugin-dir` skills, though they work.)

If you install instead, Copilot CLI caches plugin contents at install time, so **reinstall after every edit** — reloading skills alone will not pick up manifest or new-file changes:

```bash
copilot plugin install ./plugins/plugin-development
copilot skill list
```

Agents are namespaced by plugin, so invoke them with the prefix:

```bash
copilot --agent plugin-development:plugin-validator -p "Review ./my-plugin"
```

## License

[MIT](LICENSE)
