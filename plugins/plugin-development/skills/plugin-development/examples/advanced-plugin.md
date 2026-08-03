# Advanced plugin

Every component type in one plugin, with the reasoning for each and the cost it carries.

Most plugins should not look like this. Read it to understand how the pieces fit, then use
the smallest subset that solves your problem.

## Directory

```text
acme-platform/
├── plugin.json
├── LICENSE
├── README.md
├── .mcp.json
├── lsp.json
├── hooks/
│   └── hooks.json
├── commands/
│   ├── acme-audit-deps.md
│   └── acme-release-checklist.md
├── agents/
│   ├── acme-service-reviewer.agent.md
│   └── acme-incident-researcher.agent.md
├── skills/
│   ├── acme-service-conventions/
│   │   ├── SKILL.md
│   │   └── references/naming.md
│   ├── acme-deployment/
│   │   ├── SKILL.md
│   │   ├── references/rollback.md
│   │   └── scripts/preflight.py
│   └── acme-incident-response/
│       ├── SKILL.md
│       └── references/severity-matrix.md
├── bin/
│   └── acme-mcp-server
└── scripts/
    ├── block-prod-writes.sh
    └── launch-lsp.sh
```

## `plugin.json`

```json
{
  "name": "acme-platform",
  "description": "Acme platform engineering: service conventions, deployment procedures, incident response, and the internal platform API.",
  "version": "4.2.0",
  "author": {
    "name": "Acme Platform Team",
    "email": "platform@acme.example",
    "url": "https://acme.example/platform"
  },
  "homepage": "https://github.com/acme/acme-platform-plugin",
  "repository": "https://github.com/acme/acme-platform-plugin",
  "license": "Apache-2.0",
  "category": "platform",
  "keywords": ["platform", "deployment", "incident-response", "acme"],
  "commands": "commands/",
  "hooks": "hooks/hooks.json",
  "mcpServers": ".mcp.json",
  "lspServers": "lsp.json"
}
```

`skills` and `agents` remain undeclared because they sit at their default locations.
`commands` must be declared — it has no default. `hooks`, `mcpServers`, and `lspServers` are
declared here even though `hooks/hooks.json` and `.mcp.json` are default locations, because
in a manifest this large explicitness is worth more than brevity.

## The MCP server

`.mcp.json`:

```json
{
  "mcpServers": {
    "acme-platform-api": {
      "type": "stdio",
      "command": "${PLUGIN_ROOT}/bin/acme-mcp-server",
      "args": ["--stdio"],
      "env": {
        "ACME_API_TOKEN": "${ACME_API_TOKEN}",
        "ACME_API_URL": "${ACME_API_URL}"
      }
    }
  }
}
```

Reasoning: the platform API is used by all three skills and both agents, so a bundled script
per skill would mean five copies. The token comes from the environment; it is never written
into the file. The key is namespaced because MCP servers merge last-wins, so an unnamespaced
`platform` key would silently replace a user's own.

Cost: this server's tool schemas load in every session. The plugin README lists them and
states the token requirement.

## The LSP server

`lsp.json`:

```json
{
  "lspServers": {
    "acme-idl": {
      "fileExtensions": [".acme", ".acmeidl"],
      "bash": "${PLUGIN_ROOT}/scripts/launch-lsp.sh"
    }
  }
}
```

`scripts/launch-lsp.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if ! command -v acme-idl-lsp >/dev/null 2>&1; then
  echo "acme-idl-lsp is not installed. Install it with: brew install acme/tap/acme-idl-lsp" >&2
  exit 127
fi

exec acme-idl-lsp --stdio
```

Reasoning: a plugin cannot assume a language server is installed. The wrapper fails with an
actionable message instead of producing an opaque error in every session. `fileExtensions`
is required, and it is narrow — the plugin claims only its own IDL format, not `.json` or
`.yaml`.

Note that `args` is deliberately absent: it is ignored for `bash` entries, so arguments go
inside the script.

