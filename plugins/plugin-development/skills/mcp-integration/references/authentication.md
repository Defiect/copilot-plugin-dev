# MCP authentication reference

Use this reference when an MCP server needs a token, API key, OAuth bearer value, or
workspace-specific credential.

## Contents

- [Credential rules](#credential-rules)
- [Environment variables for local servers](#environment-variables-for-local-servers)
- [HTTP and SSE bearer patterns](#http-and-sse-bearer-patterns)
- [OAuth notes](#oauth-notes)
- [Token rotation](#token-rotation)
- [Documentation checklist](#documentation-checklist)

## Credential rules

| ❌ Never commit | ✅ Commit |
| --- | --- |
| Personal access tokens such as `ghp_...` or `github_pat_...` | `${GITHUB_TOKEN}` or a plugin-specific variable name |
| Cloud access keys such as `AKIA...` | `${AWS_ACCESS_KEY_ID}` only when the server explicitly needs it |
| Bearer tokens in `headers` | `"Authorization": "Bearer ${ACME_MCP_TOKEN}"` |
| Passwords in `env` | `"ACME_PASSWORD": "${ACME_PASSWORD}"` |
| Long base64 or hex strings that are credentials | A named environment variable reference |

Reference variables directly in the MCP JSON. Do not read a `.env` file from a committed
wrapper unless the plugin also documents who creates that file and where it lives.

## Environment variables for local servers

Local `local` and `stdio` servers receive variables through `env`:

```json
{
  "mcpServers": {
    "acme-stdio": {
      "type": "stdio",
      "command": "node",
      "args": ["${PLUGIN_ROOT}/servers/acme.js"],
      "env": {
        "ACME_TOKEN": "${ACME_TOKEN}",
        "ACME_STATE": "${COPILOT_PLUGIN_DATA}/acme"
      },
      "tools": ["search"]
    }
  }
}
```

Keep variable names specific to the plugin, for example `ACME_MCP_TOKEN`, because generic
names such as `TOKEN` collide with other tooling.

## HTTP and SSE bearer patterns

Remote `http` and `sse` servers use `headers` for bearer tokens or provider-specific API
keys:

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

Use `https://` endpoints. Do not document a flag that disables TLS verification; it turns
transport authentication into best-effort plaintext trust.

## OAuth notes

Copilot CLI stores MCP OAuth fallback state under the Copilot configuration directory
when keychain storage is unavailable. A plugin config should still describe the initial
authorization flow in user-facing docs because the JSON file only identifies the server
and request headers. Do not claim OAuth support for a server unless that server's own
documentation states the flow works with Copilot CLI.

For remote servers, prefer one of these committed shapes:

| Pattern | Config shape |
| --- | --- |
| Existing bearer token | `"Authorization": "Bearer ${ACME_MCP_TOKEN}"` |
| Provider API key header | `"X-API-Key": "${ACME_API_KEY}"` |
| Local token broker | `stdio` server that reads `${ACME_TOKEN}` and performs provider auth itself |

## Token rotation

1. **Name the variable.** Use a stable name such as `ACME_MCP_TOKEN` in every example.
2. **Document where to set it.** Tell users whether it belongs in their shell, CI secret
   store, or Copilot environment for the target runtime.
3. **Avoid caching secrets in the plugin directory.** Use `${COPILOT_PLUGIN_DATA}` only
   for non-secret state unless the server owns secure storage.
4. **Restart or reload.** After rotating a token, run `/mcp disable SERVER-NAME` and
   `/mcp enable SERVER-NAME`, or restart Copilot CLI if the server reads credentials only
   at process start.

## Documentation checklist

Document each credential in the plugin README or marketplace listing:

- Variable name, for example `ACME_MCP_TOKEN`.
- Provider page where the user creates the credential.
- Minimum scopes or permissions.
- Whether the server needs read-only or write-capable access.
- Rotation steps.
- The exact server name that consumes the credential.

Never put a real token in `examples/`; examples are copied into issues, logs, and pull
requests more often than authors expect.
