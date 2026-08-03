---
name: marketplace-development
description: Create, validate, version, and publish GitHub Copilot CLI plugin marketplaces. Use when the user asks to "create a plugin marketplace", "publish my plugin", "marketplace.json", "how do users install my plugin", or "add my plugin to a marketplace". Does not cover authoring the plugin itself, which is handled by the plugin-development skill.
license: MIT
---

# Marketplace development

A marketplace is a Git repository, Git URL, or local directory containing a
`marketplace.json` file that lists installable Copilot CLI plugins. Users add the
marketplace, then install a plugin by name:

```bash
copilot plugin marketplace add <repo-or-path>
copilot plugin install <plugin>@<marketplace>
```

Author the marketplace so every entry is reproducible, versioned, and testable from a
fresh checkout.

## Manifest location

Copilot discovers the marketplace manifest in this order:

1. `marketplace.json`
2. `.plugin/marketplace.json`
3. `.github/plugin/marketplace.json`
4. `.claude-plugin/marketplace.json`

Prefer `.github/plugin/marketplace.json`; it keeps plugin metadata with other GitHub
configuration while avoiding a root-level file in repositories that already contain many
project files.

## Publishing workflow

1. **Choose the layout.** Pick one of the three layouts below and keep it consistent for
   every plugin entry.
2. **Write `marketplace.json`.** Include `name`, `owner.name`, and a `plugins` array.
   Use [references/marketplace-reference.md](references/marketplace-reference.md) when
   checking field names and source forms.
3. **Add plugin entries.** Give each entry a kebab-case `name`, `description`, `version`,
   and `source`. Keep `version` synchronized with the plugin's `plugin.json`.
4. **Decide the source strategy.** Use a relative path for plugins in the same repository.
   Use a GitHub source object for external repositories. Pin production entries to a tag
   or a full 40-character `sha`.
5. **Validate.** Run `scripts/validate_marketplace.py PATH`. Fix errors before continuing;
   review warnings before release.
6. **Test locally.** Run `copilot plugin marketplace add /absolute/path/to/repo`, then
   `copilot plugin install <plugin>@<marketplace-name>`. If this fails, fix the manifest
   before publishing.
7. **Tag a release.** Tag the repository after validation passes. Follow
   [references/publishing-and-versioning.md](references/publishing-and-versioning.md)
   for release notes and breaking-change communication.
8. **Publish.** Push the manifest, plugin directories, and tag to the repository users
   will add.
9. **Tell users the install command.** Publish both commands exactly:
   `copilot plugin marketplace add OWNER/REPO` and
   `copilot plugin install PLUGIN@MARKETPLACE`.

## Repository layouts

| Layout | Directory shape | `source` value shape |
| --- | --- | --- |
| Single plugin at root | The repository root is the plugin and also contains the marketplace manifest | `"."` or `"./"` |
| Monorepo with `plugins/` | The marketplace lists plugin directories under `plugins/`; this repository uses this layout | `"./plugins/plugin-name"` |
| Index-only marketplace | The marketplace repository contains only `marketplace.json` and points at external plugin repositories | `{ "source": "github", "repo": "owner/repo", "ref": "v1.2.3", "path": "plugins/plugin-name" }` |

For complete trees and examples, read
[references/repository-layouts.md](references/repository-layouts.md).

## The `source` field

Use one canonical source strategy per marketplace entry:

| Form | Use it for | Example |
| --- | --- | --- |
| Relative path string | Plugins stored in the same marketplace repository | `"./plugins/plugin-development"` |
| GitHub object | Plugins stored in another GitHub repository or subdirectory | `{ "source": "github", "repo": "owner/repo", "ref": "v1.2.3", "path": "plugins/name" }` |
| URL object | Plugins stored in a non-GitHub Git repository | `{ "source": "url", "url": "https://gitlab.com/owner/repo.git", "ref": "v1.2.3", "path": "plugins/name" }` |

Choose the pin deliberately:

| Pin | Trade-off |
| --- | --- |
| `ref: "main"` | Always latest, but moves under users and makes installs unreproducible. Avoid in production marketplaces. |
| `ref: "v1.2.3"` | Stable release tag. Prefer this for public marketplaces. |
| `sha: "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3"` | Immutable and auditable. Use this for high-assurance installs. The value must be the full 40-character commit SHA. |

## Versioning policy

Use semantic versioning for every plugin and marketplace entry. Keep `version` in the
plugin's `plugin.json` and the matching marketplace entry identical.

