# MCP server types reference

Use this reference when writing or reviewing an MCP server config for a Copilot CLI plugin.
The examples use `mcpServers` because plugin manifests and user configs use that shape;
project-level files may also use a bare top-level server map.

## Contents

- [Common shape](#common-shape)
- [`local`](#local)
- [`stdio`](#stdio)
- [`http`](#http)
- [`sse`](#sse)
- [Variables and defaults](#variables-and-defaults)
- [Server and tool naming](#server-and-tool-naming)
- [Tool snapshot caching](#tool-snapshot-caching)
- [Headless OAuth](#headless-oauth)

## Common shape

```json
{
  "mcpServers": {
    "server-name": {
      "type": "stdio",
      "command": "example-server",
      "args": [],
      "tools": ["*"]
    }
  }
}
```

| Field | Type | Required | Default | Behavior |
| --- | --- | --- | --- | --- |
| `type` | string | Yes for explicit plugin configs | None | Selects `local`, `stdio`, `http`, or `sse`. `streamable-http` is accepted as an alias and normalized to `http`. If omitted in an existing file, infer only during migration and write it back explicitly. |
| `tools` | string array | Required by repository MCP docs; set explicitly in plugins | `/mcp add` defaults to `*` | Lists enabled tools. Use `['*']` only when the full tool surface is intentional. |

All string and string-array fields except `tools` and `type` support variable or secret
substitution in the forms `$VAR`, `${VAR}`, and `${VAR:-default}`. For plugin-local files,
use `${PLUGIN_ROOT}` for files shipped by the plugin and `${COPILOT_PLUGIN_DATA}` for
persistent writable state.

## `local`

`local` starts a local process and communicates with it over standard input/output. It
works the same way as `stdio`; keep it only when the surrounding Copilot configuration or
docs already use the Copilot-local name.

| Field | Type | Required | Default | Behavior |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | None | Must be `local`. |
| `command` | string | Yes | None | Executable to start the MCP server. Use a bare command on `PATH` or a `${PLUGIN_ROOT}` path. |
| `args` | string array | Yes | None | Arguments passed to `command`. Use `[]` when the command takes no arguments. |
| `env` | object | No | Only `PATH` is inherited by the add flow | Environment variables passed to the process. Values must be literals or variable references. |
| `tools` | string array | Set explicitly | `/mcp add` defaults to `*` | Tool allowlist. Prefer named tools over `*`. |
| `cwd` | string | No | Process inherits the CLI's directory | Working directory for the server process. |
| `timeout` | number | No | Server default | Tool call timeout in **milliseconds**. |
| `deferTools` | string | No | `auto` | `auto` lets tool search hide this server's tools; `never` keeps them always visible. |
| `disableToolCache` | boolean | No | `false` | `true` skips loading and persisting this server's tool snapshot, forcing live discovery. |
| `oidc` | boolean | No | `false` | Injects an OIDC token into any `GITHUB_COPILOT_OIDC_MCP_TOKEN[_SUFFIX]` variable referenced in `env`. |
| `filterMapping` | string | No | `hidden_characters` | How tool output is processed: `none`, `markdown`, or `hidden_characters`. |

Minimal:

```json
{
  "mcpServers": {
    "acme-local": {
      "type": "local",
      "command": "acme-mcp",
      "args": [],
      "tools": ["search"]
    }
  }
}
```

Complete:

```json
{
  "mcpServers": {
    "acme-local": {
      "type": "local",
      "command": "${PLUGIN_ROOT}/bin/acme-mcp",
      "args": ["--state", "${COPILOT_PLUGIN_DATA}/acme", "--mode", "readonly"],
      "env": {
        "ACME_API_TOKEN": "${ACME_API_TOKEN}",
        "ACME_REGION": "${ACME_REGION:-us-east-1}"
      },
      "tools": ["search", "get_document"]
    }
  }
}
```

## `stdio`

`stdio` starts a local process and communicates with it over `stdin`/`stdout`. Prefer this
name for new plugin configs because it is the standard MCP protocol transport name and is
compatible with other MCP clients.

| Field | Type | Required | Default | Behavior |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | None | Must be `stdio`. |
| `command` | string | Yes | None | Executable to start the server. |
| `args` | string array | Yes | None | Arguments passed to `command`. |
| `env` | object | No | Only configured variables are guaranteed | Environment variables passed to the server. |
| `tools` | string array | Set explicitly | `/mcp add` defaults to `*` | Tool allowlist. |
| `cwd` | string | No | Process inherits the CLI's directory | Working directory for the server process. |
| `timeout` | number | No | Server default | Tool call timeout in **milliseconds**. |
| `deferTools` | string | No | `auto` | `auto` lets tool search hide this server's tools; `never` keeps them always visible. |
| `disableToolCache` | boolean | No | `false` | `true` skips loading and persisting this server's tool snapshot, forcing live discovery. |
| `oidc` | boolean | No | `false` | Injects an OIDC token into any `GITHUB_COPILOT_OIDC_MCP_TOKEN[_SUFFIX]` variable referenced in `env`. |
| `filterMapping` | string | No | `hidden_characters` | How tool output is processed: `none`, `markdown`, or `hidden_characters`. |

Minimal:

```json
{
  "mcpServers": {
    "acme-stdio": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@acme/mcp-server"],
      "tools": ["lookup"]
    }
  }
}
```

Complete:

```json
{
  "mcpServers": {
    "acme-stdio": {
      "type": "stdio",
      "command": "node",
      "args": ["${PLUGIN_ROOT}/servers/acme-mcp.js", "--cache", "${COPILOT_PLUGIN_DATA}/cache"],
      "env": {
        "ACME_TOKEN": "${ACME_TOKEN}",
        "ACME_ENDPOINT": "${ACME_ENDPOINT:-https://api.example.com}"
      },
      "tools": ["lookup", "read_record"]
    }
  }
}
```

## `http`

`http` connects to a remote MCP server using the Streamable HTTP transport. Use HTTPS for
committed plugin configs.

| Field | Type | Required | Default | Behavior |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | None | Must be `http`. `streamable-http` is accepted as an alias and is normalized to `http`; prefer writing `http`. |
| `url` | string | Yes | None | Remote MCP endpoint URL. Use `https://`. |
| `headers` | object | No | None | HTTP headers attached to requests. Values may reference environment variables. |
| `tools` | string array | Set explicitly | `/mcp add` defaults to `*` | Tool allowlist. |
| `timeout` | number | No | Server default | Tool call timeout in **milliseconds**. |
| `deferTools` | string | No | `auto` | `auto` lets tool search hide this server's tools; `never` keeps them always visible. |
| `oauthClientId` | string | No | None | Static OAuth client ID; skips dynamic client registration. |
| `oauthPublicClient` | boolean | No | `true` | Set `false` for a confidential client with a stored secret. |
| `oauthGrantType` | string | No | `authorization_code` | `authorization_code` uses the browser flow; `client_credentials` is fully headless. |
| `oidc` | boolean | No | `false` | Sends an OIDC token as the `Bearer` `Authorization` header. |
| `filterMapping` | string | No | `hidden_characters` | How tool output is processed: `none`, `markdown`, or `hidden_characters`. |

Minimal:

```json
{
  "mcpServers": {
    "acme-http": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "tools": ["search"]
    }
  }
}
```

Complete:

```json
{
  "mcpServers": {
    "acme-http": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${ACME_MCP_TOKEN}",
        "X-Acme-Workspace": "${ACME_WORKSPACE}"
      },
      "tools": ["search", "get_document"]
    }
  }
}
```

## `sse`

`sse` connects to a remote MCP server using the legacy HTTP with Server-Sent Events
transport. Use it only when the server has not moved to Streamable HTTP.

| Field | Type | Required | Default | Behavior |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | None | Must be `sse`. |
| `url` | string | Yes | None | Remote SSE endpoint URL. Use `https://`. |
| `headers` | object | No | None | HTTP headers attached to requests. Values may reference environment variables. |
| `tools` | string array | Set explicitly | `/mcp add` defaults to `*` | Tool allowlist. |
| `timeout` | number | No | Server default | Tool call timeout in **milliseconds**. |
| `deferTools` | string | No | `auto` | `auto` lets tool search hide this server's tools; `never` keeps them always visible. |
| `oauthClientId` | string | No | None | Static OAuth client ID; skips dynamic client registration. |
| `oauthPublicClient` | boolean | No | `true` | Set `false` for a confidential client with a stored secret. |
| `oauthGrantType` | string | No | `authorization_code` | `authorization_code` uses the browser flow; `client_credentials` is fully headless. |
| `oidc` | boolean | No | `false` | Sends an OIDC token as the `Bearer` `Authorization` header. |
| `filterMapping` | string | No | `hidden_characters` | How tool output is processed: `none`, `markdown`, or `hidden_characters`. |

Minimal:

```json
{
  "mcpServers": {
    "acme-sse": {
      "type": "sse",
      "url": "https://mcp.example.com/sse",
      "tools": ["search"]
    }
  }
}
```

Complete:

```json
{
  "mcpServers": {
    "acme-sse": {
      "type": "sse",
      "url": "https://mcp.example.com/sse",
      "headers": {
        "Authorization": "Bearer ${ACME_MCP_TOKEN}"
      },
      "tools": ["search", "get_document"]
    }
  }
}
```

## Variables and defaults

| Topic | Rule |
| --- | --- |
| Secret references | Use `$VAR`, `${VAR}`, or `${VAR:-default}`. In Copilot cloud-agent repository settings, referenced secret and variable names must start with `COPILOT_MCP_`. |
| Local process environment | The add flow documents `PATH` inheritance and requires other variables to be configured in `env`. Plugin configs should not rely on ambient credentials. |
| HTTP scheme | Use `https://` for `http` and `sse`. Treat `http://` as a local-development exception only. |
| Tool default | The `/mcp add` UI defaults to `*`; committed plugin files should set `tools` explicitly so reviewers see the context cost. |

## Server and tool naming

The server name is the key in `mcpServers`, and it becomes part of every tool name the
model sees. Choose it deliberately.

- **Namespace it to your plugin.** `acme-docs` is a good key; `search` is not. Server names
  collide across sources, and a generic key will be shadowed by, or shadow, someone else's.
- **Copilot sanitizes names before sending them to the model.** Any character outside
  `a-z`, `A-Z`, `0-9`, `-`, and `_` is replaced with `-`. Unicode is Punycode-encoded, and
  `@` is replaced with `-` to avoid colliding with Punycode. Write names that already
  satisfy those rules so the name in your config matches the name the model reasons about.
- **The combined `serverName-toolName` is capped at 64 characters.** When truncation would
  create a collision, a numeric suffix is appended (`my-server-tool2`, `my-server-tool3`).
  A long server name silently eats the budget your tool names need, so keep the key short.
- **Never write to stdout from a `stdio` or `local` server.** The MCP protocol owns that
  stream; stray `print` or log output corrupts the message framing and the server appears
  to fail for no visible reason. Log to stderr or a file.

## Tool snapshot caching

Copilot CLI persists a snapshot of each local server's tool list so tools are usable
immediately at startup while live discovery runs in the background. Live discovery always
runs and replaces the snapshot when it completes.

This matters while you are developing an MCP server: after you add or rename a tool, the
first moments of a session may still show the previous list. Set `disableToolCache: true`
on the server to force live discovery for that server only, or set
`COPILOT_MCP_TOOL_CACHE=false` to disable snapshot loading and persistence for the whole
process. Both opt-outs leave existing cache files untouched. Ship neither in a released
plugin — they trade startup latency for freshness that only an author needs.

## Headless OAuth

For CI or scheduled use where no browser exists, a remote server can use the
`client_credentials` grant. It requires all three of:

- `oauthGrantType: "client_credentials"`
- `oauthClientId` — the static client ID issued by the provider
- `oauthPublicClient: false` — the client is confidential

plus a `client_secret` stored in the system keychain, configured once through the `/mcp` UI
or written to the OAuth credential store. With this set, the CLI skips the browser,
callback server, PKCE, and dynamic registration entirely, and posts
`grant_type=client_credentials` to the discovered token endpoint on every 401.

```json
{
  "mcpServers": {
    "headless-api": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "tools": ["search"],
      "oauthClientId": "YOUR-CLIENT-ID",
      "oauthPublicClient": false,
      "oauthGrantType": "client_credentials"
    }
  }
}
```

A plugin should not hard-code a client ID that only its author can use. Reference it
through a variable, or document it as something the installer must supply.
