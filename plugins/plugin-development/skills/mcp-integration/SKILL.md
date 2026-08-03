---
name: mcp-integration
description: Configure and ship MCP servers with a GitHub Copilot CLI plugin. Use when the user asks to "bundle an MCP server", "add a tool server to my plugin", mentions ".mcp.json", or says "my MCP server isn't loading". Does not cover authoring an MCP server itself, only shipping and configuring one in a plugin.
license: MIT
---

# MCP integration

Bundling an MCP server in a plugin means the plugin declares one or more Model Context
Protocol servers, and every installing user gets those tools in their Copilot CLI session.
Do this deliberately: every MCP tool consumes context in every session, even when the
user's task does not need it.

## Core principles

**1. Bundle the smallest useful tool surface.** Prefer focused servers and explicit
`tools` allowlists. A broad server makes every session heavier and increases the chance
that Copilot selects the wrong tool.

**2. Treat configuration as shipped API.** Server names, environment variables, headers,
and file paths become part of the plugin contract. Rename them only as a breaking change.

**3. Keep secrets out of committed files.** Reference environment variables in `env` and
`headers`; never commit tokens, passwords, API keys, or bearer values.

**4. Name servers defensively.** MCP server definitions merge last-wins, unlike agents
and skills. A plugin MCP server can override a project server with the same name, so use
plugin-prefixed names such as `acme-docs` instead of `docs`.

## Integration workflow

1. **Choose the transport.** Use `stdio` for a local process that speaks MCP over
   standard input/output, `local` only when preserving an existing Copilot-style local
   config, `http` for Streamable HTTP, and `sse` only for a legacy Server-Sent Events
   endpoint.
2. **Write the config.** Create an `mcpServers` object, or use the bare top-level server
   map only for project-level files. Validate the shape with
   [`scripts/validate_mcp.py`](scripts/validate_mcp.py).
3. **Parameterize secrets.** Put credentials in environment variables and reference them
   from `env` or `headers`. For OAuth or bearer-token patterns, open
   [`references/authentication.md`](references/authentication.md).
4. **Declare the config.** Put the file at `.mcp.json` or `.github/mcp.json` in the
   plugin, or set `mcpServers` in `plugin.json` to a path or inline object.
5. **Install the plugin.** Run `copilot plugin install ./path/to/plugin`. Reinstall after
   editing source files because installed plugin components are copied at install time.
6. **Verify the server.** In Copilot CLI, run `/mcp show` or `copilot mcp list --json`,
   then inspect the tool list for the server. If an agent should use the server, confirm
   its `tools` and `mcp-servers` frontmatter expose the server intentionally.
7. **Handle failure.** Read the server status from `/mcp show SERVER-NAME`, fix the first
   reported config or startup error, reinstall the plugin, and test again.

## Server types

| Type | Required fields | Choose it when |
| --- | --- | --- |
| `local` | `type`, `command`, `args` | A Copilot-oriented local process config already uses `local`. |
| `stdio` | `type`, `command`, `args` | A bundled or external process speaks MCP over `stdin`/`stdout`; this is the standard protocol name and the portable default. |
| `http` | `type`, `url` | A remote server supports Streamable HTTP. Use `https://` URLs. |
| `sse` | `type`, `url` | A remote server still exposes the legacy SSE transport. Use only for compatibility. |

Set `tools` explicitly for every shipped server, even when a setup command would default
to `*`, so reviewers can see the context budget in the committed file. For every field
and complete examples, open [`references/server-types.md`](references/server-types.md).

## File locations

Copilot CLI reads plugin MCP configuration from these places:

| Location | Use |
| --- | --- |
| `.mcp.json` | Default plugin or project MCP config. |
| `.github/mcp.json` | Shared repository-style config. |
| `plugin.json` `mcpServers` path | Point at a JSON file such as `.mcp.json`. |
| `plugin.json` `mcpServers` object | Inline the server map in the manifest. |

Project-level files may use a bare top-level map where each key is a server name. Prefer
`mcpServers` in plugin examples because it is unambiguous.

## Copilot shape, not VS Code shape

VS Code's top-level `servers` key is **not** read by Copilot CLI.