| Change | Bump |
| --- | --- |
| Remove or rename a skill or agent | Major |
| Change a hook from advisory to blocking, or otherwise change blocking behavior | Major |
| Remove a bundled script | Major |
| Add a skill, agent, hook, MCP server, LSP server, or command | Minor |
| Improve instructions, fix a script bug, or clarify descriptions without breaking callers | Patch |

## Strict entries

`strict` defaults to `true` on plugin entries. Leave it true for marketplace distribution:
strict entries must conform to the schema and validation rules, which catches mistakes
before users install them. Use `strict: false` only for legacy or direct-install
compatibility, and document the reason at the repository level.

## Anti-patterns

| ❌ Avoid | ✅ Prefer |
| --- | --- |
| Omit `version` from a public entry | Set `version` and match the plugin's `plugin.json` |
| Use `ref: "main"` for a production marketplace | Pin to `ref: "v1.2.3"` or a full 40-character `sha` |
| Repeat the name as the description: `"Spark plugin"` | State the concrete capability users get |
| Omit `owner` or `owner.name` | Set `owner.name` so users know who maintains the catalog |
| Point `source` at a path that does not exist | Validate relative paths from the repository root |
| Use a short SHA | Use the full 40-character commit SHA |
| Commit without testing `marketplace add` locally | Add the local path and install at least one plugin before publishing |

## Publishing checklist

- [ ] `marketplace.json` lives at `.github/plugin/marketplace.json` unless the repository
      has a documented reason to use another discovery location.
- [ ] Every plugin entry has `name`, `description`, `version`, and `source`.
- [ ] Every relative `source` resolves to a plugin directory containing a discoverable
      `plugin.json`.
- [ ] Production external sources use a release tag or full 40-character `sha`.
- [ ] `scripts/validate_marketplace.py .github/plugin/marketplace.json` exits 0.
- [ ] `copilot plugin marketplace add /absolute/path/to/repo` succeeds locally.
- [ ] `copilot plugin install PLUGIN@MARKETPLACE` succeeds locally.
- [ ] The repository tag and changelog describe the release at the repository level.

Tell users:

```bash
copilot plugin marketplace add OWNER/REPO
copilot plugin install PLUGIN@MARKETPLACE
```

For a local pilot, tell users:

```bash
copilot plugin marketplace add /absolute/path/to/marketplace
copilot plugin install PLUGIN@MARKETPLACE
```

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `marketplace add` fails | The manifest is missing, invalid JSON, or not in a discovered location | Run `scripts/validate_marketplace.py REPO` and move the file to `.github/plugin/marketplace.json` |
| Plugin not found in marketplace | The user installed from a different marketplace name or the catalog cache is stale | Run `copilot plugin marketplace list`, then `copilot plugin marketplace update MARKETPLACE` |
| Install succeeds but components are missing | The plugin's `plugin.json` points to wrong component paths | Validate the plugin itself with the plugin-development validator |
| Updates are not picked up | Plugin components are copied at install time | Re-run `copilot plugin install ./path`; `/skills reload` is not enough for installed plugin edits |
| Relative source works locally but not after publish | The path was relative to the manifest file instead of the repository root | Resolve paths from the repository root and revalidate |
| A pinned source does not update | A `sha` is immutable by design | Publish a new marketplace entry version pointing at a new full SHA |

## Bundled files

- [references/marketplace-reference.md](references/marketplace-reference.md) — exhaustive
  schema and source forms.
- [references/publishing-and-versioning.md](references/publishing-and-versioning.md) —
  release process, tagging, deprecation, and semver policy.
- [references/repository-layouts.md](references/repository-layouts.md) — directory trees,
  matching manifests, and layout trade-offs.
- [examples/single-plugin-marketplace.json](examples/single-plugin-marketplace.json) —
  root-plugin marketplace example.
- [examples/monorepo-marketplace.json](examples/monorepo-marketplace.json) — monorepo
  marketplace example with `metadata.pluginRoot`.
- [examples/external-sources-marketplace.json](examples/external-sources-marketplace.json)
  — external GitHub sources with tag and SHA pins.
- [scripts/validate_marketplace.py](scripts/validate_marketplace.py) — validate a
  marketplace manifest or repository root.
- [scripts/init_marketplace.py](scripts/init_marketplace.py) — scaffold a marketplace
  repository.
- [scripts/add_plugin.py](scripts/add_plugin.py) — add or update a marketplace entry from
  a plugin manifest.
- [scripts/bump_version.py](scripts/bump_version.py) — bump a plugin version and matching
  marketplace entries.
