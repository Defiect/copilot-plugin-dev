# Marketplace reference

## Contents

- [Manifest discovery](#manifest-discovery)
- [Top-level fields](#top-level-fields)
- [`owner`](#owner)
- [`metadata`](#metadata)
- [Plugin entry fields](#plugin-entry-fields)
- [`source` forms](#source-forms)
- [`strict`](#strict)
- [Validation expectations](#validation-expectations)

## Manifest discovery

Copilot CLI searches for the first marketplace manifest in this order:

1. `marketplace.json`
2. `.plugin/marketplace.json`
3. `.github/plugin/marketplace.json`
4. `.claude-plugin/marketplace.json`

Relative plugin sources are resolved from the marketplace repository root, not from the
manifest file's parent directory. A manifest at `.github/plugin/marketplace.json` can
therefore point at `"./plugins/example"`.

## Top-level fields

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `name` | string | Yes | — | Kebab-case marketplace identifier, max 64 characters. Dots are accepted for Open Plugin Spec plugins. This becomes the name users type after `@`. |
| `owner` | object | Yes | — | Marketplace maintainer metadata. Must contain `name`. |
| `plugins` | array | Yes | — | List of plugin entry objects. Names must be unique within the marketplace. |
| `metadata` | object | No | `{}` | Optional marketplace metadata: `description`, `version`, and `pluginRoot`. |

Example:

```json
{
  "name": "team-copilot-plugins",
  "owner": { "name": "Team Platform", "email": "platform@example.com" },
  "metadata": {
    "description": "Curated Copilot CLI plugins for Team Platform",
    "version": "1.0.0"
  },
  "plugins": []
}
```

## `owner`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | Yes | Person, team, or organization responsible for the marketplace. |
| `email` | string | No | Contact email for marketplace issues. |

Do not add arbitrary owner fields. Unknown fields are ignored by the CLI and should be
removed.

## `metadata`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `description` | string | No | Human-readable marketplace summary. |
| `version` | string | No | Marketplace catalog version. Use semver. |
| `pluginRoot` | string | No | Directory containing plugins in a monorepo. Resolve it from the repository root. |

Use `metadata.pluginRoot` to document a monorepo convention, not to replace each entry's
`source`. Entries still need explicit `source` values.

## Plugin entry fields

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `name` | string | Yes | — | Kebab-case plugin name, max 64 characters. Must be unique in the marketplace. |
| `source` | string or object | Yes | — | Relative path, GitHub source object, or URL source object. |
| `description` | string | No | From plugin metadata when browsed after install | Max 1024 characters. Include what the plugin provides, not just the name. |
| `version` | string | No | — | Semantic version. Keep it equal to `plugin.json`. |
| `author` | object | No | — | `{ "name": "...", "email": "...", "url": "..." }`; `name` is required when present. |
| `homepage` | string | No | — | Plugin homepage URL. |
| `repository` | string | No | — | Source repository URL. |
| `license` | string | No | — | SPDX identifier such as `MIT`. |
| `keywords` | string[] | No | `[]` | Search terms. |
| `category` | string | No | — | Category shown by marketplace tooling. |
| `tags` | string[] | No | `[]` | Additional labels. |
| `commands` | string or string[] | No | Plugin default | Component path override. Use only when marketplace metadata must override the plugin. |
| `agents` | string or string[] | No | Plugin default | Component path override. |
| `skills` | string or string[] | No | Plugin default | Component path override. |
| `hooks` | string or object | No | Plugin default | Hook path or inline hook configuration. |
| `mcpServers` | string or object | No | Plugin default | MCP path or inline server map activated when the plugin source does not ship one. |
| `lspServers` | string or object | No | Plugin default | LSP path or inline server map. |
| `strict` | boolean | No | `true` | Use strict schema and validation rules for marketplace installs. |

## `source` forms

### Relative path string

Use this when the plugin is in the same repository as the marketplace:

```json
{
  "name": "plugin-development",
  "version": "1.0.0",
  "source": "./plugins/plugin-development"
}
```

The path resolves from the repository root. It must point at a plugin directory containing
one of the discoverable plugin manifests:

1. `.plugin/plugin.json`
2. `plugin.json`
3. `.github/plugin/plugin.json`
4. `.claude-plugin/plugin.json`

### GitHub source object with a release tag

Use this when the plugin lives in a GitHub repository:

```json
{
  "name": "external-reviewer",
  "version": "2.4.0",
  "source": {
    "source": "github",
    "repo": "octo-org/copilot-plugins",
    "ref": "v2.4.0",
    "path": "plugins/external-reviewer"
  }
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `source` | string | Yes | Must be `"github"`. |
| `repo` | string | Yes | GitHub `OWNER/REPO`. |
| `ref` | string | No | Branch or tag. Prefer release tags for public marketplaces. |
| `path` | string | No | Plugin directory inside the repository. Omit when the plugin is at the repository root. |
| `sha` | string | No | Full 40-character commit SHA. Use for immutable installs. |

### GitHub source object pinned to a SHA

```json
{
  "name": "audited-plugin",
  "version": "1.0.1",
  "source": {
    "source": "github",
    "repo": "octo-org/audited-plugin",
    "sha": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
    "path": "."
  }
}
```

A SHA pin must use all 40 hexadecimal characters. Short SHAs are not accepted because they
are ambiguous and less auditable.

### URL source object

Use this for Git repositories that are not addressed as GitHub `OWNER/REPO` values:

```json
{
  "name": "gitlab-hosted-plugin",
  "version": "1.8.0",
  "source": {
    "source": "url",
    "url": "https://gitlab.com/octo-org/copilot-plugin.git",
    "ref": "v1.8.0",
    "path": "."
  }
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `source` | string | Yes | Must be `"url"`. |
| `url` | string | Yes | Git URL. |
| `ref` | string | No | Branch or tag. Prefer release tags. |
| `path` | string | No | Plugin directory inside the repository. |
| `sha` | string | No | Full 40-character commit SHA. |

## `strict`

`strict` defaults to `true`. Leave it enabled for marketplaces so schema violations fail
before users install a plugin. Set `strict: false` only for a legacy entry that cannot be
made conformant, and explain the exception in the repository release notes.

## Validation expectations

Run:

```bash
scripts/validate_marketplace.py .github/plugin/marketplace.json
```

Treat these as release blockers:

| Check | Severity |
| --- | --- |
| Missing `name`, `owner`, `owner.name`, or `plugins` | Error |
| Duplicate plugin entry names | Error |
| Plugin name is not kebab-case | Error |
| Relative `source` does not resolve to a directory | Error |
| Relative `source` directory has no discoverable `plugin.json` | Error |
| GitHub or URL source has a short or non-hex `sha` | Error |
| Unknown fields | Warning |
| Missing entry `version` or `description` | Warning |
| Entry `version` or `description` disagrees with referenced `plugin.json` | Warning |
| `ref` is `main` or `master` | Warning |
