---
name: polaris-automations
description: "Configures Polaris automations (alert rules) and explains why one did or did not fire. Produces a rule body for POST /api/v1/automations plus a walkthrough of the seven-step Automations wizard, using the server's own field names: triggers (asset metric, asset state, Path Monitor, host metric, event, change, composite AND/OR), holds counted in polls (forPolls, 'sustained for N polls'), windows and poll groups (windowSec / windowPolls), count windows, dimension filters, severity bands and bandNotify, reset / clear / resetActions, notify / api_call / script / event / reboot actions, recipients and channels, escalation tiers, reminders / repeat, quiet time, maintenance windows, dependency suppression, down detection (monitorStatus == down, missedPolls, passive), precedence and carve-out. Load when someone asks to create or edit an automation or alert rule, 'alert me when X', 'why didn't my automation fire', 'why did it fire', for escalation, reminders, quiet time, maintenance or Dep. Down behaviour, for automation JSON, or for POST/PUT /automations, /automations/preview or /automations/schema."
---

# Polaris automations

An **automation** is the whole unit: which devices, what to watch, at what severity, what
to do about it, and when it resets. This skill produces one that is **correct about what the
engine will actually do**, or explains why an existing one fired, or did not fire.

Script actions (what a script receives when it runs, its args template, the registry entry)
belong to the sibling skill **`polaris-automation-scripts`**. Load that one for the script itself.
This skill only wires the `script` action into a rule.

## A deliverable is three things, not one

| # | What | Why |
|---|---|---|
| 1 | **The rule body** as JSON, valid against the server schema, with `"enabled": false` | the API path: `POST /api/v1/automations`; and what *View code* in the UI shows |
| 2 | **The wizard walkthrough**: step by step, using the on-screen names (Devices, Trigger, Reset, Actions, Quiet time, Summary) | most operators build in the UI, and the field names differ from the JSON keys |
| 3 | **The dry run**: the `POST /automations/preview` body and what to look for in the answer (`meetsCount`, `carveOut`) | it shows the devices covered and how many readings meet the trigger now, without writing anything |

If the question is "why did / didn't it fire", the deliverable is a diagnosis instead: walk
the checklist in [references/scope-and-coverage.md](references/scope-and-coverage.md#why-didnt-it-fire)
and name the gate that applied.

## Which file

| You need… | Read |
|---|---|
| every top-level field, its default, and what omitting it does (PUT is a full replace) | [references/rule-model.md](references/rule-model.md) |
| trigger types, every metric / state field / change type, comparators, aggregations, `forPolls` vs `windowSec` vs `windowPolls`, dimension filters, composites, `missedPolls` | [references/triggers-and-conditions.md](references/triggers-and-conditions.md) |
| scope / device filters, the monitored gate, precedence and carve-out, maintenance, dependency suppression, down detection, the "why didn't it fire" checklist | [references/scope-and-coverage.md](references/scope-and-coverage.md) |
| actions, recipients, channels, reset and `resetActions`, severity bands and `bandNotify`, escalation, repeat, quiet time | [references/actions-escalation-repeat.md](references/actions-escalation-repeat.md) |
| what to hand the user: API sequence, wizard steps, preview, schema, permissions, testing | [references/delivery.md](references/delivery.md) |
| worked rules: device down, CPU high, interface errors, interface down, sensor alarm, storage days-until-full, state probe, event pattern, composite AND | [references/recipes.md](references/recipes.md) |

## The twelve things that are always true

1. **A `monitorStatus == down` automation *defines* down.** Its `trigger.missedPolls` is the
   number of missed polls that makes its devices go Down (rule 36). A device that no such
   automation covers reads **`passive`** and is never declared down. Creating, narrowing,
   disabling or deleting one changes down detection for real devices.
2. **Only monitored, unsuppressed devices alert** (rule 37). The device must be `monitored`
   and must not be in a maintenance window or dependency-suppressed. Un-monitoring a device
   clears its live alerts. This one gate applies to every trigger type, event triggers included.
3. **Holds are counted in readings, not seconds.** Write `forPolls` on the trigger and
   `reset.sustainPolls` on the reset. The engine ticks every 60 s but counts consecutive
   qualifying *readings*, so one 5-minute poll is one reading, not five. `forDurationSec` /
   `sustainSec` are wall-clock mirrors. Write them only if a rule must stay time-based.
4. **A time window and a poll group are different things.** `windowSec` takes whatever
   samples landed in that time. `windowPolls` is a **Poll Group Size**: non-overlapping groups of
   N readings, and then `forPolls` counts **groups** (rule 66). Either one needs an aggregation
   other than `latest`.
5. **`scope: {}` selects no devices for a device trigger.** For device triggers, write
   `{"allAssets": true}` or a condition tree. On an event trigger, a bare `{}` means "any device".
   See [scope-and-coverage.md](references/scope-and-coverage.md#scope-shapes).
6. **The more specific automation wins, and same-rank ties both fire** (rule 18). Two
   automations with the same trigger signature carve devices out by rank: All assets < Device type < OS <
   Manufacturer < Model < Tag < Region < IP block < Subnet < Hostname. The lower one's alert is
   cleared as *superseded*. Event and change triggers are exempt.
7. **Omitted fields take defaults, and some defaults change behaviour.** `enabled` defaults to
   `true`. `severity` defaults to `warning`. An absent `reset` means **`manual`**: the alert never
   clears on its own. Unknown trigger and top-level keys are **dropped without an error**. Action
   objects are strict and return a 400 for unknown keys.
8. **PUT replaces the whole rule.** Read the rule, change it, and send all of it back. If you
   delete `enabled`, a disabled rule goes live. If you delete `reset`, the rule becomes manual-clear.
9. **Pinned components gate everything dimensioned** (rule 57). Interface, IPsec tunnel and similar conditions
   read only pinned members. An unpinned port never alerts, however the rule is written. The one exception is
   `poeStatus == fault`, which covers every PoE port.
10. **A device that goes down takes its other alerts with it** (rule 29). Its open CPU,
    interface, sensor and SD-WAN alerts clear as *superseded* without sending "resolved". Nothing new fires
    about the device while it is down.
11. **Maintenance pauses alerts; quiet time holds messages.** A maintenance window stops polling, clears
    device-down alerts, and pauses every other open alert (rule 16). Quiet time still raises
    the alert, but holds the emails and pushes, then sends a summary when it ends (rule 92).
12. **Two action types need a second permission.** A `script` action needs
    `automationScripts:write`. A `reboot` action needs `assets:write`. Everything else needs
    `automationManagement:write`. A test delivery is session-only and returns 401 to a bearer token.

## Emitting the answer

Lead with the rule JSON in one fenced block, with `"enabled": false`. Replace every
placeholder (`<email-channel-id>`, `<asset-type>`, `<recipient@example.com>`, …) before
posting. A placeholder address fails the email check, and the 400 names the field. Next, give
the wizard walkthrough as a numbered list keyed to the seven step names. Then give the preview
body and say what a healthy answer looks like. End with one line on what the operator will
see when it fires (severity, who is told, when it clears).

Close with two reminders, every time:

- **A human must review an automation before it is enabled in production.** That means its
  devices, threshold, hold, recipients and reset. Enable it from the list's toggle once the preview looks right.
- If the rule is, or replaces, a **`monitorStatus == down`** automation, say so plainly. It
  changes how and when its devices are declared Down, including which devices become
  `passive`. Check `GET /automations/:id/removal-impact` before you disable or delete one.

If the request touches deployed code, external webhooks or customer-facing wording, add that
it needs human review before use. Never put a real token, hostname, address or device name
into a rule you emit.
