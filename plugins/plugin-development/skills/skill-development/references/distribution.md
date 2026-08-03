# Distributing a skill

## Contents

- [Choosing a distribution channel](#choosing-a-distribution-channel)
- [Project skills](#project-skills)
- [Personal skills](#personal-skills)
- [Plugin skills](#plugin-skills)
- [Precedence and name collisions](#precedence-and-name-collisions)
- [Installing a skill someone else wrote](#installing-a-skill-someone-else-wrote)
- [Managing installed skills](#managing-installed-skills)
- [Versioning](#versioning)

## Choosing a distribution channel

| Channel | Location | Use when |
| --- | --- | --- |
| Project | `.github/skills/NAME/` in the repository | The skill only makes sense for this codebase, and everyone working in it should get it |
| Personal | `~/.copilot/skills/NAME/` | It encodes your own habits and should follow you between projects |
| Plugin | `skills/NAME/` inside a plugin | It should be installable, versioned, updatable, and shared with people outside one repository |

Rule of thumb: start as a project or personal skill while iterating, and promote it into a
plugin once it is stable and someone else wants it.

## Project skills

Commit the skill directory to the repository. Copilot CLI reads project skills from, in
order:

1. `.github/skills/`
2. `.agents/skills/`
3. `.claude/skills/`

Prefer `.github/skills/` — it is the GitHub-native convention and is also read by Copilot
cloud agent and Copilot code review. The other two exist for cross-tool compatibility.

In a monorepo, skills in parent directories are inherited, so a skill at the repository
root applies to every package beneath it.

## Personal skills

Place the directory in `~/.copilot/skills/NAME/` (or `~/.agents/skills/NAME/`). If
`COPILOT_HOME` is set, use `$COPILOT_HOME/skills/`.

Personal skills apply to every session on that machine, so keep them genuinely general.
A personal skill that assumes one repository's layout will misfire everywhere else.

## Plugin skills

Put the skill in a plugin's `skills/` directory:

```text
my-plugin/
├── plugin.json
└── skills/
    ├── skill-one/SKILL.md
    └── skill-two/SKILL.md
```

`plugin.json` does not need to list them — `skills/` is the default location. Override it
only to use a different directory or several:

```json
{ "skills": ["skills/", "extra-skills/"] }
```

Install locally while developing:

```bash
copilot plugin install ./my-plugin
```

Plugin components are **cached at install time**. After editing a skill, run the same
install command again to refresh the cache; `/skills reload` alone will not pick up a
change to an installed plugin's files.

## Precedence and name collisions

Skills are deduplicated by their frontmatter `name`, and the **first one found wins**:

```text
1. <project>/.github/skills/
2. <project>/.agents/skills/
3. <project>/.claude/skills/
4. <parents>/.github/skills/ ...      (inherited)
5. ~/.copilot/skills/
6. ~/.agents/skills/
7. plugin skills/ directories
8. COPILOT_SKILLS_DIRS and config
```

Because plugin skills load last, a project or personal skill with the same name silently
suppresses the plugin's version. Two practical consequences:

- **When publishing a plugin**, choose distinctive skill names. `deploy` will be shadowed
  in half the repositories that install it; `acme-deploy` will not.
- **When debugging "my skill changed behavior"**, run `/skills info NAME` to see which
  copy actually loaded.

## Installing a skill someone else wrote

```bash
# From a local directory — registers the directory as a skill source
copilot skill add ./downloaded-skill

# From a file or URL — copies the skill into your personal skills directory
copilot skill add https://example.com/skill.md

# Scope a file or URL install to the current repository instead of your user account
copilot skill add ./skill.md --project
```

Installing a **directory** registers it as a custom skill source in place. Installing a
**file or URL** materializes the content into `~/.copilot/skills/<name>/SKILL.md` (or
`.github/skills/` with `--project`). The name comes from the frontmatter `name` field,
falling back to one inferred from the file or URL.

Alternatively, copy the skill directory into `.github/skills/` or `~/.copilot/skills/`
yourself and run `/skills reload`.

Review a third-party skill before installing it, especially its bundled scripts and any
`allowed-tools: shell` in the frontmatter. A skill is executable content.

## Managing installed skills

| Task | In a session | From the terminal |
| --- | --- | --- |
| List | `/skills list` | `copilot skill list` |
| Details and location | `/skills info NAME` | `copilot skill list --json` |
| Enable / disable | `/skills` then toggle | `copilot plugins enable NAME --skill` |
| Add a source directory | `/skills add` | `copilot skill add DIR` |
| Reload after editing | `/skills reload` | restart the session |
| Remove | — | `copilot skill remove NAME` |

The `copilot plugins` (plural) command family is gated and prints *"The plugins command is
not available"* in some builds. The singular `copilot plugin list` and `copilot skill list`
are the reliable terminal commands; prefer them in anything you document for users.

Skills provided by a plugin cannot be removed with `--skill`; disable them, or manage the
plugin itself.

## Versioning

Skills have no version field of their own. Version the unit that ships them:

- **Plugin skills** — bump `version` in `plugin.json` and in the marketplace entry.
  Semantic versioning applies to observable behavior: a changed description that alters
  triggering is a minor bump; a removed capability or renamed skill is a major bump.
- **Project skills** — Git history is the version. Note behavior changes in the pull
  request description.
- **Renaming a skill** is a breaking change: anyone invoking `/old-name` loses it, and any
  documentation referring to it goes stale.
