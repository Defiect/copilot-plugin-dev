# Loading order and precedence

Why a component that validates cleanly can still fail to appear, and how to diagnose it.

## Contents

- [The three precedence systems](#the-three-precedence-systems)
- [Custom agents](#custom-agents)
- [Agent skills](#agent-skills)
- [MCP servers](#mcp-servers)
- [Where installed plugins live](#where-installed-plugins-live)
- [Worked example: a shadowed skill](#worked-example-a-shadowed-skill)
- [Worked example: agents that only look like a collision](#worked-example-agents-that-only-look-like-a-collision)
- [Worked example: an overridden MCP server](#worked-example-an-overridden-mcp-server)
- [Diagnosing a shadowing problem](#diagnosing-a-shadowing-problem)
- [Designing around precedence](#designing-around-precedence)

## The three precedence systems

There is no single ordering. Three component families resolve conflicts differently, and
each has its own source list.

| Family | Deduplicated by | Rule | Where plugins sit |
| --- | --- | --- | --- |
| Custom agents | ID, derived from the **filename** | First loaded wins | Not in the list — plugin agents are namespaced |
| Agent skills | Frontmatter `name` | First loaded wins | 7th of 8 |
| MCP servers | Server key | **Last loaded wins** | 2nd of 3 |
| Built-in tools and agents | — | Always present, never overridable | — |

Plugins sit near the end of the skill list, so plugin **skills lose** almost every conflict.
For MCP servers plugins **win** against everything except `--additional-mcp-config`. Plugin
**agents do not compete at all** — they get their own `<plugin-name>:` namespace.

Hooks are absent from this table because they do not deduplicate. Every registered hook for
an event runs, in an order not to be depended on.

## Custom agents

Agents resolve in **two separate namespaces**.

**Plugin agents are namespaced.** An agent shipped by a plugin is registered as
`<plugin-name>:<agent-id>`, so `agents/reviewer.agent.md` in the `acme-platform` plugin is
invoked as `acme-platform:reviewer`. The bare ID never resolves to it. Plugin agents
therefore cannot shadow, and cannot be shadowed by, anything.

**Everything else shares one flat namespace**, deduplicated by the agent ID derived from
the filename — `reviewer.agent.md` becomes `reviewer`. The `name` frontmatter field is a
display name and has no effect on deduplication. First loaded wins:

| Order | Source | Scope |
| --- | --- | --- |
| 1 | `~/.copilot/agents/` | Personal |
| 2 | `<project>/.github/agents/` | Project |
| 3 | `<parents>/.github/agents/` | Inherited, for monorepos |
| 4 | `<project>/.claude/agents/` | Project, compatibility |
| 5 | `<parents>/.claude/agents/` | Inherited, compatibility |
| 6 | Remote organization and enterprise agents | Remote, via API |

Note the first row. For **agents**, personal configuration outranks project configuration —
the opposite of skills. A stale `~/.copilot/agents/reviewer.agent.md` beats the
repository's `reviewer`, though it does not affect any plugin's.

## Agent skills

First loaded wins. Deduplication key: the frontmatter `name` field. The directory name is
irrelevant to deduplication.

| Order | Source | Scope |
| --- | --- | --- |
| 1 | `<project>/.github/skills/` | Project |
| 2 | `<project>/.agents/skills/` | Project |
| 3 | `<project>/.claude/skills/` | Project, compatibility |
| 4 | `<parents>/.github/skills/` and equivalents | Inherited, for monorepos |
| 5 | `~/.copilot/skills/` | Personal |
| 6 | `~/.agents/skills/` | Personal |
| 7 | Plugin `skills/` directories | Plugin |
| 8 | `COPILOT_SKILLS_DIRS` environment variable and config | Custom |

For **skills**, project configuration outranks personal. Commands load after skills, and a
skill overrides a command of the same name.

## MCP servers

Last loaded wins. Deduplication key: the server name.

| Order | Source | Priority |
| --- | --- | --- |
| 1 | `~/.copilot/mcp-config.json` | Lowest |
| 2 | Plugin MCP configurations | Middle |
| 3 | `--additional-mcp-config` command-line flag | Highest |

Consequences:

- A plugin **replaces** a user's personal server of the same name, silently from the user's
  point of view. Namespace plugin server keys.
- When two plugins declare the same server name, the plugin that loaded last wins and the
  CLI emits a warning naming every earlier plugin that defined it.
- `--additional-mcp-config` is the user's escape hatch for overriding a plugin's server.
  Mention it in the plugin README if the plugin ships a server users may want to redirect.

## Where installed plugins live

| Item | Path |
| --- | --- |
| Installed via a marketplace | `~/.copilot/installed-plugins/<marketplace>/<plugin-name>` |
| Installed directly from a path or URL | `~/.copilot/installed-plugins/_direct/<source-id>/` |
| Marketplace cache (Linux) | `~/.cache/copilot/marketplaces/` |
| Marketplace cache (macOS) | `~/Library/Caches/copilot/marketplaces/` |
| Cache location override | `COPILOT_CACHE_HOME` |
| Per-plugin writable data | `${COPILOT_PLUGIN_DATA}`, alias `${CLAUDE_PLUGIN_DATA}` |

These are copies. `${PLUGIN_ROOT}` resolves to the installed path, not to the repository the
plugin was built in. Write runtime state to `${COPILOT_PLUGIN_DATA}`, never into the
installed-plugins directory, which the CLI manages and replaces on reinstall.

Inspecting the installed copy is the fastest way to confirm whether a reinstall actually
picked up an edit.

## Worked example: a shadowed skill

Files on disk:

```text
/repo/.github/skills/deploy/SKILL.md                    name: deploy   (stale, from last year)
~/.copilot/skills/deploy-notes/SKILL.md                 name: deploy   (personal scratch)
<installed>/acme-platform/skills/acme-deploy/SKILL.md   name: deploy   (the plugin's, current)
```

All three declare `name: deploy`.

| Order | Source | Result |
| --- | --- | --- |
| 1 | `/repo/.github/skills/deploy/` | **Wins.** This is the skill that loads. |
| 5 | `~/.copilot/skills/deploy-notes/` | Discarded — duplicate `name`. |
| 7 | Plugin | Discarded — duplicate `name`. (Only a *second plugin* would get a qualified name; see below.) |

The personal skill lives in a directory called `deploy-notes` and the plugin's in
`acme-deploy`, yet both still collide, because the key is the frontmatter `name`. Renaming
directories changes nothing; changing the `name:` value does.

User-visible symptom: "I installed the plugin, but it gives me the old instructions."

### Two plugins are the exception

Shadowing applies when a plugin skill collides with a **project or personal** skill. When
two *plugins* provide skills with the same `name`, neither is dropped — both stay reachable
under plugin-qualified invocation names:

```text
/acme-platform:deploy     → the acme-platform plugin's skill
/globex-tools:deploy      → the globex-tools plugin's skill
/deploy                   → routes to the higher-priority plugin
```

Qualification happens **only on collision**. A plugin skill whose name is unique keeps its
bare name; the moment a second plugin ships the same name, both are re-keyed. Verified
against `copilot skill list --json`, which reports the qualified names directly:

```json
{"name": "plug-a:shared-probe", "source": "plugin", "path": ".../plug-a/skills/shared-probe"}
{"name": "plug-b:shared-probe", "source": "plugin", "path": ".../plug-b/skills/shared-probe"}
```

The published reference writes this form as `/my-plugin/search` with a slash. The CLI
actually uses a **colon**, matching the `<plugin-name>:<agent-id>` convention for agents.
Use the colon.

This applies to **skills only**. Commands keep the standard tier-based deduplication, where
the higher-priority source wins outright.

Two practical consequences:

- A plugin skill name that collides with another plugin is recoverable — the user can still
  reach yours by qualifying it. A collision with a project or personal skill is not.
- Still namespace your skill names. The bare `/deploy` going to somebody else's plugin is a
  bad first experience, and no user wants to type a qualified name to get the tool they
  installed.

## Worked example: agents that only look like a collision

```text
~/.copilot/agents/reviewer.agent.md                 → ID "reviewer"                 (personal)
/repo/.github/agents/reviewer.agent.md              → ID "reviewer"                 (project)
<installed>/acme-platform/agents/reviewer.agent.md  → ID "acme-platform:reviewer"   (plugin)
```

There are two independent outcomes here.

Among the non-plugin agents, the **personal** one wins, because `~/.copilot/agents/` is
first in the flat agent source list. The project's `reviewer` is silently ignored. This
surprises people who assume project configuration always wins — it does for skills, not for
agents.

The plugin's agent is unaffected. It is registered as `acme-platform:reviewer` and stays
reachable:

```bash
copilot --agent acme-platform:reviewer -p "Review this change"
```

Asking for the bare `reviewer` gets the personal agent, and asking for a plugin agent by
bare ID fails outright — the error lists every available qualified ID, which is the fastest
way to discover the exact spelling.

Because the namespace already guarantees uniqueness, prefixing a plugin's agent filenames
is a readability choice rather than a collision defense. It is still worth doing when the
bare ID would be meaningless in isolation:

| | Filename in a plugin | Resulting ID |
| --- | --- | --- |
| Acceptable | `reviewer.agent.md` | `acme-platform:reviewer` |
| Clearer | `service-reviewer.agent.md` | `acme-platform:service-reviewer` |

For **project and personal** agents, which have no namespace, distinct filenames are still
a genuine requirement.

## Worked example: an overridden MCP server

```jsonc
// ~/.copilot/mcp-config.json
{ "mcpServers": { "github": { "type": "http", "url": "https://api.github.com/mcp" } } }
```

```jsonc
// <installed>/acme-platform/.mcp.json
{ "mcpServers": { "github": { "type": "http", "url": "https://ghe.acme.example/mcp" } } }
```

Effective configuration: the **plugin's** entry. MCP merges last-wins and plugins outrank
personal configuration, so the user's own server is replaced for that key without them
asking.

The user's remedy is `--additional-mcp-config`, which outranks the plugin. The plugin
author's remedy is to not cause the collision:

| | Key |
| --- | --- |
| ❌ | `github` — collides with the ecosystem-standard key |
| ❌ | `db` |
| ✅ | `acme-ghe` |
| ✅ | `acme-platform-db` |

## Diagnosing a shadowing problem

Only skills and MCP servers can actually be shadowed. If a plugin *agent* seems missing,
the cause is almost always that it was invoked by its bare ID instead of
`<plugin-name>:<agent-id>`. Run `copilot --agent bogus -p x`: the error lists every
available qualified agent ID, which is the fastest way to find the exact spelling.

1. **Confirm the plugin is installed.**

   ```bash
   copilot plugin list
   ```

2. **Search every scope for the same skill name.** The key is frontmatter `name`:

   ```bash
   grep -rl "^name: deploy$" \
     .github/skills .agents/skills .claude/skills \
     ~/.copilot/skills ~/.agents/skills 2>/dev/null
   ```

   For non-plugin agents, which do share a flat namespace, the key is the filename:

   ```bash
   find ~/.copilot/agents .github/agents .claude/agents \
     -name 'reviewer.agent.md' 2>/dev/null
   ```

3. **Check the installed copy** to rule out a stale install:

   ```bash
   ls ~/.copilot/installed-plugins/*/acme-platform/skills/
   ```

4. **Run the precedence checker** from the `plugin-testing` skill, which sweeps every scope,
   reports which skill copy wins and why, and prints the qualified ID of every plugin agent.

5. **Resolve** by one of:
   - Deleting the stale project or personal copy, if it is genuinely obsolete.
   - Renaming the plugin's skill to a namespaced `name`.
   - Accepting the shadow, if the local override is intentional.

6. **Reinstall and re-verify.** Components are copied at install time, so a rename in the
   source tree has no effect until `copilot plugin install ./path` runs again.

## Designing around precedence

1. **Namespace plugin skill `name` values** with the plugin's name or a short prefix.
   Plugins lose nearly every skill collision, so the goal is to never have one. Plugin
   *agents* need no such care — they are namespaced automatically as
   `<plugin-name>:<agent-id>` and cannot collide.
2. **Namespace MCP and LSP server keys** for the opposite reason — plugins *win* those
   collisions and will replace a user's own configuration without warning them.
3. **Remember that personal agents outrank project agents, while project skills outrank
   personal skills.** Do not generalize one rule to the other.
4. **Do not attempt to override a built-in tool or agent.** It cannot be done.
5. **Document every name the plugin claims** in the plugin README, so a user hitting a
   collision finds the cause in one place.
6. **Assume hooks accumulate.** A hook must be safe to run alongside other plugins' hooks
   for the same event, in an unspecified order.
