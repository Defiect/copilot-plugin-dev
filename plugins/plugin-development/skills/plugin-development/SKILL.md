---
name: plugin-development
description: Builds, structures, and ships GitHub Copilot CLI plugins — the manifest, and the skills, agents, commands, hooks, MCP servers, and LSP servers a plugin can contain. Use when the user asks to "create a plugin", "build a Copilot plugin", "add a skill to my plugin", "what goes in plugin.json", "package these agents", or mentions a plugin manifest or plugin directory layout. Delegates deep work on individual component types to the sibling skills for skills, agents, hooks, MCP, LSP, marketplaces, and testing.
license: MIT
---

# Plugin development

A Copilot CLI plugin is a directory with a manifest and one or more components. Everything
else — the marketplace entry, the install command, the version tag — is packaging around
that directory.

This skill owns the plugin as a whole: deciding which components a plugin needs, writing
the manifest, laying out the directory, and getting it installed and verified. Deep work on
a single component type belongs to a sibling skill; this skill hands off to them.

## Core principles

1. **Only `name` is required.** Everything else in `plugin.json` is optional and defaulted.
   A plugin that adds keys it does not need is harder to read, not more complete.
2. **Convention over configuration.** `agents/` and `skills/` are found automatically. Add
   an explicit path only when the layout deviates from the default.
3. **Every component costs context in every session.** A skill's description, an agent's
   description, and every MCP tool schema are loaded for every user, every time. A plugin
   with four excellent skills beats one with twelve mediocre ones.
4. **Plugins load last.** Project and personal skills shadow plugin skills by `name`, so
   assume a plugin skill can be silently overridden and name it distinctly. Plugin agents
   are exempt: they are namespaced as `<plugin-name>:<agent-id>`.
5. **Installation copies files.** Editing the source directory does nothing to an installed
   plugin. The edit → reinstall → verify loop is mandatory, not optional.

## Guided creation workflow

1. **State the problem in one sentence.** "Copilot does not know how this repository does
   database migrations." If the sentence needs an "and", the plugin is probably two plugins.
