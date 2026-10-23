# Actions, recipients, reset, bands, escalation, reminders, quiet time

Wizard step **5 — Actions** is a stack of cards: the mandatory **In-app Alert** (the message
template), the **Require Acknowledgement** row, the **Dependency-Down Bypass** row (down
automations only), then, per severity, the **Trigger Action** list with its
**+ Escalation Action** chain, and last the **Reset Action** list. Step **4 — Reset** decides
when the alert ends. Step **6 — Quiet time** decides when nobody is told.

## Action types

| `type` | Fields (required **bold**) | Notes |
|---|---|---|
| `notify` | **`channelId`**, `channelIds` (1–10), recipients…, `respectUserPreference`, `emailComposition`, `repeat`, `escalation` | sends through delivery channels |
| `api_call` | **`url`** (http/https, ≤ 2000, no `{tokens}`), `method` (`GET` `POST` `PUT` `PATCH` `DELETE`, default `POST`), `headers` (≤ 20; names 1–100, values ≤ 1000), `bodyTemplate` (≤ 10 000, `{tokens}`), `timeoutSec` (1–60, default 15) | loopback, link-local and metadata hosts are refused |
| `script` | **`scriptId`**, **`runOn`** (`server` \| `agent`), `argsTemplate` (≤ 2000), `timeoutSec` (1–600) | needs `automationScripts:write`. The script must exist, be enabled and allow that `runOn`. For the script itself, see **`polaris-automation-scripts`** |
| `event` | — | writes the `notification.triggered` audit Event. A no-op on event and change triggers |
| `reboot` | `when` (`at` default \| `now`), `at` (`HH:MM` server time, default `02:00`), recipients…, `cc`, `bcc`, `minGapHours` (1–720, default 24) | needs `assets:write`. **Books** a reboot, never sends one inline (rule 115) |

Where actions may go: `actions` (≤ 20), `severityBands[i].actions` (≤ 20), escalation tiers
(≤ 10 per tier), `resetActions` (≤ 20), `bandNotify.resolvedActions` (≤ 20). Only the first two
take a per-action `escalation`, and only a `notify` in those two takes `repeat`.

- **`api_call` headers are secrets** (rule 114). They are sealed at rest and masked in every response
  and in View code. A masked value is restored only while the URL is unchanged. **Export drops `api_call`
  actions entirely.** Do not put a real token in an example. Use a placeholder and tell the
  operator to type the value into the wizard.
- **`reboot`** cannot go on `resetActions` or `resolvedActions` (a recovery is no reason to
  reboot). It needs at least one To recipient for the results email. It is skipped, with an
  `asset.reboot_automation_skipped` Event, when a booking is already pending or the device rebooted
  within `minGapHours`. A device that is not allowed to reboot (no opt-in, an HA FortiGate) records an
  `automation.action_error`. Tests and Export never run or carry it.
- `api_call` and `script` run **once**, when the alert first fires (and in a tier that names them).
  Reminders re-send `notify` only.

## Notify: channels and recipients

Channel ids come from `GET /delivery-channels`. Types: `smtp`, `oauth_m365` (email), `web_push`
(one per install), `slack`, `teams` (webhook), `pushbullet`. **Only email and Web Push route
to recipients.** Slack, Teams and Pushbullet post to their own fixed destination and ignore recipient fields.

`channelIds` lets one action deliver through several channels ("email **and** push"). When it is
present, `channelId` **must equal `channelIds[0]`**, and no channel may repeat.

| Recipient key | Reaches | Wizard pill |
|---|---|---|
| `addresses: [email]` (≤ 100) | that mailbox, email only | Address |
| `recipientUserIds: [id]` | those accounts (email or push) | User. Ids come from `GET /automations/recipient-users` |
| `recipientRoles: [roleId]` | every user holding the role. **Role ids, not names** | Role |
| `recipientRegions: [name]` | users tagged with the named map regions (bare names, no `region:` prefix) | Region |
| `recipientTags: [name]` | users whose tag scope carries a registry tag | Tag |
| `recipientDeviceRegion: true` | users of the **triggering device's** regions, any level | Asset's Region Users (To only) |
| `recipientDeviceRegionLevels: [1..8]` | the device's region at that level, counted outward: 1 = its own innermost, 2 = the division above | Asset's L*n* Region Users (To only) |
| `recipientAssetContacts: true` | address-book contacts whose device filter covers the device, email only | Asset's Responsible Contacts (To only) |
| `recipientAllUsers` / `recipientAllRegions: true` | broadcasts, **Web Push only** (refused without a push channel) | Send to All Users / All User Regions |