| ❌ VS Code shape | ✅ Copilot CLI shape |
| --- | --- |
| `{"servers":{"docs":{"command":"npx","args":["-y","@example/mcp"]}}}` | `{"mcpServers":{"docs":{"type":"stdio","command":"npx","args":["-y","@example/mcp"],"tools":["*"]}}}` |

If a server works in VS Code but not in Copilot CLI, migrate the top-level key and remove
VS Code-only `inputs` or `envFile` indirection.

## Precedence and naming

MCP servers merge **last-wins**. This is the opposite of agents and skills, which use
first-wins precedence. Practical consequence: a plugin MCP server **can override** a
project or personal server with the same name. Prefix plugin server names with the plugin
or company name, for example `acme-search`, because generic names such as `github`,
`docs`, or `jira` collide easily.

For the full loading order, a worked merge example, and agent tool-frontmatter guidance,
open [`references/precedence-and-tools.md`](references/precedence-and-tools.md).

## Plugin paths and state

Use `${PLUGIN_ROOT}` when a config needs a file shipped in the plugin:

```json
{
  "mcpServers": {
    "acme-index": {
      "type": "stdio",
      "command": "python3",
      "args": ["${PLUGIN_ROOT}/servers/acme_index.py"],
      "tools": ["search_index"]
    }
  }
}
```

Use `${COPILOT_PLUGIN_DATA}` for writable plugin state. Do not write inside the installed
plugin directory; installed plugin files are cache content and may be replaced on update.

## Secrets

| ❌ Do not commit | ✅ Commit this instead |
| --- | --- |
| `"GITHUB_TOKEN": "ghp_abc123..."` | `"GITHUB_TOKEN": "${GITHUB_TOKEN}"` |
| `"Authorization": "Bearer real-token"` | `"Authorization": "Bearer ${ACME_MCP_TOKEN}"` |
| `"api_key": "live_secret_value"` | `"api_key": "${ACME_API_KEY}"` |

Document required credentials in the plugin README and name the exact environment
variables users must set. Never hide required authentication in a wrapper script.

## Tool budget guidance

| Rule | Reason |
| --- | --- |
| Prefer focused MCP servers | Fewer tool schemas consume less context in every session. |
| Set `tools` to specific tool names | `*` exposes every current and future tool from the server. |
| Document each bundled server's tools in the plugin README | Users can decide whether the plugin is worth the context cost. |
| Consider agent `tools` and `mcp-servers` filters | Agents that do not need the server should not receive its tools. |

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Server does not appear | The config file is not at a discovered location or `plugin.json` points to the wrong path | Put the config at `.mcp.json` / `.github/mcp.json`, or fix `mcpServers`, then reinstall the plugin. |
| Server appears but tools do not | `tools` excludes the tool, the server failed tool discovery, or the agent filters omit the server | Run `/mcp show SERVER-NAME`, compare the tool list, then update `tools` or agent frontmatter. |
| Auth failures | A token was omitted, named incorrectly, or committed as a literal placeholder | Use environment-variable references and document the required variables. |
| Stdio server exits immediately | The command is missing, args are wrong, or the script needs a working directory or dependency | Run the exact command manually, then fix `command`, `args`, or the bundled script. |
| HTTP server TLS errors | The URL uses `http://`, a self-signed certificate, or an intercepted corporate certificate | Use a trusted `https://` endpoint; do not disable TLS validation in plugin docs. |
| Works in VS Code but not CLI | The config uses top-level `servers`, `inputs`, or `envFile` | Convert it to `mcpServers` with direct `env` or `headers` references. |

## Bundled files

- [`references/server-types.md`](references/server-types.md) — field reference and per-type examples.
- [`references/authentication.md`](references/authentication.md) — credential patterns and documentation rules.
- [`references/precedence-and-tools.md`](references/precedence-and-tools.md) — loading order, merge examples, and agent tool filters.
- [`examples/stdio-server.json`](examples/stdio-server.json) — one local stdio server.
- [`examples/http-server.json`](examples/http-server.json) — one remote HTTP server with a bearer header.
- [`examples/plugin-bundled-server.json`](examples/plugin-bundled-server.json) — a bundled script launched through `${PLUGIN_ROOT}`.
- [`examples/multi-server.json`](examples/multi-server.json) — mixed transports and environment-variable secrets.
- [`scripts/validate_mcp.py`](scripts/validate_mcp.py) — stdlib-only MCP config validator.
