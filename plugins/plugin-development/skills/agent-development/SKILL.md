---
name: agent-development
description: "Create, review, and debug GitHub Copilot custom agents. Use when the user asks to \"create a custom agent\", \"write a subagent\", \"agent.md\", \"make an agent that reviews code\", or \"why isn't my agent being delegated to\". Distinguishes agents from skills: agents get their own context window and tool set; skills inject instructions into the current one."
license: MIT
---

# Agent development

A custom agent is a Markdown profile that creates a separate Copilot worker with its own
instructions, context window, and tool allowlist. Use this skill to design agents that are
specific enough to delegate reliably and constrained enough to run safely.

## Agents vs skills vs commands

Choose the smallest customization that fits the job. A skill teaches the current agent how
to do something; an agent is a separate worker with its own context window and constrained
tools. Use an agent when the work is independent, long, or needs isolation from the main
conversation.

| Question | Agent | Skill | Command |
| --- | --- | --- | --- |
| What it is | A named worker profile in `*.agent.md` | A lazy-loaded instruction bundle in `SKILL.md` | A user-invoked prompt or workflow entry point |
| Where it runs | In a subagent with a separate context window | In the current agent's context window | In the current interaction when invoked |
| What context it gets | Its prompt body, delegated task, selected tools, and context it gathers | The current conversation plus the loaded skill body | The command prompt and arguments |
| When Copilot chooses it | Automatically from `description`, unless disabled; users can also select it | Automatically from the skill `description` | Only when the user invokes the command |
| Choose this when | The task is independent, lengthy, parallelizable, or should not pollute main context | The current agent needs procedures, references, scripts, or conventions | The user needs a repeatable entry point with explicit arguments |

## Anatomy and discovery

Create one file per agent. The agent ID comes from the **filename**, not from the
frontmatter `name` display field.

```text
my-plugin/
├── plugin.json
└── agents/
    ├── acme-code-reviewer.agent.md   # ID: acme-code-reviewer
    └── acme-test-runner.agent.md     # ID: acme-test-runner
```

Both `.agent.md` and plain `.md` are accepted, and the ID is the filename minus the
extension either way. Use `.agent.md`: it makes the file's purpose obvious and keeps agent
files distinguishable from documentation that happens to sit in the same tree.

Copilot CLI discovers custom agents from these locations:

| Location | Scope | Invoked as |
| --- | --- | --- |
| `.github/agents/` | Current project | `<agent-id>` |
| `~/.copilot/agents/` | Current user | `<agent-id>` |
| `<plugin>/agents/` | Installed plugin | `<plugin-name>:<agent-id>` |

**Plugin agents are namespaced automatically.** An agent shipped by a plugin is registered
under `<plugin-name>:<agent-id>`. A file `agents/plugin-validator.agent.md` inside the
`plugin-development` plugin is invoked as `plugin-development:plugin-validator`, and the
bare `plugin-validator` does not resolve to it:

```bash
copilot --agent plugin-development:plugin-validator -p "Review ./my-plugin"
```

Two consequences follow:

- **Plugin agents cannot be shadowed**, and cannot shadow anything. A personal
  `~/.copilot/agents/plugin-validator.agent.md` and a plugin
  `plugin-development:plugin-validator` coexist; each resolves only under its own name.
- **Project and personal agents share one flat namespace** and do dedupe by ID, first found
  wins. Personal outranks project, so `~/.copilot/agents/foo.agent.md` shadows
  `.github/agents/foo.agent.md`.

Prefixing plugin agent filenames is therefore a readability choice, not collision
avoidance — the namespace already guarantees uniqueness. Prefixes still matter for project
and personal agents, which have no namespace of their own.

## Frontmatter reference

Agent files start with YAML frontmatter and continue with the system prompt body. The body
is capped at **30,000 characters**; treat that as a hard limit, not a target.

