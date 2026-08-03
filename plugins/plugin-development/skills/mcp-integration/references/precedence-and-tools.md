# MCP precedence and tools reference

Use this reference when a plugin MCP server collides with another server name, or when an
agent should receive only selected MCP tools.

## Contents

- [Loading order](#loading-order)
- [Last-wins merge rule](#last-wins-merge-rule)
- [Worked merge example](#worked-merge-example)
- [Naming conventions](#naming-conventions)
- [Agent tool filtering](#agent-tool-filtering)

## Loading order

Copilot CLI always keeps built-in tools and built-in agents. User-defined components load
around them with different merge rules:

| Scope | Agents and skills | MCP servers |
| --- | --- | --- |
| Built-in | Built-in tools and agents are always present and cannot be overridden. | Built-in servers, such as GitHub MCP, are available without plugin config. |
| Project | `.github/agents/`, `.github/skills/`, and related project roots. | Repository `.github/mcp.json`. |
| Workspace | Not a distinct agent or skill tier. | `.mcp.json`. When both exist in one directory, `.mcp.json` wins over `.github/mcp.json`. |
| Personal | `~/.copilot/agents/` and `~/.copilot/skills/`. Personal skills outrank project skills. | `~/.copilot/mcp-config.json`. Project definitions outrank it. |
| Plugin | Plugin `agents/` and `skills/` directories. | Plugin `.mcp.json`, `.github/mcp.json`, or `plugin.json` `mcpServers`. |
| Command line | Not a normal agent or skill source. | `--additional-mcp-config` can override a plugin MCP server with the same name. |

Skills use first-found-wins by `name`, so plugin skills lose to project and personal
definitions. Plugin agents are namespaced as `<plugin-name>:<agent-id>` and do not collide
at all. MCP servers use last-wins by server name, so later MCP definitions replace earlier
ones.

## Last-wins merge rule

MCP servers are keyed by server name. If two configs define `docs`, only the later one is
used. This is intentionally different from agents and skills, where the first definition
wins and plugin definitions lose to project or personal definitions.

Practical consequence: a plugin MCP server can override a project server if both use the
same name. Use distinct names even for obvious services.

## Worked merge example

Project config:

```json
{
  "mcpServers": {
    "docs": {
      "type": "http",
      "url": "https://project.example.com/mcp",
      "tools": ["search"]
    }
  }
}
```

Plugin config loaded later:

```json
{
  "mcpServers": {
    "docs": {
      "type": "stdio",
      "command": "node",
      "args": ["${PLUGIN_ROOT}/servers/docs.js"],
      "tools": ["lookup"]
    },
    "acme-docs": {
      "type": "http",
      "url": "https://docs.acme.example/mcp",
      "tools": ["search"]
    }
  }
}
```

Effective result:

```json
{
  "mcpServers": {
    "docs": {
      "type": "stdio",
      "command": "node",
      "args": ["${PLUGIN_ROOT}/servers/docs.js"],
      "tools": ["lookup"]
    },
    "acme-docs": {
      "type": "http",
      "url": "https://docs.acme.example/mcp",
      "tools": ["search"]
    }
  }
}
```

The plugin's `docs` definition won because MCP uses last-wins. The safer design is to
ship only `acme-docs` and leave the project `docs` server untouched.

## Naming conventions

| ❌ Collision-prone | ✅ Distinct |
| --- | --- |
| `docs` | `acme-docs` |
| `github` | `acme-github-insights` |
| `jira` | `acme-jira-readonly` |
| `search` | `acme-internal-search` |

Keep names stable. Agents and user prompts can refer to MCP server names, and approvals
for MCP tools use the raw configured server name.

## Agent tool filtering

Custom agents can control tools with frontmatter. Use `tools` to expose broad tool
categories or exact tools, and use `mcp-servers` to limit which MCP servers reach the
agent.

`mcp-servers` is a **mapping** of server name to configuration, using the same schema as
`mcp-config.json` — not a list of server names:

```markdown
---
description: Review Acme docs using only the Acme docs MCP server.
tools: ["read", "search"]
mcp-servers:
  acme-docs:
    type: http
    url: https://mcp.example.com/mcp
    tools: ["search", "get_document"]
---
```

To restrict which of the plugin's servers an agent may reach, narrow the agent's `tools`
list. `mcp-servers` *adds* servers for that agent; it does not filter the ones already
configured.

Apply these rules:

1. **Expose only needed servers.** Add `mcp-servers` only when an agent needs a server the
   session does not already have.
2. **Pair server filters with `tools`.** If an agent does not need external tools, do not
   expose MCP tools just because the plugin installed them.
3. **Document server tool names.** Put each bundled server's tool list in the plugin
   README so agent authors can filter intentionally.
4. **Recheck after server updates.** A server using `tools: ["*"]` may expose new tools
   after an update, changing agent behavior without a plugin diff.
