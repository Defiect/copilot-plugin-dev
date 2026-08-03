# Plugin quality evaluation

## Contents

- [Quality is behavior](#quality-is-behavior)
- [Trigger reliability](#trigger-reliability)
- [Context cost](#context-cost)
- [Component value](#component-value)
- [False-trigger testing](#false-trigger-testing)
- [Scoring rubric](#scoring-rubric)

## Quality is behavior

A valid plugin can still be a bad plugin. Evaluate whether each component makes Copilot
more reliable, cheaper, or safer than the baseline. Delete components that do not earn
their context and maintenance cost.

## Trigger reliability

Measure skill triggering with a small evaluation set:

1. **Write 3-5 positive prompts.** Use realistic user wording and avoid the skill name.
2. **Write 2-3 near-miss prompts.** These should not trigger the skill.
3. **Run each prompt in a fresh session.** Record whether the skill triggered and whether
   the first action matched the skill's workflow.
4. **Calculate reliability.** Positive reliability is `triggered positives / total positives`.
   False-trigger rate is `triggered near-misses / total near-misses`.
5. **Iterate on descriptions.** Change one description at a time and rerun every prompt.

Target 80% or better positive reliability and 0 false triggers before publishing.

## Context cost

Only skill names and descriptions are always loaded, but every installed skill pays that
cost. Keep descriptions between 100 and 500 characters, remove duplicated nouns, and add
only trigger phrases that improve measured reliability.

Audit cost with this table:

| Component | Always-loaded text | Runtime-loaded text | Keep? |
| --- | --- | --- | --- |
| Skill | `name` + `description` | `SKILL.md` body on trigger | Yes/No |
| Agent | Agent description | Agent prompt on delegation | Yes/No |
| MCP server | Tool names and schemas when tools load | Tool results | Yes/No |
| Hook | None in prompt, but runtime risk | Command or prompt behavior | Yes/No |

## Component value

Each component needs a reason to exist:

| Component | Earns its place when | Delete or merge when |
| --- | --- | --- |
| Skill | It changes decisions for a specific recurring task | The body restates general knowledge |
| Agent | It needs a distinct role, tool set, or context window | It is just a long skill body |
| Hook | It enforces or records an event reliably | It surprises users or blocks normal work |
| MCP server | It exposes external state Copilot cannot otherwise access | The same task is a simple script |
| LSP server | It improves code intelligence for a language in the plugin's scope | It duplicates built-in language support |

## False-trigger testing

False triggers waste context and can steer Copilot into the wrong workflow. For each skill,
write prompts that share vocabulary but should not load it. Example:

| Skill | Should trigger | Should not trigger |
| --- | --- | --- |
| `marketplace-development` | `add my plugin to a marketplace` | `open the GitHub marketplace website` |
| `plugin-testing` | `my skill isn't loading` | `write unit tests for this Python module` |

If a near-miss triggers, narrow the description and add a boundary clause.

## Scoring rubric

Score each plugin out of 20 before release.

| Area | 0 points | 1 point | 2 points | 3 points | 4 points |
| --- | --- | --- | --- | --- | --- |
| Static validity | Fails parse or schema checks | Installs only with warnings ignored | Validates with warnings | Validates cleanly | Validates cleanly in CI and locally |
| Runtime loading | Components absent | Some components appear | All appear but not tested | All appear and explicit tests pass | All appear, explicit and natural tests pass |
| Trigger reliability | Not measured | Under 50% | 50-79% | 80-94% | 95%+ with zero false triggers |
| Context efficiency | Bloated and duplicated | Long descriptions and unused files | Some duplication remains | Descriptions are concise | Every component earns its cost |
| Release readiness | No versioning | Partial versioning | Versioned but no changelog | Versioned with release notes | Versioned, tagged, changeloged, and rollback documented |

Publish only at 16 or above, with no zero-point category.
