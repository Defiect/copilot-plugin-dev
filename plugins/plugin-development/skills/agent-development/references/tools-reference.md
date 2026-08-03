# Custom agent tools reference

## Contents

- [Tool filtering model](#tool-filtering-model)
- [Aliases and risks](#aliases-and-risks)
- [Least-privilege recipes](#least-privilege-recipes)
- [MCP tools](#mcp-tools)
- [Tool selection workflow](#tool-selection-workflow)
- [Common mistakes](#common-mistakes)

## Tool filtering model

The `tools` field filters which tools an agent may use. If the field is omitted, all
available tools are enabled. If it is an empty list, no tools are enabled.

```yaml
# all available tools
tools: ["*"]

# no tools
tools: []

# least-privilege read-only review
tools: ["read", "search"]
```

Use primary aliases in new Copilot agent files. Compatibility aliases such as `Read` or
`Bash` may appear in cross-tool examples, but primary aliases are clearer in Copilot CLI
plugins.

## Aliases and risks

| Primary alias | Compatible aliases | Permits | Risk |
| --- | --- | --- | --- |
| `execute` | `shell`, `Bash`, `powershell` | Running shell commands. | Highest risk: commands can change state, install packages, or expose local data. |
| `read` | `Read`, `NotebookRead` | Reading file contents. | Can expose sensitive repository files to the model context. |
| `edit` | `Edit`, `MultiEdit`, `Write`, `NotebookEdit` | Creating or modifying files. | Can damage code or configuration if the prompt is wrong. |
| `search` | `Grep`, `Glob` | Finding files and text. | Low risk, but broad searches can pull irrelevant context. |
| `agent` | `custom-agent`, `Task` | Invoking another custom agent. | Can create uncontrolled delegation chains unless the prompt forbids it. |
| `web` | `WebSearch`, `WebFetch` | Web search and URL fetching where supported. | May introduce untrusted external content into the task. |
| `todo` | `TodoWrite` | Structured task-list management where supported. | Low direct risk; can create process overhead for small tasks. |

Grant the risk, not the ambition. A reviewer that only reports findings does not need
`edit`; a test runner that only runs commands does not need `edit`.

## Least-privilege recipes

| Archetype | Tools | Rationale |
| --- | --- | --- |
| Reviewer | `read`, `search` | Needs evidence from files and diffs; should not edit or run commands. |
| Researcher | `read`, `search`, `web` | Needs local and external evidence; should report, not modify. |
| Test runner | `read`, `search`, `execute` | Needs to locate existing commands and run them; should not patch failures. |
| Refactorer | `read`, `search`, `edit` | Needs to understand and modify code; add `execute` only if it must run tests. |
| Doc writer | `read`, `search`, `edit` | Needs existing docs and write access; shell is rarely necessary. |
| Triager | `read`, `search` | Needs classification from existing artifacts; should not mutate state. |

Escalate tool access one alias at a time. Re-test the agent after adding `edit` or
`execute` because those aliases change the failure modes.

## MCP tools

MCP server tools can be enabled by name through `tools`.

| Form | Meaning |
| --- | --- |
| `github/get_issue` | Enable one tool from the `github` MCP server. |
| `github/*` | Enable all tools from the `github` MCP server. |
| `custom-mcp/tool-1` | Enable one tool from an agent-defined MCP server. |

Out-of-the-box MCP server names documented for Copilot cloud agent include `github` and
`playwright`. The GitHub server provides read-only tools by default with a token scoped to
the source repository. The Playwright server is configured to access localhost.

## Tool selection workflow

1. **Write the desired output.** Decide whether the agent reports, edits, runs, or
   delegates.
2. **Map each required action to one alias.** Reporting needs `read` and `search`; editing
   needs `edit`; command execution needs `execute`.
3. **Remove unused aliases.** If the process never calls a shell command, remove
   `execute`.
4. **State tool boundaries in the prompt.** A read-only agent should say `Never edit
   files` even if `edit` is absent; this makes behavior clear to reviewers.
5. **Validate.** Run `scripts/validate_agent.py` and resolve unknown-tool warnings.

## Common mistakes

| ❌ Mistake | Why it fails | ✅ Fix |
| --- | --- | --- |
| `tools: ["*"]` for convenience | The agent can do more than its purpose requires. | Start with the smallest recipe above. |
| `execute` for a reviewer | Shell access is unnecessary for static review and raises risk. | Use `read`, `search`. |
| `edit` for a test runner | A runner should report failures, not patch them. | Use `read`, `search`, `execute`. |
| Misspelled alias | Unknown names are ignored, so the agent silently lacks capability. | Run the validator and use primary aliases. |
| Nested agent delegation by default | Subagents can recurse or duplicate work. | Omit `agent` unless orchestration is the agent's core job. |
