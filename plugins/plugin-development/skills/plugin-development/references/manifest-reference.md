# `plugin.json` reference

Every field the Copilot CLI reads from a plugin manifest, with its type, whether it is
required, its default, and its behavior.

## Contents

- [Manifest location](#manifest-location)
- [Identity fields](#identity-fields)
- [Discovery fields](#discovery-fields)
- [Component fields](#component-fields)
- [Open Plugin Spec mode](#open-plugin-spec-mode)
- [Variable expansion](#variable-expansion)
- [Complete examples](#complete-examples)
- [Validation rules](#validation-rules)

## Manifest location

The CLI looks for the manifest in this order and uses the first one it finds:

1. `.plugin/plugin.json`
2. `plugin.json`
3. `.github/plugin/plugin.json`
4. `.claude-plugin/plugin.json`

`plugin.json` at the plugin root is the recommended location. `.claude-plugin/plugin.json`
exists so that plugins written for Claude Code load without modification; do not choose it
for a new Copilot plugin.

If more than one location contains a manifest, the later ones are ignored entirely — they
are not merged.

## Identity fields

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `name` | string | **Yes** | — | kebab-case identifier, 64 characters maximum. Lowercase letters, digits, and hyphens. Dots are rejected unless the manifest is in Open Plugin Spec mode. This is the name users type in `copilot plugin install`. |
| `description` | string | No | — | 1024 characters maximum. Shown in marketplace listings and `copilot plugin list`. Write it for a human deciding whether to install, not for a model. |
| `version` | string | No | — | Semantic version, `MAJOR.MINOR.PATCH`. Optional to the CLI, mandatory in practice for anything you distribute. |
| `author` | object | No | — | `{ "name": "...", "email": "...", "url": "..." }`. `name` is required *inside* the object if the object is present. |
| `homepage` | string | No | — | URL to documentation. |
| `repository` | string | No | — | URL to source. |
| `license` | string | No | — | SPDX identifier, for example `MIT`, `Apache-2.0`. |
| `keywords` | string[] | No | `[]` | Search terms for marketplace discovery. |
| `category` | string | No | — | A single grouping label. |
| `tags` | string[] | No | `[]` | Additional labels. |
| `$schema` | string | No | — | See [Open Plugin Spec mode](#open-plugin-spec-mode). |

### `name` rules in detail

| | Value |
| --- | --- |
| ✅ | `terraform-workflows` |
| ✅ | `acme-internal-tooling` |
| ❌ | `Terraform Workflows` — spaces and capitals |
| ❌ | `terraform_workflows` — underscores |
| ❌ | `acme.terraform` — dots, unless in Open Plugin Spec mode |
| ❌ | A 70-character name — over the 64-character limit |

### `description` rules in detail

The plugin description is read by people, unlike a skill description which is read by the
model. Optimize for a marketplace listing line.

| | Value |
| --- | --- |
| ❌ | `Terraform plugin` — says nothing the name did not |
| ❌ | `Use when the user asks about Terraform...` — that is skill-description phrasing |
| ✅ | `Terraform review, plan analysis, and module scaffolding conventions for Acme infrastructure repositories.` |

## Discovery fields

None. There is no `enabled`, `priority`, or `order` field. Load order is determined by
scope (built-in, project, personal, plugin) and cannot be influenced from the manifest.

## Component fields

Each component field is optional. When omitted, the default location is searched.

| Field | Accepted types | Default location | Notes |
| --- | --- | --- | --- |
| `skills` | string \| string[] | `skills/` | Directory or directories containing `<name>/SKILL.md`. |
| `agents` | string \| string[] | `agents/` | Directory or directories containing `*.agent.md`. |
| `commands` | string \| string[] | — | Directory or directories containing command files (single-file `.md` skills). |
| `hooks` | string \| object | `hooks.json`, then `hooks/hooks.json` | A path to a hooks JSON file, or the hooks configuration inline. |
| `mcpServers` | string \| object | `.mcp.json`, then `.github/mcp.json` | A path to an MCP JSON file, or an inline map of server name to configuration. |
| `lspServers` | string \| object | `lsp.json`, `.github/lsp.json`, `lsp-config/servers.json` | A path to an LSP JSON file, or an inline map. |
| `extensions` | string \| string[] \| object | — | Directories containing Node.js CLI extensions. Object form: `{ "paths": [...], "exclusive": bool }`. |

### Path form versus inline form

Both of these are valid and equivalent:

```json
{
  "name": "my-plugin",
  "mcpServers": ".mcp.json"
}
```

```json
{
  "name": "my-plugin",
  "mcpServers": {
    "acme-issues": {
      "type": "stdio",
      "command": "${PLUGIN_ROOT}/bin/issues-server",
      "args": ["--stdio"]
    }
  }
}
```

Prefer the path form once a configuration exceeds a handful of lines. A manifest that is
mostly MCP configuration is hard to scan for the fields that identify the plugin.

### Multiple paths

```json
{
  "name": "my-plugin",
  "skills": ["skills/", "vendor/shared-skills/"]
}
```

Order matters only in that duplicate skill `name` values resolve first-found-wins within
the plugin.

### `extensions`

```json
{
  "extensions": {
    "paths": ["extensions/"],
    "exclusive": true
  }
}
```

Each listed directory holds one subdirectory per extension, and each of those must contain
an `extension.mjs`, `extension.cjs`, or `extension.js` entry file. Extensions are
experimental and load only when the user has enabled experimental features.

`exclusive: true` suppresses the CLI's **built-in** extensions — a user-visible change that
should be documented in the plugin README. See
[commands-and-extensions.md](commands-and-extensions.md) for the full model.

## Open Plugin Spec mode

Setting `$schema` to the canonical Agent Plugins (Open Plugin Spec) v1.0.0 schema URL,
`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`, puts the manifest into Open
Plugin Spec mode, which is the cross-vendor plugin format. Spec semantics apply *additively*
on top of normal plugin loading. In that mode the `name` field accepts dots, which the spec
uses for reverse-DNS style identifiers.

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "org.acme.terraform",
  "version": "1.0.0"
}
```

Use this only if the plugin is intended to be consumed by more than one agent harness. For
a Copilot-only plugin it adds an identifier convention with no benefit. Note also that
`extensions` carries a different, currently unspecified meaning in this mode — do not
combine the two.

## Variable expansion

| Variable | Expands to | Valid in |
| --- | --- | --- |
| `${PLUGIN_ROOT}` | Absolute path of the *installed* plugin directory | Hook commands, MCP configurations, LSP configurations |
| `${COPILOT_PLUGIN_DATA}` | A writable per-plugin data directory | The same places |
| `${CLAUDE_PLUGIN_DATA}` | Alias for `${COPILOT_PLUGIN_DATA}` | Compatibility only |

`${PLUGIN_ROOT}` is the installed location, which is inside the Copilot configuration
directory — not the repository you developed in. Any path that must survive installation
has to go through it.

| | Value |
| --- | --- |
| ❌ | `"command": "/home/sean/dev/my-plugin/bin/server"` |
| ❌ | `"command": "./bin/server"` — relative to an unspecified working directory |
| ✅ | `"command": "${PLUGIN_ROOT}/bin/server"` |

## Complete examples

### Minimal

```json
{
  "name": "acme-conventions"
}
```

Valid. Loads `skills/` and `agents/` if present.

### Typical distributed plugin

```json
{
  "name": "terraform-workflows",
  "description": "Terraform review, plan analysis, and module scaffolding conventions for Acme infrastructure repositories.",
  "version": "2.1.0",
  "author": {
    "name": "Acme Platform Team",
    "email": "platform@acme.example",
    "url": "https://acme.example/platform"
  },
  "homepage": "https://github.com/acme/terraform-workflows",
  "repository": "https://github.com/acme/terraform-workflows",
  "license": "Apache-2.0",
  "category": "infrastructure",
  "keywords": ["terraform", "iac", "aws", "review"]
}
```

### Every component declared explicitly

```json
{
  "name": "acme-platform",
  "description": "Platform engineering tooling for Acme services.",
  "version": "3.0.0",
  "author": { "name": "Acme Platform Team" },
  "license": "MIT",
  "skills": ["skills/"],
  "agents": ["agents/"],
  "commands": ["commands/"],
  "hooks": "hooks/hooks.json",
  "mcpServers": ".mcp.json",
  "lspServers": "lsp.json",
  "extensions": { "paths": ["extensions/"], "exclusive": false }
}
```

## Validation rules

`validate_plugin.py` enforces the following. Errors block; warnings should be resolved or
justified.

| Severity | Rule |
| --- | --- |
| Error | Manifest is missing, unparseable, or not a JSON object |
| Error | `name` missing, empty, over 64 characters, or not kebab-case (outside Open Plugin Spec mode) |
| Error | `author` present but not an object, or missing `author.name` |
| Error | A component path declared in the manifest does not exist on disk |
| Error | `hooks`, `mcpServers`, or `lspServers` is neither a string nor an object |
| Error | A hardcoded credential appears anywhere in the manifest |
| Warning | `description` missing, or over 1024 characters |
| Warning | `version` missing, or not valid semver |
| Warning | `license` missing on a plugin that also declares `repository` or `homepage` |
| Warning | A component field points at the default location and is therefore redundant |
| Warning | A declared component directory exists but is empty |
| Warning | An unrecognized top-level field is present |
| Note | The plugin declares no components at all |
