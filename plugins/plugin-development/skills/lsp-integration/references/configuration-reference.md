# LSP configuration reference

Use this reference when writing `lspServers` for a Copilot CLI plugin.

## Contents

- [Top-level shape](#top-level-shape)
- [Fields](#fields)
- [Launch forms](#launch-forms)
- [`args` caveat](#args-caveat)
- [Variable expansion and paths](#variable-expansion-and-paths)
- [Validation checklist](#validation-checklist)

## Top-level shape

```json
{
  "lspServers": {
    "typescript": {
      "command": "typescript-language-server",
      "args": ["--stdio"],
      "fileExtensions": {
        ".ts": "typescript",
        ".tsx": "typescriptreact"
      }
    }
  }
}
```

`lspServers` is a map. Each key is a server name. Each value is a server definition.
Server names should use alphanumeric characters, underscores, and hyphens.

## Fields

| Field | Type | Required | Default | Behavior |
| --- | --- | --- | --- | --- |
| `fileExtensions` | object | Yes | None | Map of file extensions to language IDs, for example `{ ".rs": "rust" }`. |
| `command` | string | At least one launch form | None | Executable to launch the language server. |
| `bash` | string | At least one launch form | None | Bash script line executed via `bash -c SCRIPT` on Linux/macOS. |
| `powershell` | string | At least one launch form | None | PowerShell script line executed via `pwsh -c SCRIPT` on Windows. |
| `args` | string array | No | None | Arguments passed to `command`. Ignored for `bash` and `powershell`. |
| `env` | object | No | None | Environment variables to set when spawning the server. Supports `${VAR}` and `${VAR:-default}` expansion syntax. |
| `cwd` | string | No | Config-file-relative behavior documented | Working directory. Absolute or relative to the configuration file; supports `${PLUGIN_ROOT}`. |
| `rootUri` | string | No | `.` | Project root relative to the Git root. Use it for monorepos. |
| `initializationOptions` | any | No | None | Options sent to the server in the LSP `initialize` request. |
| `requestTimeoutMs` | number | No | 90,000 | Timeout for server requests in milliseconds. |

## Launch forms

Use `command` when a binary on `PATH` accepts normal arguments:

```json
{
  "lspServers": {
    "python": {
      "command": "pyright-langserver",
      "args": ["--stdio"],
      "fileExtensions": {".py": "python", ".pyi": "python"}
    }
  }
}
```

Use `bash` when the plugin ships a wrapper or needs a shell check:

```json
{
  "lspServers": {
    "go": {
      "bash": "${PLUGIN_ROOT}/skills/lsp-integration/examples/bundled-wrapper.sh gopls",
      "fileExtensions": {".go": "go"}
    }
  }
}
```

Use `powershell` for Windows-specific launch scripts:

```json
{
  "lspServers": {
    "example": {
      "powershell": "${PLUGIN_ROOT}/scripts/start-example-lsp.ps1",
      "fileExtensions": {".example": "example"}
    }
  }
}
```

The plugin reference documents that both `bash` and `powershell` can be specified for a
cross-platform server, with the platform-appropriate command selected. This skill's
validator flags multiple launch forms by default to keep examples single-platform and
unambiguous; relax that house rule only when the plugin intentionally ships both scripts.

## `args` caveat

`args` is ignored for `bash` and `powershell` entries. This is a common silent mistake.

| ❌ Ignored | ✅ Honored |
| --- | --- |
| `{"bash":"start-gopls.sh","args":["-rpc.trace"]}` | `{"bash":"start-gopls.sh -rpc.trace"}` |
| `{"powershell":"start.ps1","args":["--stdio"]}` | `{"powershell":"start.ps1 --stdio"}` |
| `{"command":"gopls","args":["serve"]}` | `{"command":"gopls","args":["serve"]}` |

## Variable expansion and paths

Use `${PLUGIN_ROOT}` for files shipped inside the installed plugin. Use `env` for process
environment variables and values that need `${VAR}` or `${VAR:-default}` expansion.

Avoid hardcoded absolute paths. If a wrapper needs persistent state, pass a path under the
project root or document the server's own cache location; LSP docs do not define a plugin
state variable for language servers beyond plugin path expansion.

## Validation checklist

1. **Check the map.** Confirm the top-level object is `lspServers` or a bare server map in
   a plugin field.
2. **Check extensions.** Ensure `fileExtensions` is non-empty and every key starts with a
   dot unless the language server documents a filename-style extension such as `.rake`.
3. **Check launch form.** Use one of `command`, `bash`, or `powershell` for house-style
   configs; avoid mixing unless intentionally shipping a cross-platform pair.
4. **Check `args`.** Use `args` only with `command`.
5. **Check paths.** Replace hardcoded absolute paths with `${PLUGIN_ROOT}` wrappers.
6. **Check startup.** Run `/lsp test SERVER-NAME` after installing the plugin.
