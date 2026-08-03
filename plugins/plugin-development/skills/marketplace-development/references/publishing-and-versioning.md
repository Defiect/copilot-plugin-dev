# Publishing and versioning marketplaces

## Contents

- [Release policy](#release-policy)
- [Pre-release validation](#pre-release-validation)
- [Tagging](#tagging)
- [Changelogs](#changelogs)
- [Communicating breaking changes](#communicating-breaking-changes)
- [Deprecating a plugin](#deprecating-a-plugin)
- [Semver bump table](#semver-bump-table)

## Release policy

Publish a marketplace only after a real local install succeeds. Static validation catches
schema and path errors; local install testing catches packaging, cache, and component
loading errors.

Keep release documentation at the repository level. Never put `CHANGELOG.md`, `README.md`,
`INSTALL.md`, or `QUICKSTART.md` inside a skill directory because skill directories should
stay focused on runtime instructions.

## Pre-release validation

1. **Validate the marketplace.** Run
   `scripts/validate_marketplace.py .github/plugin/marketplace.json`. Fix every error and
   review every warning.
2. **Validate each plugin.** Run the plugin-development validator for every relative
   source in the marketplace. Stop if any plugin manifest or component path fails.
3. **Install from a local path.** Run
   `copilot plugin marketplace add /absolute/path/to/repo`, then
   `copilot plugin install PLUGIN@MARKETPLACE`.
4. **Confirm components.** Run `copilot plugin list` and `copilot skill list`, then start a
   session for agents and hooks because some components only appear at runtime.
   (`copilot plugins list --kind plugin --kind skill --kind mcp --kind lsp` reports all
   kinds at once, but the plural `plugins` family is gated and unavailable in some builds.)
5. **Reinstall after edits.** If any file changes, rerun `copilot plugin install ./path`;
   installed plugin files are copied at install time.

## Tagging

Tag the repository after validation and local install testing pass:

```bash
git tag v1.2.3
git push origin v1.2.3
```

Use release tags as marketplace `ref` values for public entries. Use a full 40-character
`sha` when the release must be immutable and auditable.

## Changelogs

Write changelogs at the repository level, not inside a skill directory. Include:

- Marketplace version and release tag.
- Added, changed, deprecated, and removed plugins.
- Plugin version bumps and why each bump was chosen.
- Breaking changes with migration commands.
- Known issues and rollback instructions.

## Communicating breaking changes

State the breaking change where users will see it before installing:

1. **In release notes.** Put the migration path near the top.
2. **In marketplace metadata.** Update descriptions when a plugin's purpose changes.
3. **In plugin documentation.** Update the plugin-level README or repository docs, not a
   skill-directory changelog.
4. **In install guidance.** Tell users whether to run `copilot plugin update NAME` or
   reinstall from a specific source.

## Deprecating a plugin

1. **Mark the entry.** Add clear deprecation wording to the plugin entry `description`.
2. **Keep the source installable.** Do not break existing users while they migrate.
3. **Publish the replacement.** Add the replacement plugin entry in the same release.
4. **Announce the removal version.** Give a concrete future major version for removal.
5. **Remove on a major release.** Removing an installable plugin is a breaking marketplace
   change.

## Semver bump table

| Change type | Plugin bump | Marketplace action |
| --- | --- | --- |
| Fix a typo in marketplace metadata only | Patch marketplace metadata version | Keep plugin version unchanged |
| Fix a bug in a bundled script | Patch | Update matching marketplace entry version |
| Clarify a skill body without changing behavior | Patch | Update matching marketplace entry version |
| Improve a skill description so triggering changes | Minor | Mention trigger behavior in release notes |
| Add a new skill, agent, hook, MCP server, LSP server, or command | Minor | Update entry version and release notes |
| Add a new plugin entry | Minor marketplace version | Add install command to release notes |
| Rename or remove a skill or agent | Major | Publish migration from old `/name` or agent ID |
| Change a hook's blocking behavior | Major | Call out fail-open/fail-closed impact |
| Remove a bundled script | Major | Document replacement command or removal |
| Remove a plugin entry | Major marketplace version | Deprecate before removal whenever possible |