- `respectUserPreference: true` (**Only use the channel matching the user's preferred notification method**,
  rule 39) applies only when the action offers both email and push. It filters accounts only,
  and never drops an alert: someone who prefers push but has no device still gets the email.
- Cc / Bcc live in `emailComposition.cc` / `.bcc` (`recipientUserIds`, `addresses`,
  `recipientRoles`, `recipientRegions`, `recipientTags`). The wizard refuses an action whose
  only recipients are in Cc / Bcc. `{email.recipients}` never names a Bcc (rule 60).
- One notify action sends **one email** with everyone on the To line, timestamps in the
  server's time zone, and one Acknowledge link for everyone (rule 25).
- An orphaned `region:` tag on a device makes level routing reach **nobody** for that device
  (rule 58). The other recipient keys on the same action still resolve.
- `emailComposition` on a notify: `subjectTemplate` (≤ 500), `bodyTextTemplate` (≤ 10 000),
  `bodyHtmlTemplate` (≤ 20 000), `cc`, `bcc`. Leave it `null` to keep following the shared default email.

Template tokens (message template, email, `api_call` body, script args) include `{asset}`,
`{metric.label}`, `{value.display}`, `{threshold.display}`, `{dimension}`, `{severity}`,
`{rule}`, `{time}`, `{link}`, `{ack}`, `{asset.ip}`, `{event.action}`, `{escalation.tier}`,
`{repeat.attempt}`. The full catalogue is `GET /automations/schema` → `templateVariables`.
`{link}`, `{ack}` and `{asset.link}` are empty when the install has no public URL set.

## One alert per device (`groupByAsset`)

**Raise one alert per device, not one per interface** (the noun follows the trigger). It is valid
only on a per-component trigger (interfaces, PoE ports, mounts, sensors, tunnels, SD-WAN members),
and refused on composite, host, event, change and device-wide fields (rule 75). The first email waits
one polling interval. One acknowledgement covers every component. The alert stays up until the last
component recovers, and a newly failing component re-opens an acknowledged alert with an
`[UPDATED …]` email. Turning it on or off ends the rule's live alerts.

**Alert groups** (the Automations → **Alert Groups** tab) fold several automations into one
alert. While a rule is in a group, **the group's recipients and escalation are used, not the
rule's own**. Event and change rules cannot join. Check for group membership before
diagnosing "the wrong people were told".

## Reset and the Reset Action list

