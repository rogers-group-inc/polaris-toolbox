# polaris-toolbox

A Claude Code plugin for working **with** a [Polaris](https://github.com/rogers-group-inc/polaris)
install — the monitoring and asset management application — from the outside: calling its API,
teaching it a new vendor, configuring its alerting, and scripting its automations. It replaces
the separate `polaris-api-conventions` and `polaris-automation` plugins (their history is in
this repository).

## Skills

| Skill | Use it to |
|---|---|
| **`polaris-api`** | call the REST API (`/api/v1`): tokens and roles, errors, assets and onboarding, IPAM, the SIEM quarantine flow, Path Monitor, automations, the MIB Database, manufacturer profiles, the audit tail. Generated from the in-app developer page (`/api`) — never edited by hand. |
| **`polaris-manufacturer-profiles`** | turn a vendor's MIBs into a manufacturer profile: which object is CPU, memory, a sensor table, storage, the model; per-family rows; custom widgets and state probes. Delivered as an importable profile file, with a library of profiles under `profiles/`. |
| **`polaris-automations`** | build or fix an alert rule — triggers, holds counted in polls, scope, down detection, suppression, actions, escalation, quiet time — or explain why one did or did not fire. Every recipe is validated against a running Polaris. |
| **`polaris-automation-scripts`** | write a script for an automation's script action: what it receives, where it runs, and how to make it safe to run twice. |

The skills load on their own when a task matches. Invoke one by hand with
`/polaris-toolbox:<skill>`.

## Scripts

Python 3.8+, standard library only. Each takes `--url` / `POLARIS_URL`, a token in
`POLARIS_TOKEN` or `--token-file`, and `--insecure` for a self-signed lab certificate.
Create the token under **Server Settings → API Tokens**, bound to a role with only what the
script needs (each script's `--help` says which).

| Script | Does |
|---|---|
| `scripts/apply-profile.py` | uploads the MIBs a profile file needs, previews and imports the file, reports readiness |
| `scripts/export-profiles.py` | writes profiles as files (no ids, secrets or MIB text); `--tested-on` records provenance |
| `scripts/apply-automation.py` | previews and creates (or `--update`s) rules from JSON bodies |
| `scripts/export-automations.py` | writes rule bodies with recipients replaced by placeholders and headers masked |
| `scripts/import-api-html.mjs` | regenerates `skills/polaris-api/references/` from a Polaris checkout's `public/api.html` |

## Use it

```
git clone https://github.com/rogers-group-inc/polaris-toolbox.git
claude --plugin-dir <path-to-clone>/polaris-toolbox
```

`git pull` in the clone picks up a new version (`version` in `.claude-plugin/plugin.json`).

## Keeping it current

This repository is fed from Polaris commits, not edited on its own schedule. Polaris's
`/polaris-docs-sync` routing table says when a change there must be recorded here:

- a change to `public/api.html` → `node scripts/import-api-html.mjs <polaris>/public/api.html`
  (Polaris's `check:docs` warns when `sourceApiHtmlSha256` no longer matches the page);
- a change to manufacturer profiles, MIB resolution or the profile file format →
  `skills/polaris-manufacturer-profiles/`;
- a change to the automation rule schema, the engine's gates, or the wizard →
  `skills/polaris-automations/`;
- a change to the script runner, its `{token}` vocabulary or the agent's script executor →
  `skills/polaris-automation-scripts/`.

Bump `version` with each change.

## Scope and safety

Application behaviour only: no install's hostnames, tokens, device names or people, and no
vendor MIB text (a vendor's copyright — each profile names the modules to download). Anything
these skills produce that will run in production — a profile, an automation, a script — must
be reviewed by a person and tried on one device before it is relied on.

## Licence

AGPL-3.0-only, the same as Polaris.
