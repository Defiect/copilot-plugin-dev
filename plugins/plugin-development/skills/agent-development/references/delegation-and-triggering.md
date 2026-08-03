# Delegation and triggering for custom agents

## Contents

- [How automatic delegation works](#how-automatic-delegation-works)
- [Write descriptions that fire reliably](#write-descriptions-that-fire-reliably)
- [Invocation controls](#invocation-controls)
- [Competing agents](#competing-agents)
- [Debugging procedure](#debugging-procedure)
- [Description rewrites](#description-rewrites)

## How automatic delegation works

Copilot may choose a custom agent when the user's task and the current context fit the
agent's `description`. The description is therefore the routing signal. The body is not
read until after the agent is selected, so a perfect prompt body cannot rescue a vague
description.

Custom agent work runs in a subagent with its own context window. That isolation is useful
for independent or lengthy tasks, but it means the main agent needs a structured result it
can consume when the subagent returns.

## Write descriptions that fire reliably

Use this shape:

```text
<What the agent does>. Use when <situation>, or when the user asks to "<phrase>", "<phrase>", or "<phrase>".
```

Checklist:

- State the concrete expertise: `Reviews recent Python changes for concurrency bugs`.
- Include `Use when`, `when the user`, or `for ...ing` trigger phrasing.
- Quote realistic user requests.
- Add a boundary if another agent is nearby: `Does not run tests; use the test-runner agent for command execution.`
- Avoid promises the tools cannot satisfy.

| ❌ Weak | ✅ Strong |
| --- | --- |
| `Helps with security.` | `Reviews scoped code changes for exploitable security defects. Use when the user asks to "security review", "audit this code", or "check for vulnerabilities".` |
| `Writes docs.` | `Creates or updates Markdown API documentation from existing code. Use when the user asks to "write API docs", "document this endpoint", or "update README usage".` |
| `Runs project tasks.` | `Runs existing test and build commands and reports failures without editing files. Use when the user asks to "run the tests", "check CI locally", or "reproduce this failure".` |

## Invocation controls

`disable-model-invocation` and `user-invocable` change how the agent can be reached.

| Field setting | Effect on availability |
| --- | --- |
| Omit both fields | Copilot may delegate automatically, and users can select the agent. |
| `disable-model-invocation: true` | Copilot does not auto-delegate; users must choose it manually. |
| `user-invocable: false` | The agent is hidden from manual selection and intended for automatic or programmatic use where supported. |
| Both `disable-model-invocation: true` and `user-invocable: false` | Treat as unreachable in CLI authoring; remove one setting. |

Use `disable-model-invocation` for agents that should be explicit, such as destructive or
expensive workflows. Use `user-invocable: false` sparingly because it makes manual testing
harder.

## Competing agents

When multiple agents have similar descriptions, Copilot may choose another agent or handle
the task itself. Reduce competition by narrowing each agent's description.

| Competition | Better split |
| --- | --- |
| `code-reviewer` and `security-reviewer` both say `review code` | Security agent says `exploitable security defects`; code reviewer says `correctness and regression bugs, not dedicated security audits`. |
| `test-runner` and `test-writer` both say `tests` | Runner says `run existing commands`; writer says `create or update test files`. |
| Plugin `reviewer.agent.md` and local `reviewer.agent.md` share an ID | Not a conflict — the plugin's is `acme-plugin:reviewer`. Disambiguate the *descriptions* so the model picks the right one. |

Non-plugin agents dedupe by filename-derived ID, first found wins, with personal outranking
project. Plugin agents are exempt: they are registered as `<plugin-name>:<agent-id>` and
never collide with anything.

## Debugging procedure

1. **Check that the file loads.** Restart Copilot CLI, run `/agent`, and look for the
   agent. If it is hidden intentionally, test through the programmatic route the workflow
   uses.
2. **Check the filename.** Confirm it ends with `.agent.md` and the ID is the name used in
   explicit invocations.
3. **Invoke explicitly.** Select the agent with `/agent` or ask `Use the AGENT-ID agent to
   ...`. If this fails, fix the body, tools, or frontmatter before changing the
   description.
4. **Test literal trigger phrasing.** Use one quoted phrase from the description. If this
   does not delegate, the description is still too vague or another agent is competing.
5. **Test natural phrasing.** Ask the way a real user would. If literal phrasing works and
   natural phrasing fails, add the natural phrase to the description.
6. **Inspect invocation controls.** Remove `disable-model-invocation: true` when automatic
   delegation is the goal. Avoid `user-invocable: false` until the agent is tested.
7. **Run the validator.** Resolve errors and warnings that affect discoverability or
   delegation.

## Description rewrites

### Vague review agent

❌

```yaml
description: Reviews code.
```

✅

```yaml
description: Reviews recent code changes for correctness bugs, regression risk, and concrete security defects. Use when the user asks to "review my changes", "check this implementation", or "find bugs before commit".
```

### Tool mismatch

❌

```yaml
description: Runs tests and fixes failures. Use when the user asks to "make tests pass".
tools: ["read", "search"]
```

✅

```yaml
description: Runs existing test commands and reports failures without editing files. Use when the user asks to "run the tests", "reproduce this failure", or "check CI locally".
tools: ["read", "search", "execute"]
```

### Should be a skill

❌

```yaml
description: Explains the team's commit message format. Use when the user asks to "write a commit message".
```

✅ Write a skill instead. The current agent can use commit-message instructions directly;
no separate worker or tool set is needed.
