# The rule model: every top-level field

The body `POST /api/v1/automations` and `PUT /api/v1/automations/:id` accept. Field names
and limits come from the server's rule input schema. The response is `{ rule }`: the
stored, normalized body plus `id`, `createdAt`, `updatedAt`.

## Parsing behaviour you must know first

- **The top level and the trigger objects are not strict.** An unknown or misspelled key
  (`forPoll`, `missedPoll`, `holdPolls`) is **dropped without an error**. The rule saves, and the
  setting you meant does not exist. Re-read the saved rule (`GET /automations`) and check
  that every key you sent came back.
- **Action objects, `scope`, `reset`, `dimensionFilter`, escalation, bands, quiet time and
  email composition are strict.** An unknown key there is a 400 that names the path.
- **Legacy fields still parse.** `clearBehavior`, `clearAfterSec` and `targets` are folded into
  `reset` and `actions` (the v2 fields win when both are sent). Never write the legacy fields. Some
  readers still see them mirrored on stored rows.

## Fields

| Field | Type / limits | Default when omitted | Notes |
|---|---|---|---|
| `name` | string 1–200 | required | the alert names the automation |
| `description` | string ≤ 4000, nullable | `null` | `{rule.description}` in templates |
| `enabled` | boolean | **`true`** | emit `false`; enabling is a human decision (the UI's list toggle) |
| `severity` | `notice` · `informational` · `warning` · `serious` · `critical` | `warning` | with severity bands this is the **base** severity, the lowest tier |
| `trigger` | one of six shapes | required | see [triggers-and-conditions.md](triggers-and-conditions.md) |
| `scope` | device filter object, strict | `{}` | **`{}` selects no devices for a device trigger.** See [scope-and-coverage.md](scope-and-coverage.md#scope-shapes) |
| `reset` | `{ mode, … }`, strict, nullable | **`{ "mode": "manual" }`** | absent means the alert never clears by itself |
| `actions` | ≤ 20 escalatable actions | see below | `notify` · `api_call` · `script` · `event` · `reboot` |
| `resetActions` | ≤ 20 plain actions, nullable | `null` | run when the alert **ends**. No `reboot` here, no per-action escalation or repeat |
| `severityBands` | ≤ 4 bands, nullable | `null` | numeric `asset_metric` / `host_metric` triggers with an ordered operator only |
| `bandNotify` | object, nullable | `null` (defaults apply) | which band transitions notify |
| `escalation` | `{ stopOn, tiers[] }`, nullable | `null` | the chain for the **base** severity. Bands carry their own |
| `repeat` | `{ everyMin, stopOn, stopAfterHours? }`, nullable | `null` | rule-level reminder clock. Prefer per-action `repeat` on a notify |
| `quietTime` | `null` · `{ "ignoreGlobal": true }` · a policy | `null` | `null` = the global quiet times apply |
| `requireAckNote` | boolean | `false` | acknowledging needs a note. Per band: `followUp.requireAckNote` |
| `groupByAsset` | boolean | `false` | one alert per device for per-component triggers (rule 75). Refused elsewhere |
| `messageTemplate` | string ≤ 2000, nullable | `null` | the in-app alert text; `{token}` vocabulary |
| `emailComposition` | `{ subjectTemplate?, bodyTextTemplate?, bodyHtmlTemplate?, cc?, bcc? }`, nullable | `null` | rule-level email override. A notify action's own `emailComposition` wins |
| `cooldownSec` | int 0–2592000, nullable | `null` | the engine skips a re-fire for the same rule, device and component inside this many seconds |
| `channels` | string[] | `["in_app"]` | leave it alone; every fire creates the in-app alert anyway |

### What `actions` defaults to

- **`actions` omitted:** the server adds the audit-Event action (`{ "type": "event" }`) for every
  trigger except `event` and `change`. **No notify is added.** The rule raises an in-app alert
  and writes `notification.triggered`, and nobody is emailed.
- **`actions: []` sent explicitly** is respected: no audit Event is written. That is how an API
  caller opts out of it.
- The **in-app alert is not an action.** Every fire creates one. That cannot be turned off,
  because acknowledge, clear, escalation and delivery all hang off it.
- On `event` / `change` triggers the `event` action is a no-op. An automation that wrote an
  Event on an event trigger would feed its own trigger.

### `reset` modes

| `mode` | Allowed on | Fields | Behaviour |
|---|---|---|---|
| `manual` | any | — | cleared only by an operator |
| `auto` | any | `clearThreshold?`, `sustainPolls?` (0–100), `sustainSec?` | clears when the trigger is no longer true, held for `sustainPolls` readings |
| `timed` | any | `afterSec` (1–2592000) **required** | clears after the time elapses |
| `condition` | `asset_metric`, `asset_state`, `host_metric`, `composite` | `condition` (AND/OR tree, ≤ 3 deep, ≤ 10 leaves) **required**; `sustainPolls?` | while firing, the tree is the **only** recovery authority (rule 32). Leaves must be the same kind as the trigger (device vs host) |
| `event` | `event`, `change` only | `resetEvent: { actionPattern, resourceType? }` **required** | clears when the counterpart Event arrives for the **same subject** |

`clearThreshold` (hysteresis) applies only to numeric metric triggers with an ordered operator.
For `>` / `>=` it must be at or below the fire threshold. For `<` / `<=` it must be at or above.
Without one, a numeric alert resets at the same value that raised it, so a reading sitting on
the line can re-alert.

On a `monitorStatus == down` trigger, `reset: { "mode": "auto", "sustainPolls": N }` is **also
the recovery count of the monitor state machine**. The device stays `recovering` until N probes have
answered, and the alert stays firing through `down`, `recovering` and `warning`. A `condition`
reset is its own authority and does not drive that count.

The alert clears at the **first successful probe** (when the device reads `recovering`) only
when no `sustainPolls` is set.

### Escalation shapes

Two shapes parse. Write the **v2** one:

```json
{ "stopOn": "acknowledge",
  "tiers": [ { "afterMin": 15, "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] } ],
               "repeatEveryMin": 30, "maxRepeats": 5 } ] }
```

- `stopOn`: `acknowledge` (default: stops on acknowledge **or** clear) or `clear` (ignores acknowledge).
- `tiers`: 1–5. `afterMin` 1–10080 (a week). `actions` 1–10 plain actions (no nested
  escalation or repeat). `repeatEveryMin` 5–1440. `maxRepeats` 1–20 (default 5 when repeating).
- The legacy tier shape (`channelId` + `to` + templates) still parses, and requires
  `to.recipientUserIds` or `to.addresses`. Do not author it.
- Per-action `escalation` on a top-level or band `notify` / `api_call` / `script` is accepted
  too. The wizard **hoists** those chains into the severity's chain when it next opens the rule,
  so write chains at the rule level (`escalation`) or the band level (`severityBands[i].escalation`).

### `repeat` (reminders)

`{ "everyMin": 5–1440, "stopOn": "acknowledge" | "clear", "stopAfterHours": 1–720 | null }`

- On a **notify action**, `repeat` is that action's reminder clock. An **absent** key inherits
  the rule-level `repeat`. **`"repeat": null`** means "this action does not chase", even when
  the rule has a repeat.
- A rule-level `repeat` with no notify action anywhere (top level or bands) is refused.
  Reminders re-send notify actions and nothing else.
- `stopAfterHours` is wall time from the fire, **quiet time included**.
- A `quiet` key inside `repeat` is a legacy shape. When no `quietTime` is sent, the server promotes it to
  `quietTime`. Do not author it.

### Severity bands

```json
"severityBands": [ { "threshold": 95, "severity": "critical" } ]
```

Band keys: `threshold` (required), `severity` (required), `operator?` (falls back to the
trigger's; ordered only), `forDurationSec?`, `actions` (≤ 20, default `[]`), `escalation?`,
`followUp?: { requireAckNote }`.

- Severities must **strictly increase** above the base `severity`. Thresholds need not be monotonic:
  the most severe tier that is met wins (rule 19).
- **Leave `forDurationSec` off a band.** A band without it inherits the trigger's `forPolls`. A
  band with it is measured in wall-clock seconds, even when the trigger counts readings.
- Refused on: non-numeric triggers, `==` / `!=`, and 0/1 metrics (`hwSensorAlarm`,
  `customStateValue`, `pathOk`).
- `actions: []` on a band means "run the base actions". Per-band actions are opt-in. The wizard
  calls this "Use different actions for each severity level".

`bandNotify`: `{ onIncrease: true, onDecrease: false, onResolved: true, resolvedMode: "reuse" | "dedicated", resolvedActions? }`.
These defaults mean: page when it worsens, stay silent when it eases, announce the recovery.

### Quiet time

| Value | Wizard setting | Meaning |
|---|---|---|
| `null` / absent | **Off** | the global quiet times (Automations → Settings) apply |
| `{ "ignoreGlobal": true }` | **Ignore Global Quiet Time** | never held, whatever the hour |
| a policy object | **Override Global Quiet Time** | its own windows. The global ones do not apply |

The policy shape is in [actions-escalation-repeat.md](actions-escalation-repeat.md#quiet-time).
`alertKinds` is refused on an automation's own quiet time, because the automation already is the kind.

## Read-modify-write (PUT)

`PUT /automations/:id` is a **full replace**. A field you leave out takes the default in the
table above. The ones that bite:

| Left out | Becomes |
|---|---|
| `enabled` | `true`: a disabled rule goes live |
| `reset` | `manual`: auto-clear stops |
| `actions` | the audit-Event action only: every notify is gone |
| `severityBands`, `escalation`, `resetActions`, `quietTime` | `null` |

An `api_call` action's header values come back masked (`"••••••••"`). Sending the mask back keeps the stored value,
but only while that action's `url` is unchanged. A masked header on a changed URL is a 400
(rule 114). Re-type the real value when the URL changes. Never paste a real token into chat or into a file.
