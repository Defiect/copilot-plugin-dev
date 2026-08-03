# Component patterns

How the six component types combine, and which combination fits a given problem.

## Contents

- [The six components](#the-six-components)
- [Choosing between overlapping components](#choosing-between-overlapping-components)
- [Plugin shapes](#plugin-shapes)
- [Composition rules](#composition-rules)
- [Cost model](#cost-model)

## The six components

| Component | Lives in | Loaded | Cost per session | Can it act on its own? |
| --- | --- | --- | --- | --- |
| Skill | `skills/<name>/SKILL.md` | Description always; body on trigger | Description only, ~50–150 tokens | No — it instructs the current agent |
| Agent | `agents/<id>.agent.md` | Description always; prompt on delegation | Description only | Yes — separate context window and tool set |
| Command | `commands/` | On explicit invocation | Near zero | No — it is a user-triggered prompt |
| Hook | `hooks.json` | Registered at session start, runs on events | Near zero until it fires | Yes — deterministic code, can block |
| MCP server | `.mcp.json` | Server started at session start | Every tool schema, always | Yes — provides tools the model calls |
| LSP server | `lsp.json` | Server started on demand | Near zero | No — it answers code-intelligence queries |

## Choosing between overlapping components

### Skill or agent?

| Question | Skill | Agent |
| --- | --- | --- |
| Does the work need its own context window? | No | Yes |
| Should the main conversation see all intermediate output? | Yes | No |
| Does it need a *restricted* tool set for safety? | No | Yes |
| Is it a procedure the current agent should follow? | Yes | No |
| Is it long-running and self-contained? | No | Yes |

A skill that says "read all 200 files and summarize" should be an agent — it will flood the
main context. An agent that says "here is how we name branches" should be a skill — it needs
no isolation.

### Skill or hook?

| Question | Skill | Hook |
| --- | --- | --- |
| Must it happen *every* time, without the model deciding? | No | Yes |
| Is it a judgment call? | Yes | No |
| Must it be able to block an action? | No | Yes |
| Is it advice? | Yes | No |

"Always run the formatter after editing" is a hook. "Prefer tabs in this repository" is a
skill. A hook is code; a skill is instruction. Instructions can be reasoned around, which is
sometimes correct and sometimes a security hole.

### MCP server or script in a skill?

| Question | Script | MCP server |
| --- | --- | --- |
| Is it one operation used by one skill? | Yes | No |
| Do many workflows need it? | No | Yes |
| Does the model need to discover it without reading a skill first? | No | Yes |
| Is it worth a permanent tool-schema cost in every session? | No | Yes |

Bundling a script inside a skill costs nothing until the skill triggers. An MCP server costs
tokens in every session forever. Start with a script.

## Plugin shapes

### Knowledge plugin

```text
my-plugin/
├── plugin.json
└── skills/
    ├── conventions/SKILL.md
    ├── deployment/SKILL.md
    └── incident-response/SKILL.md
```

Teaches Copilot how an organization works. No executable components, no privileges, no
runtime dependencies. This is the highest-value-per-risk shape and should be the default.

### Workflow plugin

```text
my-plugin/
├── plugin.json
├── skills/
│   └── migration/
│       ├── SKILL.md
│       ├── references/locking.md
│       └── scripts/plan_migration.py
└── agents/
    └── migration-reviewer.agent.md
```

A skill drives the procedure, a bundled script does the deterministic part, and an agent
does an isolated review pass. Everything the plugin needs is inside it.

### Integration plugin

```text
my-plugin/
├── plugin.json
├── .mcp.json
├── skills/
│   └── issue-triage/SKILL.md
└── agents/
    └── triager.agent.md
```

The MCP server supplies tools; the skill teaches Copilot how this organization uses them;
the agent does bulk triage in isolation. The skill is what makes the raw tools useful — an
MCP server alone gives capability without judgment.

### Guardrail plugin

```text
my-plugin/
├── plugin.json
├── hooks/hooks.json
└── scripts/
    ├── block-prod-writes.sh
    └── audit.py
```

Enforces policy deterministically. Install this deliberately and organization-wide, not
casually — every hook runs in every session of every installing user.

### Language-support plugin

```text
my-plugin/
├── plugin.json
├── lsp.json
├── scripts/launch-server.sh
└── skills/
    └── language-conventions/SKILL.md
```

The LSP server supplies code intelligence; the skill supplies the conventions the language
server cannot know.

## Composition rules

1. **A component may reference a sibling component by name, but not import its files.**
   Skills bundle their own scripts. Two skills that need the same script get one copy each,
   or the script moves to an MCP server.
2. **Agents do not inherit the session's skills.** An agent gets its own context. If an
   agent must follow a procedure, put the procedure in the agent's prompt, not in a skill
   and hope.
3. **Hooks cannot call skills.** Hooks are code that runs outside the model loop, except for
   `sessionStart` `prompt` entries, which inject text.
4. **MCP server names are global and last-wins.** Namespace them.
5. **Skill names are global and first-wins, with plugins last.** Namespace them too, but
   for the opposite reason — you will lose the conflict, not win it. Two plugins sharing a
   skill name both survive under `/plugin-name:skill-name`; a project or personal skill
   with the same name shadows yours outright.
6. **Agent IDs are not global.** A plugin's agents are namespaced as
   `<plugin-name>:<agent-id>`, so they can neither shadow nor be shadowed. Prefixing agent
   filenames is a readability choice, not a collision defense.

## Cost model

Every session pays for a plugin before the user types anything:

| Item | Approximate cost |
| --- | --- |
| One skill description | 50–150 tokens |
| One agent description | 50–150 tokens |
| One MCP tool schema | 100–500 tokens |
| One MCP server with 20 tools | 2,000–10,000 tokens |
| A hook that never fires | 0 tokens |
| An LSP server | 0 tokens until queried |

A plugin bundling a 40-tool MCP server can consume more context than every skill in the
plugin combined. If only three of those tools matter, say so in the plugin README and
restrict the agents that use them with the `tools` frontmatter field.

Budget rule of thumb: a plugin should cost under 2,000 tokens of always-on context. If it
costs more, split it so users can install only what they need.