2. **Choose the components.** Use the [decision table](#choosing-components). Choose the
   fewest that solve the problem. Justify each one out loud.
3. **Scaffold the directory.**

   ```bash
   scripts/init_plugin.py --name my-plugin --description "..." --author "Name"
   ```

   Pass `--with-skill`, `--with-agent`, `--with-hooks`, `--with-mcp`, or `--with-lsp` to
   generate the matching component stubs and manifest fields.
4. **Write the manifest.** See [references/manifest-reference.md](references/manifest-reference.md)
   for every field. Keep it minimal.
5. **Build each component** by delegating to the sibling skill that owns it. Do not write a
   `SKILL.md`, an `.agent.md`, a `hooks.json`, an MCP config, or an LSP config from memory —
   each has non-obvious rules that its own skill documents.
6. **Validate statically.**

   ```bash
   scripts/validate_plugin.py . --warnings-as-errors
   ```

   Resolve every error. Resolve every warning or write down why it is acceptable.
7. **Load and verify at runtime.**

   ```bash
   copilot --plugin-dir ./path/to/plugin
   ```

   This loads the plugin from your working tree with no copy and no cache. Inside the
   session, run `/skills list` and `/agent` and confirm every component appears. A
   component that validates but does not load is a failure.
8. **Trigger-test.** Start a session and phrase a request the way a real user would.
   Confirm the right component activates. If a skill does not trigger, fix its
   `description` — not its body. The `plugin-testing` skill covers this in depth.

## Choosing components

| Need | Component | Owning skill |
| --- | --- | --- |
| Teach Copilot a procedure, convention, or domain it does not know | Skill | `skill-development` |
| Delegate independent work to a separate context window with restricted tools | Agent | `agent-development` |
| Run deterministic code on a lifecycle event, or block an action | Hook | `hook-development` |
| Give Copilot access to an external system's tools and data | MCP server | `mcp-integration` |
| Give Copilot real code intelligence for a language | LSP server | `lsp-integration` |
| Offer a single-file prompt, or port a `.claude/commands/` set | Command | [references/commands-and-extensions.md](references/commands-and-extensions.md) |
| Add tools or slash commands backed by Node.js code | Extension | [references/commands-and-extensions.md](references/commands-and-extensions.md) |
| Distribute the plugin to other people | Marketplace | `marketplace-development` |

If two components could solve the problem, prefer the one that costs less context and less
privilege — usually a skill over an agent, and an agent over a hook.

## Directory anatomy

```text
my-plugin/
├── plugin.json              # the manifest — the only required file
├── README.md                # for humans browsing the repo, not for Copilot
├── LICENSE
├── skills/
│   └── my-skill/
│       ├── SKILL.md
│       ├── references/
│       ├── examples/
│       └── scripts/
├── agents/
│   └── my-agent.agent.md
├── commands/
│   └── my-command.md
├── hooks/
│   └── hooks.json
├── .mcp.json
└── lsp.json
```

Only `plugin.json` must exist. Directories that are empty should be deleted, not committed.

## Manifest essentials

```json
{
  "name": "my-plugin",
  "description": "One sentence a person reads in a marketplace listing.",
  "version": "1.0.0",
  "author": { "name": "Your Name" },
  "license": "MIT"
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `name` | Yes | kebab-case, 64 characters maximum. |
| `description` | No | 1024 characters maximum. |
| `version` | No | Semver. Required in practice for anything distributed. |
| `author` | No | Object; `name` is required inside it. |
| `agents`, `skills`, `commands` | No | Path or list of paths. Defaults: `agents/`, `skills/`. |
| `hooks`, `mcpServers`, `lspServers` | No | A path string, or the config inline as an object. |
| `extensions` | No | Node.js CLI extension directories. String, list, or `{ "paths": [...], "exclusive": true }`. |

The manifest is looked up in this order, first found wins: `.plugin/plugin.json`,
`plugin.json`, `.github/plugin/plugin.json`, `.claude-plugin/plugin.json`. Use plain
`plugin.json` at the plugin root unless there is a reason not to.

Full field-by-field detail, including every accepted shape for the component fields, is in
[references/manifest-reference.md](references/manifest-reference.md).

## Default component locations

When a manifest field is omitted, these paths are searched automatically:

| Component | Default location |
| --- | --- |
| Agents | `agents/*.agent.md` |
| Skills | `skills/<name>/SKILL.md` |
| Hooks | `hooks.json`, then `hooks/hooks.json` |
| MCP servers | `.mcp.json`, then `.github/mcp.json` |
| LSP servers | `lsp.json`, `.github/lsp.json`, or `lsp-config/servers.json` |
| Commands | No default — the `commands` field must be declared |

Declaring a field that points at the default location is redundant. Declare it when the
layout differs, or when being explicit prevents a future reader from guessing.

## Variables available to components

| Variable | Expands to | Use it for |
| --- | --- | --- |
| `${PLUGIN_ROOT}` | The installed plugin directory | Paths to bundled scripts in hooks, MCP, and LSP configs |
| `${COPILOT_PLUGIN_DATA}` | A writable per-plugin data directory | Caches, logs, state. Alias: `${CLAUDE_PLUGIN_DATA}` |

Never hardcode an absolute path. The install directory is not the source directory.

## Loading order and precedence

Three component families resolve conflicts differently, and plugins sit near the end of
every source list.

| Component | Conflict key | Rule | Practical consequence for a plugin |
| --- | --- | --- | --- |
| Skills | Frontmatter `name` | First found wins | Project skills, then personal skills, shadow the plugin's |
| Agents | Filename-derived ID | Namespaced per plugin | Plugin agents resolve as `<plugin-name>:<agent-id>` and never collide |
| MCP servers | Server key | **Last wins** | The plugin overrides the user's own server of the same name |
| Built-in tools and agents | — | Never overridable | — |

Two traps live in that table. Skills and MCP servers resolve in opposite directions. And
agents load personal-first while skills load project-first, so the two do not follow the
same rule. See [references/loading-and-precedence.md](references/loading-and-precedence.md)
for the full source lists and worked examples of each.

## Anti-patterns

| | Pattern |
| --- | --- |
| ❌ | Declaring `"skills": "skills/"` and `"agents": "agents/"` when those are the defaults, in a manifest that has nothing else to say |
| ✅ | Omitting them, or declaring them because the plugin also loads a second skills directory |
| ❌ | Shipping a `hooks.json` so the plugin can "log usage" — it then runs in every session of every user who installs it |
| ✅ | Shipping hook *examples* users copy into their own project, and reserving plugin hooks for behavior the plugin exists to provide |
| ❌ | One plugin containing a Kubernetes skill, a CSS skill, and a tax-calculation agent |
| ✅ | One plugin per coherent domain, so users can install what they need |
| ❌ | `"name": "My Plugin"` |
| ✅ | `"name": "my-plugin"` — kebab-case, no spaces, no capitals |
| ❌ | An absolute path such as `/home/me/plugin/scripts/hook.sh` in a hook config |
| ✅ | `${PLUGIN_ROOT}/scripts/hook.sh` |
| ❌ | A `README.md` inside a skill directory explaining the skill |
| ✅ | One `README.md` at the plugin root for humans; `SKILL.md` is the only document Copilot reads |
| ❌ | Editing a skill in an *installed* plugin and expecting a new session to pick it up |
| ✅ | Iterating with `copilot --plugin-dir ./path`, which reads the working tree directly |
| ❌ | An MCP server keyed `github` that silently overrides the user's own `github` server |
| ✅ | A distinctly named key such as `acme-github-internal` |
| ❌ | Committing an empty `commands/` or `hooks/` directory |
| ✅ | Deleting directories the plugin does not use |

## Validation

```bash
# Whole-plugin structural validation
scripts/validate_plugin.py path/to/plugin --warnings-as-errors

# Machine-readable, for CI
scripts/validate_plugin.py path/to/plugin --json
```

Exit codes: `0` clean, `1` errors found, `2` usage error. `validate_plugin.py` checks the
manifest, every skill, every agent, hooks, MCP, LSP, commands, extensions, bundled-file
links, script permissions, and hardcoded credentials. It is the gate the CI workflow in this
repository runs.

Per-component validators live in the sibling skills and go deeper than `validate_plugin.py`
does. Run both.

## Iterate, then verify

Develop against your working tree, and install only to check the release artifact.

```bash
# Edit a file, then start a session that reads the source directory directly.
copilot --plugin-dir ./plugins/my-plugin

# Inside the session:
#   /skills list   confirm skills loaded
#   /agent         confirm agents loaded as my-plugin:<agent-id>
# Then trigger-test with realistic phrasing.
```

Nothing is copied, so there is no reinstall step and no stale cache. Note that
`copilot skill list` does not report `--plugin-dir` skills even though they load correctly —
check `/skills list` from inside the session instead.

Once before release, exercise the real installed layout:

```bash
copilot plugin install ./plugins/my-plugin   # deprecated for local paths, but still the
copilot plugin list                          # only way to test ${PLUGIN_ROOT} resolution

# The durable equivalent, which keeps working when direct installs are removed:
copilot plugin marketplace add /absolute/path/to/repo
copilot plugin install my-plugin@my-marketplace
```

Reinstall after **every** edit if you are testing this way — the install copies files, and a
fresh session alone will not pick up changes.

```bash
copilot plugin uninstall my-plugin
```

That reinstall step exists because plugin components are copied into the Copilot config
directory at install time. Reloading skills inside a running session re-reads the
*installed* copy, not your working tree. `--plugin-dir` sidesteps the whole problem, which
is why it is the loop to develop in.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `plugin install` reports no manifest | Manifest is not in a discovered location | Move it to `plugin.json` at the plugin root |
| Plugin installs, no skills appear | Skills are not at `skills/<name>/SKILL.md`, or the file is not named exactly `SKILL.md` | Fix the layout, or set the `skills` field |
| Skill appears but never activates | The `description` does not match how users phrase the request | Rewrite the description with concrete trigger phrases |
| Agent missing from `/agent` | Filename does not end in `.agent.md`, or `user-invocable: false` | Rename the file, or check frontmatter |
| Component still shows old content | Stale installed copy | Re-run `copilot plugin install ./path` |
| A component works for you, not for others | Absolute path, or a dependency assumed to be installed | Use `${PLUGIN_ROOT}`; guard external binaries |
| Two plugins fight over a name | First-found-wins for skills; MCP and LSP keys are last-wins | Rename with a distinguishing prefix |
| Hook fires for everyone unexpectedly | Plugin hooks are global to the session | Reconsider whether it should be a plugin hook at all |

## Reference material

- [references/manifest-reference.md](references/manifest-reference.md) — every `plugin.json`
  field, type, default, and accepted shape. Read before writing a manifest by hand.
- [references/component-patterns.md](references/component-patterns.md) — how the six
  component types combine, with recipes for common plugin shapes.
- [references/loading-and-precedence.md](references/loading-and-precedence.md) — the full
  loading pipeline and worked conflict examples. Read when a component is being shadowed.
- [references/commands-and-extensions.md](references/commands-and-extensions.md) — the
  `commands` and `extensions` manifest fields, which the other skills do not cover.
- [examples/minimal-plugin.md](examples/minimal-plugin.md) — one skill, five-line manifest.
- [examples/standard-plugin.md](examples/standard-plugin.md) — skills plus an agent plus a
  marketplace entry.
- [examples/advanced-plugin.md](examples/advanced-plugin.md) — every component type in one
  plugin, with the reasoning for each.

## Related skills

| Task | Skill |
| --- | --- |
| Writing a `SKILL.md` | `skill-development` |
| Writing an `.agent.md` | `agent-development` |
| Writing `hooks.json` | `hook-development` |
| Bundling an MCP server | `mcp-integration` |
| Bundling a language server | `lsp-integration` |
| Publishing and versioning | `marketplace-development` |
| Verifying and debugging | `plugin-testing` |