| Field | Type | Required | Default | Effect |
| --- | --- | --- | --- | --- |
| `description` | string | Yes | None | Describes the agent and drives automatic delegation. State **when** to delegate. |
| `name` | string | No | Filename-derived ID | Display name for the agent; it does not determine the ID. |
| `target` | string | No | Both supported environments | Targets an environment such as `vscode` or `github-copilot`. |
| `tools` | string or string list | No | All tools | Filters which built-in and MCP tools the agent can use. |
| `model` | string | No | Inherits default model | Overrides the model used when the agent executes. |
| `disable-model-invocation` | boolean | No | `false` | Prevents automatic delegation when `true`; the agent must be selected manually. |
| `user-invocable` | boolean | No | `true` | Hides the agent from user selection when `false`. |
| `mcp-servers` | object | No | None | Adds MCP servers and tools for the agent where supported. |
| `metadata` | object | No | None | Stores string annotations for tooling; not used by VS Code or other IDE agents. |

Read [references/frontmatter-reference.md](references/frontmatter-reference.md) before
shipping an agent with `mcp-servers`, `metadata`, or non-default invocation controls.
`infer` is retired; never use it in new agent files.

## Tools

The `tools` field accepts a YAML list or a comma-separated string:

```yaml
tools: ["read", "search"]
```

```yaml
tools: read, search
```

Use primary aliases unless compatibility requires another spelling: `execute`, `read`,
`edit`, `search`, `agent`, `web`, and `todo`. `tools: ["*"]` enables all tools. `tools: []`
enables none.

| Agent purpose | Minimal tools | Do not grant by default |
| --- | --- | --- |
| Code reviewer | `read`, `search` | `edit`, `execute` |
| Researcher | `read`, `search`, `web` | `edit`, `execute` |
| Test runner | `read`, `search`, `execute` | `edit` |
| Refactorer | `read`, `search`, `edit` | `execute` unless tests must run |
| Documentation writer | `read`, `search`, `edit` | `execute` |
| Triage classifier | `read`, `search` | `edit`, `execute` |

For risks and MCP tool naming, read [references/tools-reference.md](references/tools-reference.md).

## System prompt design

Write the body as the agent's operating manual. A reliable agent prompt has this skeleton:

1. **State the persona.** Start with one sentence: `You are an expert ...`. This anchors
   the role before any procedure starts.
2. **List Core Responsibilities.** Use numbered outcomes, not topics, so the agent knows
   what success means.
3. **Define the Process.** Give ordered steps with failure branches. This prevents a
   topic-list prompt from becoming improvisation.
4. **Set Quality Standards.** Use testable rules such as `Every finding includes file:line`.
5. **Specify Output Format.** Provide a literal template. Without an explicit output
   format, the result is hard for the caller to parse or act on.

Compact output-format block:

```markdown
## Output Format

Verdict: PASS | PASS WITH MINOR ISSUES | FAIL

### Critical
- `file:line` — [Bug, exploit path, or data-loss risk] — [Required fix]

### Major
- `file:line` — [Correctness or maintainability issue] — [Recommended fix]

### Minor
- `file:line` — [Low-risk improvement] — [Optional fix]

If no findings meet the bar, write `No reportable findings.` and list what was checked.
```

For deeper templates, read [references/system-prompt-design.md](references/system-prompt-design.md).

## Authoring workflow

1. **Pick the customization type.** Use the comparison table above. If the main agent must
   keep control and only needs instructions, write a skill instead.
2. **Name the file.** Choose a distinctive kebab-case ID such as
   `acme-security-reviewer.agent.md`; avoid IDs that collide with built-ins or common
   local names.
3. **Write the description.** State the expertise and the delegation trigger: `Use when
   the user asks to ...`. If automatic delegation fails, fix this field first.
4. **Constrain tools.** Grant the smallest alias set that lets the agent complete its
   job. Add `execute` only when running commands is central to the task.
5. **Write the system prompt.** Use the skeleton above and keep the body under 30,000
   characters.