## The hooks

`hooks/hooks.json`:

```json
{
  "version": 1,
  "hooks": {
    "preToolUse": [
      {
        "type": "command",
        "matcher": "shell|bash",
        "bash": "${PLUGIN_ROOT}/scripts/block-prod-writes.sh",
        "timeoutSec": 5
      }
    ]
  }
}
```

Reasoning, and the caveat: this hook runs for every installing user, in every session, on
every shell tool call. It is justified here only because blocking writes to production is
the reason the plugin exists at the organization that ships it. The `matcher` restricts it
to shell tools; the timeout is short because `preToolUse` timeouts fail **open**, so a slow
hook silently stops protecting anything.

A hook is a security control only in combination with real controls on the production
system. Never rely on it alone.

The plugin README states, in the first section, that installing this plugin installs a
`preToolUse` hook. Surprising a user with a hook is a trust failure.

## The commands

`commands/acme-release-checklist.md`:

```markdown
Run the Acme pre-release checklist for this service.

1. Confirm the version in the service manifest matches the tag being released.
2. Confirm the changelog has an entry for this version with no "TBD" placeholders.
3. Confirm every migration in this release has a stated rollback path.
4. Confirm the deployment runbook link resolves.
5. List any open pull request labelled `release-blocker`.

Output a checklist with a pass or fail mark per item and a single overall verdict line.
Do not modify any file.
```

Reasoning: release engineers know exactly when they want this. Making it a skill would mean
guessing, and would cost always-on context to describe a workflow the user can name.

## The agents

Two agents, each with a minimal tool set:

| Agent | `tools` | Why |
| --- | --- | --- |
| `acme-service-reviewer` | `read, search` | Reviews. Must not edit or execute. |
| `acme-incident-researcher` | `read, search, web` | Gathers context during an incident. Must not change anything while a system is degraded. |

Both filenames carry the `acme-` prefix for readability. Plugin agents are namespaced
automatically, so these resolve as `acme-platform:acme-service-reviewer` and
`acme-platform:acme-incident-researcher`. A repository with its own `reviewer.agent.md`
cannot shadow them, and they cannot shadow it.

## The skills

| Skill | Bundles | Why it is a skill and not something else |
| --- | --- | --- |
| `acme-service-conventions` | One reference | Pure knowledge. No execution, no isolation needed. |
| `acme-deployment` | One reference, one script | A procedure with one deterministic step, delegated to `preflight.py`. |
| `acme-incident-response` | One reference | Judgment under pressure — exactly what instructions are for. |

## Cost accounting

| Item | Always-on cost |
| --- | --- |
| 3 skill descriptions | ~350 tokens |
| 2 agent descriptions | ~250 tokens |
| MCP tool schemas (11 tools) | ~2,200 tokens |
| Commands | ~0 |
| Hooks | ~0 until fired |
| LSP | ~0 until queried |
| **Total** | **~2,800 tokens per session** |

That is above the 2,000-token guideline. The honest options are to trim the MCP server's
tool surface, or to split the incident-response content into a second plugin that only the
on-call rotation installs. Publishing this table in the plugin README lets users make that
call themselves.

## Checklist before shipping something this large

- [ ] Every skill `name` is namespaced.
- [ ] Every MCP and LSP server key is namespaced.
- [ ] No absolute paths anywhere; every bundled path uses `${PLUGIN_ROOT}`.
- [ ] No credentials in any committed file; every secret comes from the environment.
- [ ] The README states, prominently, that the plugin installs a hook and what it does.
- [ ] The README lists every MCP tool and the credentials required.
- [ ] Every external binary is guarded by a wrapper with an actionable failure message.
- [ ] `validate_plugin.py . --warnings-as-errors` exits zero.
- [ ] The plugin has been installed from a clean state and every component verified present.
- [ ] Each skill has been trigger-tested with realistic user phrasings.
- [ ] The always-on context cost has been measured and published.
