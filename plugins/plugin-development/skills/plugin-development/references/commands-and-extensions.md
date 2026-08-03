# Commands and extensions

The two `plugin.json` component fields that no sibling skill covers.

## Contents

- [Commands](#commands)
- [Extensions](#extensions)
- [When to use each](#when-to-use-each)

## Commands

A command is an **alternative skill format**: a single `.md` file whose filename becomes the
command name, using a simplified frontmatter format with no `name` field. Commands are not a
separate mechanism with separate rules — they are skills with less ceremony.

Three consequences follow, and all three are easy to get wrong:

- A command **is** model-invocable by default, exactly like a skill. Set
  `disable-model-invocation: true` if you want it to fire only when the user asks.
- A command **does** support frontmatter — four fields, listed below.
- A command **loses** to a skill with the same name. Skills win; commands then follow the
  standard tier-based rule where the higher-priority source wins.

### Declaring commands

```json
{
  "name": "my-plugin",
  "commands": "commands/"
}
```

`commands` accepts a string or an array of strings, each a directory path relative to the
plugin root. Unlike `skills` and `agents`, there is no implicit default directory — a plugin
that ships commands must declare the field.

Outside plugins, commands live in `.claude/commands/` in a repository. That is the
cross-tool location Copilot CLI reads; there is no `.github/commands/` equivalent.

### Layout

```text
my-plugin/
├── plugin.json
└── commands/
    ├── audit-deps.md
    └── release-notes.md
```

The file name determines the command name: `audit-deps.md` becomes `/audit-deps`.

### Frontmatter

| Field | Type | Purpose |
| --- | --- | --- |
| `description` | string | What the command does and when to use it. Drives model invocation. |
| `argument-hint` | string | Freeform hint shown in the picker, for example `"[package] [--fix]"`. |
| `allowed-tools` | string or list | Tools pre-approved while the command runs. Same security weight as a skill's. |
| `disable-model-invocation` | boolean | `true` stops the agent from running the command on its own. |

There is no `name` field — the filename is the name. Frontmatter is optional, but omitting
`description` means the model has nothing to match on, so the command becomes effectively
user-only without saying so.

Commands really are skills under the hood, and you can see it: after installing a plugin
that ships `commands/`, the command appears in `copilot skill list --json` with
`"source": "plugin"` and the `description` you wrote in its frontmatter.

### Writing a command

The body is a prompt. It should read as an instruction to Copilot, in the imperative, with
everything the model needs to act without a follow-up question.

```markdown
---
description: Audit direct dependencies for outdated versions and known advisories. Use when the user asks to "check dependencies" or "audit deps".
argument-hint: "[manifest-path]"
disable-model-invocation: true
---

Audit this repository's direct dependencies.

For each direct dependency in the manifest:

1. Report the installed version and the latest published version.
2. Flag any dependency more than two major versions behind.
3. Flag any dependency with a known advisory, citing the advisory ID.
4. Ignore transitive dependencies unless they carry a critical advisory.

Output a Markdown table with columns: package, installed, latest, status, action.
Do not modify any file.
```

### Command, skill, or agent?

| | Command | Skill | Agent |
| --- | --- | --- | --- |
| Shape | One `.md` file | A directory with `SKILL.md` plus bundled files | One `.agent.md` file |
| Who triggers it | The user, or the model via `description` | The user, or the model via `description` | Copilot delegating, or the user |
| Can bundle scripts and references | No | Yes | No |
| Always-on context cost | The description | The description | The description |
| Where it runs | The current conversation | The current conversation | Its own context window |
| Priority on a name clash | Loses to a skill | Wins over a command | Separate namespace |

Because commands and skills differ mainly in *shape*, the real question is whether the
capability needs bundled files. A command is a single prompt file; the moment it needs a
reference document, a script, or a second example, it wants to be a skill.

**For a plugin, prefer skills.** Plugin skills get progressive disclosure, bundled scripts,
and plugin-qualified names when two plugins collide. Commands exist mostly so that
`.claude/commands/` content keeps working. Use `commands` in a plugin when you are porting
an existing set of command files, not as the default choice for new work.

### Anti-patterns

| | Pattern |
| --- | --- |
| ❌ | Duplicating a skill's body into a command "so the user can force it" |
| ✅ | One skill; skills are already user-invocable via `/name` |
| ❌ | Assuming a command only runs when the user types it |
| ✅ | Setting `disable-model-invocation: true` when that is what you actually mean |
| ❌ | Copying a `SKILL.md` frontmatter block, `name` field and all, into a command |
| ✅ | Using only the four supported keys; the filename is the name |
| ❌ | A command that asks a clarifying question as its first line |
| ✅ | A command that states its assumptions and proceeds |
| ❌ | Shipping a `commands/` directory without declaring `commands` in the manifest |
| ✅ | Declaring the field — commands have no default location |
| ❌ | Shipping a command and a skill with the same name and expecting both to be reachable |
| ✅ | Picking one; the skill always wins |

## Extensions

`extensions` points at directories containing **Copilot CLI extensions** — small Node.js
modules that run as separate processes alongside the session and connect back to it. This
field has nothing to do with bundling extra content directories.

An extension can add two things no other component type can:

- **Tools** that Copilot calls while it works.
- **Slash commands** that the user runs.

Because an extension is real code in its own process, it can hold state across a session —
for example, accumulating a running total across tool calls — which no prompt-based
component can do.

### Hard constraints

Read these before choosing `extensions` over a skill or an MCP server:

- **Experimental.** Extensions load only when experimental features are on, via the
  `--experimental` flag or `/experimental on`. A plugin that ships only an extension does
  nothing for a user who has not enabled it.
- **JavaScript only.** The entry file must be named `extension.mjs`, `extension.cjs`, or
  `extension.js`, and the CLI runs it directly with Node.js. TypeScript is not supported —
  compile to JavaScript before shipping.
- **One directory per extension.** The subdirectory name becomes the extension name.
- **It executes with the user's privileges.** Same trust bar as any script you ask someone
  to run.
- **The user can restrict or disable it.** `/extensions mode` offers *Load & Augment*
  (default), *Load Only* (extensions run, but Copilot cannot manage them), and *Disabled*.
  Changes take effect immediately, and *Disabled* persists into future sessions.

### Layout and entry point

```text
my-plugin/
├── plugin.json
└── extensions/
    └── token-counter/
        └── extension.mjs
```

The entry file connects to the session using the SDK that ships with the CLI:

```javascript
import { joinSession } from "@github/copilot-sdk/extension";

const session = await joinSession({
  name: "token-counter",
  // register tools and slash commands here
});
```

That single call is what turns a plain Node.js file into an extension: it connects the
process to the running session and registers everything the extension contributes.

Outside plugins, extensions are discovered in `.github/extensions/NAME/` (project) and
`~/.copilot/extensions/NAME/` (personal). Both use an identical structure, so an extension
directory can be moved between them, or into a plugin, unchanged.

### Declaring extensions

```json
{ "extensions": "extensions/" }
```

```json
{ "extensions": ["extensions/", "vendor/extensions/"] }
```

```json
{
  "extensions": {
    "paths": ["extensions/"],
    "exclusive": true
  }
}
```

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `paths` | string[] | — | Directories that contain extension subdirectories. |
| `exclusive` | boolean | `false` | When `true`, **suppresses the CLI's built-in extensions**. |

`exclusive: true` is a strong, user-visible change: it turns off extensions that ship with
the CLI, in every session where the plugin is enabled. Set it only when your plugin
deliberately replaces built-in behavior, and say so plainly in the plugin README.

A plugin that declares the canonical Open Plugin Spec `$schema` opts into spec semantics, in
which `extensions` carries a different meaning. The published reference notes this but does
not define it, so avoid combining `$schema` with `extensions` until it is specified.

### Extensions, skills, or MCP?

| Need | Use |
| --- | --- |
| Teach Copilot how to do something | A skill |
| Expose tools from an existing service or process | An MCP server |
| Add a tool that observes or accumulates session state in-process | An extension |
| Add a slash command that runs code rather than a prompt | An extension |

Reach for an extension last. It is experimental, JavaScript-only, off by default, and runs
arbitrary code — an MCP server covers most "add a tool" cases with a stable, cross-client
contract.

### Anti-patterns

| | Pattern |
| --- | --- |
| ❌ | Using `extensions` to point at `skills/`, `agents/`, or a docs directory |
| ✅ | Using the component field that matches the content type |
| ❌ | Shipping an extension as a plugin's only component |
| ✅ | Pairing it with a skill so the plugin still does something without `--experimental` |
| ❌ | `exclusive: true` set "to be safe" |
| ✅ | `exclusive: true` only to deliberately replace built-in extensions, documented in the README |
| ❌ | Shipping TypeScript source as `extension.ts` |
| ✅ | Compiling to `extension.mjs` before publishing |
| ❌ | An `extensions` path that does not exist |
| ✅ | Deleting the field when the directory is removed |

## When to use each

| Situation | Field |
| --- | --- |
| Skills in a non-default directory | `skills` |
| Agents in a non-default directory | `agents` |
| A ported `.claude/commands/` file set | `commands` |
| Node.js code that adds tools or slash commands | `extensions` |
| Deliberately replacing the CLI's built-in extensions | `extensions` with `exclusive: true` |

Most plugins need none of these. `skills/` and `agents/` are found automatically; reach for
`commands` and `extensions` only when the default layout genuinely does not fit.