6. **Validate.** Run `scripts/validate_agent.py PATH` from this skill directory or call it
   by absolute path.
7. **Test delegation.** Invoke explicitly with `/agent`, then make a natural request that
   does not name the agent. If explicit invocation works but automatic delegation does not,
   revise `description` using
   [references/delegation-and-triggering.md](references/delegation-and-triggering.md).

## Anti-patterns

| ❌ Avoid | ✅ Prefer |
| --- | --- |
| `description: Helps with code.` | `description: Reviews recent code changes for correctness and security. Use when the user asks to "review my changes" or "check this implementation".` |
| `tools: ["*"]` on every agent | Grant `read, search` first; add `edit` or `execute` only when required. |
| No output format | A `## Output Format` section with headings, severity tiers, and a verdict line. |
| A prompt that lists topics only | A numbered process that says what to read, check, decide, and report. |
| `Be helpful.` | Testable rules such as `Report only findings with a concrete file:line location.` |
| Duplicating the main agent's broad job | A narrow worker such as `dependency-license-reviewer`. |
| An agent that only teaches a procedure | A skill, because no separate context or tool set is needed. |
| Body over 30,000 characters | Move background material into references or shorten the procedure. |
| `infer: false` | `disable-model-invocation: true`; `infer` is retired. |

## Testing and iteration

1. **Confirm loading.** Restart Copilot CLI after creating the file. In an interactive
   session, run `/agent` and check that the agent appears when `user-invocable` is not
   `false`.
2. **Invoke explicitly.** Select the agent with `/agent`, or ask `Use the AGENT-ID agent
   to ...`. This tests the body separately from delegation.
3. **Test automatic delegation.** Ask a realistic request without naming the agent, such
   as `Review these auth changes for vulnerabilities`. If Copilot does not delegate, edit
   `description`, not the body.
4. **Inspect the result.** Check whether the report follows the output template and whether
   tool use stayed within the intended scope.
5. **Iterate one change at a time.** Re-test after each description, tool, or prompt edit;
   multiple changes hide the cause of improvement or regression.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Agent is not listed | Wrong location, wrong extension, hidden by `user-invocable: false`, or invalid frontmatter | Place `*.agent.md` in `.github/agents/`, `~/.copilot/agents/`, or `<plugin>/agents/`; run the validator. |
| Agent is listed but never auto-delegated | `description` does not describe when to delegate, or `disable-model-invocation: true` is set | Add quoted trigger phrasing and remove the disable flag if automatic use is desired. |
| Agent runs but ignores instructions | Prompt is a topic list, conflicts with the task, or lacks failure branches | Rewrite as persona, responsibilities, process, standards, and output format. |
| Agent lacks a needed tool | `tools` is too narrow | Add the smallest missing alias, then re-test. |
| Plugin agent not found by its bare ID | Plugin agents are namespaced as `<plugin-name>:<agent-id>` | Invoke it as `plugin-name:agent-id`; the error message lists every available qualified ID. |
| Prompt is truncated or rejected | Body exceeds 30,000 characters | Shorten the body and move optional background into references. |

## Bundled files

- [references/frontmatter-reference.md](references/frontmatter-reference.md) — field types,
  defaults, interactions, MCP servers, metadata, and retired fields.
- [references/system-prompt-design.md](references/system-prompt-design.md) — detailed prompt
  skeletons, bounded processes, and output templates.
- [references/tools-reference.md](references/tools-reference.md) — tool aliases, risks, and
  least-privilege recipes.
- [references/delegation-and-triggering.md](references/delegation-and-triggering.md) —
  automatic delegation mechanics and debugging procedure.
- [examples/complete-agent-examples.md](examples/complete-agent-examples.md) — complete
  copy-pasteable agent files.
- [scripts/validate_agent.py](scripts/validate_agent.py) — standalone validator for agent
  profile files and plugin `agents/` directories.
