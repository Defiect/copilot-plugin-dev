# Repository layouts for plugin marketplaces

## Contents

- [Single-plugin-at-root](#single-plugin-at-root)
- [Monorepo with `plugins/`](#monorepo-with-plugins)
- [Index-only marketplace](#index-only-marketplace)
- [Choosing a layout](#choosing-a-layout)

## Single-plugin-at-root

Use this layout when one repository exists only to ship one plugin.

```text
my-plugin-repo/
├── .github/
│   └── plugin/
│       └── marketplace.json
├── plugin.json
├── skills/
│   └── deploy/
│       └── SKILL.md
├── agents/
│   └── reviewer.agent.md
├── README.md
└── LICENSE
```

Matching marketplace manifest:

```json
{
  "name": "my-plugin-marketplace",
  "owner": { "name": "Example Team", "email": "plugins@example.com" },
  "metadata": {
    "description": "Marketplace for the my-plugin Copilot CLI plugin",
    "version": "1.0.0"
  },
  "plugins": [
    {
      "name": "my-plugin",
      "description": "Provides deployment and review helpers for Example Team projects.",
      "version": "1.0.0",
      "source": "."
    }
  ]
}
```

| Pros | Cons |
| --- | --- |
| Smallest repository shape | Does not scale to many plugins |
| Easy direct install with `copilot plugin install OWNER/REPO` | Marketplace and plugin versioning are tightly coupled |
| Few relative paths to get wrong | Harder to share scripts across plugins |

## Monorepo with `plugins/`

Use this layout when one team publishes several related plugins. This repository uses the
same pattern.

```text
copilot-dev-marketplace/
├── .github/
│   └── plugin/
│       └── marketplace.json
├── plugins/
│   ├── plugin-development/
│   │   ├── plugin.json
│   │   └── skills/
│   │       └── skill-development/
│   │           └── SKILL.md
│   └── testing-tools/
│       ├── plugin.json
│       └── skills/
│           └── plugin-testing/
│               └── SKILL.md
├── README.md
└── LICENSE
```

Matching marketplace manifest:

```json
{
  "name": "team-copilot-marketplace",
  "owner": { "name": "Example Team", "email": "plugins@example.com" },
  "metadata": {
    "description": "Curated Copilot CLI plugins for Example Team",
    "version": "1.0.0",
    "pluginRoot": "plugins"
  },
  "plugins": [
    {
      "name": "plugin-development",
      "description": "Build, validate, test, and publish GitHub Copilot CLI plugins.",
      "version": "1.0.0",
      "source": "./plugins/plugin-development"
    },
    {
      "name": "testing-tools",
      "description": "Verify plugin installs, runtime loading, and component behavior.",
      "version": "1.0.0",
      "source": "./plugins/testing-tools"
    }
  ]
}
```

| Pros | Cons |
| --- | --- |
| Scales to several plugins | Requires path validation for every entry |
| Keeps one marketplace catalog and release process | Repository tags may cover more than one plugin |
| Allows shared repository-level docs and CI | Contributors must avoid skill-directory changelogs |

## Index-only marketplace

Use this layout when the marketplace only indexes plugins hosted elsewhere.

```text
copilot-plugin-index/
├── .github/
│   └── plugin/
│       └── marketplace.json
├── README.md
└── LICENSE
```

Matching marketplace manifest:

```json
{
  "name": "copilot-plugin-index",
  "owner": { "name": "Example Curators", "email": "plugins@example.com" },
  "metadata": {
    "description": "Curated external Copilot CLI plugins",
    "version": "1.0.0"
  },
  "plugins": [
    {
      "name": "review-helper",
      "description": "Adds code review skills and agents for Example projects.",
      "version": "2.1.0",
      "source": {
        "source": "github",
        "repo": "example/review-helper",
        "ref": "v2.1.0",
        "path": "."
      }
    },
    {
      "name": "audited-tools",
      "description": "Pins audited scripts and skills for regulated deployments.",
      "version": "1.0.3",
      "source": {
        "source": "github",
        "repo": "example/audited-tools",
        "sha": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
        "path": "plugins/audited-tools"
      }
    }
  ]
}
```

| Pros | Cons |
| --- | --- |
| Keeps the catalog small | Cannot validate remote plugin files from a local checkout |
| Allows independent plugin repositories and release cadences | Requires disciplined tag or SHA pinning |
| Good for curated third-party catalogs | Users trust both the index and external repositories |

## Choosing a layout

| Situation | Choose |
| --- | --- |
| One plugin, one repository, simple release process | Single-plugin-at-root |
| Several related plugins owned by one team | Monorepo with `plugins/` |
| Curating plugins owned by other repositories | Index-only marketplace |

Prefer monorepo with `plugins/` when starting a team marketplace. It keeps validation and
release automation simple while leaving room for more plugins.
