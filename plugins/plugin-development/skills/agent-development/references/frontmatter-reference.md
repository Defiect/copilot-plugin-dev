# Custom agent frontmatter reference

## Contents

- [Format](#format)
- [Field summary](#field-summary)
- [`description`](#description)
- [`name`](#name)
- [`target`](#target)
- [`tools`](#tools)
- [`model`](#model)
- [`disable-model-invocation` and `user-invocable`](#disable-model-invocation-and-user-invocable)
- [`mcp-servers`](#mcp-servers)
- [`metadata`](#metadata)
- [Retired and unsupported fields](#retired-and-unsupported-fields)
- [Validation checklist](#validation-checklist)

## Format

A custom agent profile is a Markdown file with YAML frontmatter followed by the system
prompt body:

```markdown
---
name: Readme specialist
description: Improves README files. Use when the user asks to "write a README" or "fix the docs".
tools: ["read", "search", "edit"]
---

You are a documentation specialist...
```

Rules:

- Name the file `AGENT-ID.agent.md` for Copilot CLI plugin agents. The ID is the filename
  without `.agent.md`.
- Put plugin agents in `<plugin>/agents/`. Project agents use `.github/agents/`; personal
  agents use `~/.copilot/agents/`.
- Keep the prompt body at or below **30,000 characters**. The limit is hard.
- Quote YAML values that contain `: `, `#`, `{`, `[`, or other YAML-significant tokens.

## Field summary

| Field | Type | Required | Default | Accepted forms | Effect |
| --- | --- | --- | --- | --- | --- |
| `description` | string | Yes | None | Plain string | Explains purpose and drives delegation. |
| `name` | string | No | Filename-derived ID | Plain string | Display name only; does not determine ID. |
| `target` | string | No | Both supported environments | `vscode`, `github-copilot` | Restricts target environment. |
| `tools` | string or string list | No | All tools | `read, search` or `["read", "search"]` | Filters available built-in and MCP tools. |
| `model` | string | No | Default model | Model name string | Overrides the model when the agent executes. |
| `disable-model-invocation` | boolean | No | `false` | `true` or `false` | Prevents automatic model delegation when `true`. |
| `user-invocable` | boolean | No | `true` | `true` or `false` | Controls whether users can select the agent manually. |
| `mcp-servers` | object | No | None | YAML mapping | Adds MCP servers and tools for the agent where supported. |
| `metadata` | object | No | None | String key/value mapping | Annotates the agent for tooling. |

## `description`

Write the description as a delegation contract. It must state what the agent does and when
Copilot should hand work to it.

```yaml
description: Reviews recent code changes for correctness, security, and regression risk. Use when the user asks to "review my changes", "check this implementation", or "find bugs in this PR".
```

Checklist:

- Include `Use when ...`, `when the user ...`, or equivalent trigger phrasing.
- Quote two to five phrases a user would type.
- Distinguish the agent from overlapping agents.
- Keep it specific; descriptions under 40 characters rarely delegate reliably.
- Keep it under 1024 characters for portability.

## `name`

`name` is a display name. The agent ID comes from the filename:

| File | `name` | Agent ID |
| --- | --- | --- |
| `agents/acme-reviewer.agent.md` | `Code Review Specialist` | `acme-reviewer` |
| `agents/security-auditor.agent.md` | omitted | `security-auditor` |

Use a kebab-case filename even if the display name uses spaces. Avoid IDs that collide
with built-in agents such as `explore`, `task`, `general-purpose`, `code-review`,
`research`, and `rubber-duck`.

## `target`

`target` is a string. The documented values are `vscode` and `github-copilot`. If unset,
the agent applies to both supported environments. Omit this field for Copilot CLI plugin
agents unless there is a concrete compatibility reason to restrict it.

## `tools`

`tools` accepts either a comma-separated string or a YAML list:

```yaml
tools: read, search
```

```yaml
tools:
  - read
  - search
```

Documented primary aliases are case-insensitive:

| Alias | Permits |
| --- | --- |
| `execute` | Shell execution through the appropriate shell. |
| `read` | Reading file contents. |
| `edit` | Editing or writing files. |
| `search` | Searching files and file contents. |
| `agent` | Invoking another custom agent. |
| `web` | Fetching URLs and web search where supported. |
| `todo` | Structured task-list management where supported. |

Special forms:

| Form | Effect |
| --- | --- |
| Omit `tools` | Enable all available tools. |
| `tools: ["*"]` | Enable all available tools explicitly. |
| `tools: []` | Disable all tools. |
| `github/get_issue` | Enable a named MCP server tool. |
| `github/*` | Enable all tools from a named MCP server. |

Prefer explicit least-privilege aliases over `"*"`. Unknown tool names are ignored by the
runtime, but the validator warns because misspellings silently remove capability.

## `model`

`model` is a string. If unset, the agent inherits the default model. Use this field only
when a specific agent has a demonstrated need for a different model; unnecessary model
pinning makes behavior harder to update as defaults improve.

## `disable-model-invocation` and `user-invocable`

These fields control how the agent can be selected.

| `disable-model-invocation` | `user-invocable` | Resulting behavior |
| --- | --- | --- |
| `false` or unset | `true` or unset | Copilot may delegate automatically, and users may select the agent. |
| `true` | `true` or unset | Copilot will not auto-delegate; users must select the agent manually. |
| `false` or unset | `false` | Users cannot select it manually; it remains available for automatic or programmatic use where supported. |
| `true` | `false` | No normal CLI route can reach it. Treat this as an authoring error. |

Use `disable-model-invocation: true` for agents that are too expensive or risky to run
without explicit selection. Use `user-invocable: false` only for agents intended to be
called programmatically by tooling.

## `mcp-servers`

`mcp-servers` is a YAML mapping that configures additional MCP servers for the custom
agent. It uses the repository MCP JSON configuration shape expressed in YAML.

```yaml
mcp-servers:
  custom-mcp:
    type: local
    command: some-command
    args: ["--arg1", "--arg2"]
    tools: ["*"]
```

Notes from the documented behavior:

- MCP tools can be filtered through `tools` with names such as `custom-mcp/tool-1`.
- `stdio` is mapped to the cloud agent's `local` type for compatibility.
- Secret and variable interpolation is supported by the documented MCP configuration
  syntax, including `$NAME`, `${NAME}`, `${NAME:-default}`, `${{ secrets.NAME }}`, and
  `${{ vars.NAME }}`.
- The `mcp-servers` field is not used in VS Code and other IDE custom agents.

## `metadata`

`metadata` is an object consisting of string key/value pairs. Use it for annotations that
external tooling consumes, not for runtime instructions. Put behavior in the prompt body;
put delegation behavior in `description`.

```yaml
metadata:
  owner: platform-team
  review-tier: strict
```

## Retired and unsupported fields

| Field | Status | Use instead |
| --- | --- | --- |
| `infer` | Retired | `disable-model-invocation` and `user-invocable` |
| `allowed-tools` | Skill field, not agent field | `tools` |
| `argument-hint` | Not supported for Copilot cloud agent | Put required inputs in the prompt body. |
| `handoffs` | Not supported for Copilot cloud agent | Use documented agent invocation mechanisms. |

`infer` appears in older examples. Do not copy it. If both `infer` and
`disable-model-invocation` appear, the documented precedence gives
`disable-model-invocation` control, but new files must remove `infer` entirely.

## Validation checklist

- [ ] Filename ends in `.agent.md` and the derived ID is kebab-case.
- [ ] `description` is present, specific, and trigger-oriented.
- [ ] `tools` grants only the aliases the agent needs.
- [ ] `disable-model-invocation` and `user-invocable` are booleans when present.
- [ ] `disable-model-invocation: true` is not combined with `user-invocable: false`.
- [ ] Prompt body is non-empty, headed, procedural, and under 30,000 characters.
- [ ] Prompt includes an explicit output or deliverable format.
- [ ] No `infer` or `allowed-tools` field remains.