- Step 4's default-checked **Reset when the trigger is no longer true** is `reset.mode: "auto"`.
  Untick it for **Custom conditions** (`condition`), timed, or manual. Event and change rules get
  **When a matching event arrives** (`event`). Modes and limits are in
  [rule-model.md](rule-model.md#reset-modes).
- `resetActions` run when the alert **ends**: an auto, timed, condition or event reset, or an
  operator clear. They are how recovery gets announced. In the wizard, adding a Notify to the trigger list
  puts a matching one in **Reset Action**, which follows it until you edit it. Over the API you must write
  `resetActions` yourself. Without them a recovery is silent: the alert resolves, and
  `notification.auto_cleared` is logged.
- Not "recovered", so **no** reset actions: superseded by a down device or by a more specific rule,
  cleared by a maintenance window (device-down), out of scope.

## Severity bands

**Use multiple severity levels** → **+ Severity**. Each band is a higher severity at its own
threshold (up to 4 bands above the base). One alert **climbs and eases in place** rather than
firing several. De-escalation is immediate, and the hysteresis dead band eases it to the base.
Bands share the trigger's metric, aggregation, window and dimension filter, and inherit its hold.

**Use different actions for each severity level** lets each band have its own `actions`,
`escalation` and `followUp.requireAckNote` (rule 56: the note requirement is per severity).
A band with no actions runs the base actions. `bandNotify` decides which transitions notify:
by default it notifies on increase and on resolve, not on decrease. The all-clear either reuses
the last band's actions (`resolvedMode: "reuse"`) or runs `resolvedActions` (`"dedicated"`).

## Escalation

*"If this stays unhandled, who else should hear?"* Escalation belongs to a **severity**, not to an action:
`escalation` is the base severity's chain, and `severityBands[i].escalation` is that band's.

- Each tier (**+ Escalation Action**, up to 5): **Escalate after N minutes unhandled**
  (`afterMin`, measured from the fire, up to a week), a full action list, and an optional **Repeat
  every … min, max …** (`repeatEveryMin` ≥ 5, `maxRepeats` 1–20).
- **Stop escalating when**: `stopOn: "acknowledge"` (*Acknowledged (or cleared)*, the default) or
  `"clear"` (*Cleared only*).
- The pattern to reach for: the trigger notifies `recipientDeviceRegionLevels: [1]` (the site's
  people), and tier 1 after 15 minutes notifies `recipientDeviceRegionLevels: [2]` (the division).
- A tier may hold a `reboot` ("nobody acknowledged the memory alert in 30 minutes, reboot it").

## Reminders (`repeat`)

*"How often should this delivery chase?"* **Repeat this action** at the foot of a notify row:
`{ "everyMin": 15, "stopOn": "acknowledge", "stopAfterHours": null }`. It belongs to the **action**
(rule 56), so "page the on-call every 5 minutes, leave the digest alone" is two notify actions
with different `repeat` values. It is offered on firing lists only, never on reset actions or tiers.
Absent means inherit the rule-level `repeat`. `null` means do not repeat.

## Quiet time

Quiet time never drops an alert (rule 92). The alert is raised, shows a **QUIET** pill, writes its
audit event, and scripts and API calls still run. What is held is the **people-facing sends**, and a
**summary email** goes out when the quiet period ends (or at `summaryAt`). It lists what is still outstanding,
what recurred, and what was sent live. Held means held, never skipped (rule 44).

Step 6 choices: **Off** (`quietTime: null`, the global quiet times apply), **Ignore Global Quiet Time**
(`{ "ignoreGlobal": true }`, the usual choice for critical automations), **Override Global Quiet
Time** (a policy). Global quiet times live in Automations → **Settings** → **Global Quiet Times**.

```json
"quietTime": {
  "windows": [ { "version": 1, "kind": "recurring", "freq": "weekly", "daysOfWeek": [0, 1, 2, 3, 4, 5],
                 "hours": [ { "startTime": "22:00", "endTime": "06:00" } ] },
               { "version": 1, "kind": "recurring", "freq": "weekly", "daysOfWeek": [0, 6] } ],
  "held": { "warning": { "alerts": true, "alertReminders": true, "escalations": true, "escalationReminders": true } },
  "summaryAt": "07:30"
}
```

This is "nights and weekends". The overnight window covers Sunday through Friday, because an
overnight range belongs to the day it **starts**. Without Sunday, Monday 00:00–06:00 would not
be quiet. Friday's 22:00 start runs into Saturday's all-day window, and overlap between
windows is allowed.

- `windows` (1–8) use the maintenance recurrence shapes. `kind: "recurring"` takes `freq`
  `daily` / `weekly` (needs `daysOfWeek`, 0 = Sunday) / `monthly` (`dayOfMonth`) / `yearly`
  (`month`, `day`). Hours go in `hours: [{startTime, endTime}]`, or per day in `hoursByDay`. No hours means
  all day. An end at or before the start runs past midnight. `kind: "oneshot"` takes `startAt` / `endAt`
  as local `YYYY-MM-DDTHH:MM` with no offset.
- Times are **server-local wall clock**. A browser's own clock is the usual trap.
- `held` is per severity, with four booleans: `alerts` (the first send, the one that owes a summary),
  `alertReminders`, `escalations`, `escalationReminders`. A severity with no entry is not held.
- Also available: `summaryChannelId`, `recurrenceThreshold` (1–100), `summaryAlways` (the all-quiet
  email, default on), and `recipients` (**Recipient exceptions…**, rule 120:
  `[{ "address": "<recipient@example.com>", "held": {} }]`, where `{}` means that address ignores the quiet time).
- `stopAfterHours` on a reminder counts quiet time too. Test deliveries are never held.

## What stops a live alert

| Event | Effect |
|---|---|
| Acknowledge | stops escalation and reminders where `stopOn` says so. The alert stays live |
| Clear, or the reset condition becomes true | ends it, runs `resetActions` |
| Leaves scope / stops being monitored | cleared `out_of_scope` |
| Maintenance window opens | device-down alerts cleared. Others paused |
| Device goes down | other alerts superseded (rule 29) |
| Parent genuinely down | retired by dependency suppression (rule 38) |
| More specific rule takes the device | superseded (rule 18) |
| Pin removed | that component's alert clears (rule 57) |
| Quiet period | **nothing**: it holds sends, not alerts |
