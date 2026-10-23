# Recipes

Each recipe is a complete body for `POST /api/v1/automations`. Before posting, replace every
`<placeholder>`:

| Placeholder | Where it comes from |
|---|---|
| `<email-channel-id>` | `GET /delivery-channels`, the id of an `smtp` or `oauth_m365` channel |
| `<recipient@example.com>` | a real mailbox. The placeholder fails the email check, and the 400 names `addresses` |
| `<asset-type>` | an asset type in the inventory. Preview the scope to confirm it selects devices |
| `<state-probe-id>` | `GET /automations/schema` → `stateProbes` |
| `<interface-name>`, `<mount-path>` | `POST /automations/dimension-values` for the scoped devices |

All recipes ship with `"enabled": false`. **A human reviews and enables each one.** Run
`POST /automations/preview` with the same body first.

## 1. Device down after 3 missed polls

Defines down for the scoped devices: down after 3 misses outstanding, back up after 3 answers.
It announces the recovery.

```json
{
  "name": "Device down — <asset-type>",
  "enabled": false,
  "severity": "critical",
  "trigger": { "type": "asset_state", "field": "monitorStatus", "operator": "==", "value": "down", "missedPolls": 3 },
  "scope": { "condition": { "op": "and", "children": [ { "field": "assetType", "operator": "equals", "value": "<asset-type>" } ] } },
  "reset": { "mode": "auto", "sustainPolls": 3 },
  "actions": [
    { "type": "notify", "channelId": "<email-channel-id>", "recipientDeviceRegionLevels": [1], "addresses": ["<recipient@example.com>"] },
    { "type": "event" }
  ],
  "resetActions": [
    { "type": "notify", "channelId": "<email-channel-id>", "recipientDeviceRegionLevels": [1], "addresses": ["<recipient@example.com>"] }
  ]
}
```

- **This changes down detection** for every device it covers (rule 36). If a broader down rule
  exists, this one carves its devices out (Device type beats All assets). If not, devices outside it
  stay `passive`. Run `removal-impact` on any down rule it replaces.
- `missedPolls` is the wizard's **Sustained for (polls)**. No `forPolls` goes with it.
- To keep paging for devices behind a dead switch, add `"alertWhenDependencyDown": true` to the
  trigger (**Dependency-Down Bypass**, rule 78).

## 2. CPU high for 3 polls, critical above 98 %, with escalation and reminders

```json
{
  "name": "CPU high — <asset-type>",
  "enabled": false,
  "severity": "serious",
  "trigger": { "type": "asset_metric", "metric": "cpuPct", "operator": ">", "threshold": 90, "aggregation": "latest", "forPolls": 3 },
  "scope": { "condition": { "op": "and", "children": [ { "field": "assetType", "operator": "equals", "value": "<asset-type>" } ] } },
  "reset": { "mode": "auto", "clearThreshold": 80, "sustainPolls": 2 },
  "severityBands": [ { "threshold": 98, "severity": "critical" } ],
  "actions": [
    { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"],
      "repeat": { "everyMin": 30, "stopOn": "acknowledge", "stopAfterHours": 12 } },
    { "type": "event" }
  ],
  "escalation": { "stopOn": "acknowledge", "tiers": [
    { "afterMin": 30, "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "recipientDeviceRegionLevels": [2] } ] } ] },
  "resetActions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] } ]
}
```

- Fires after 3 consecutive readings over 90. It clears after 2 readings at or below 80 (the hysteresis
  dead band). One alert climbs to critical in place over 98 and inherits the trigger's 3-poll hold.
- The reminder rides the notify action (rule 56). The escalation tier belongs to the base severity. A
  critical band with no `actions` of its own runs the base actions.

## 3. Interface errors: average of 5-poll groups, two groups in a row

```json
{
  "name": "Interface in-errors — <asset-type>",
  "enabled": false,
  "severity": "warning",
  "trigger": { "type": "asset_metric", "metric": "ifInErrorRate", "operator": ">", "threshold": 5,
               "aggregation": "avg", "windowPolls": 5, "forPolls": 2,
               "dimensionFilter": { "ifNamePattern": "<interface-name>" } },
  "scope": { "condition": { "op": "and", "children": [ { "field": "assetType", "operator": "equals", "value": "<asset-type>" } ] } },
  "reset": { "mode": "auto", "sustainPolls": 2 },
  "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] }, { "type": "event" } ]
}
```

- Poll groups (rule 66): about 10 polls to alert. Only **pinned** interfaces produce readings
  (rule 57). Drop `ifNamePattern` to cover every pinned port, one alert each, or join several
  names with `|`.

## 4. Interface down, one alert per device

```json
{
  "name": "Uplink down — <asset-type>",
  "enabled": false,
  "severity": "serious",
  "trigger": { "type": "asset_state", "field": "ifOperStatus", "operator": "==", "value": "down", "forPolls": 2,
               "dimensionFilter": { "ifNamePattern": "<interface-name>" } },
  "scope": { "condition": { "op": "and", "children": [ { "field": "assetType", "operator": "equals", "value": "<asset-type>" } ] } },
  "reset": { "mode": "auto" },
  "groupByAsset": true,
  "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] }, { "type": "event" } ]
}
```

- Admin-down ports are ignored. `groupByAsset` folds every down port on one device into one alert that
  ends when the last port recovers (rule 75).

## 5. Hardware sensor alarm (the device's own alarm bit)

```json
{
  "name": "Fan or PSU alarm",
  "enabled": false,
  "severity": "serious",
  "trigger": { "type": "asset_metric", "metric": "hwSensorAlarm", "operator": "==", "threshold": 1, "forPolls": 2 },
  "scope": { "allAssets": true },
  "reset": { "mode": "auto" },
  "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] }, { "type": "event" } ]
}
```

- Prefer the alarm bit over a threshold on `hwSensorValue` (rule 24). Narrow it with
  `"dimensionFilter": { "sensorClass": "fan" }` (or `power`, `temperature`, …). A 0/1 metric
  refuses severity bands and `clearThreshold`.

## 6. Storage full within 14 days

```json
{
  "name": "Storage full within 14 days",
  "enabled": false,
  "severity": "warning",
  "trigger": { "type": "asset_metric", "metric": "storageDaysUntilFull", "operator": "<=", "threshold": 14,
               "dimensionFilter": { "mountPathPattern": "<mount-path>" } },
  "scope": { "allAssets": true },
  "reset": { "mode": "auto" },
  "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] }, { "type": "event" } ]
}
```

- A forecast from the 30-day trend. A filesystem that is not growing gives no reading, so it never fires.
  The default email draws the forecast out to 14 days. Remove `dimensionFilter` to cover every mount.

## 7. State probe alarm (a manufacturer-profile state widget)

```json
{
  "name": "Device state flag — <state-probe-id>",
  "enabled": false,
  "severity": "serious",
  "trigger": { "type": "asset_metric", "metric": "customStateValue", "operator": "==", "threshold": 1, "forPolls": 2,
               "dimensionFilter": { "stateProbeId": "<state-probe-id>" } },
  "scope": { "allAssets": true },
  "reset": { "mode": "auto" },
  "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] }, { "type": "event" } ]
}
```

- `1` is the probe's true state. Check its two labels in `/schema` → `stateProbes` to confirm that
  `1` is the problem state. Add `"stateRowPattern": "<row label>"` to watch one row, e.g. one PSU.

## 8. Event pattern: agent disconnected, cleared by its reconnect

```json
{
  "name": "Polaris Agent disconnected",
  "enabled": false,
  "severity": "warning",
  "trigger": { "type": "event", "actionPattern": "agent.disconnected" },
  "scope": { "allAssets": true },
  "reset": { "mode": "event", "resetEvent": { "actionPattern": "agent.connected" } },
  "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] } ],
  "resetActions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] } ]
}
```

- The reset matches the **same subject**. No `event` action: on an event trigger it is a no-op.
  Agent upgrades and reinstalls hold the host in maintenance, so they do not page (rules 80, 80a).
- **Directional variant:** `"trigger": { "type": "event", "actionPattern": "capacity.severity_changed",
  "detailsMatch": { "direction": "escalated" } }` with a reset on `capacity.severity_recovered`.
  Capacity events name no device, so its scope must stay unconstrained (`{}` or `allAssets`). A filtered
  event rule never fires on an event with no asset (rule 46).

## 9. Composite AND: CPU and memory both high

```json
{
  "name": "CPU and memory both high — <asset-type>",
  "enabled": false,
  "severity": "serious",
  "trigger": { "type": "composite", "kind": "asset", "op": "and", "forPolls": 3,
    "children": [
      { "type": "asset_metric", "metric": "cpuPct", "operator": ">", "threshold": 90 },
      { "type": "asset_metric", "metric": "memPct", "operator": ">", "threshold": 90 } ] },
  "scope": { "condition": { "op": "and", "children": [ { "field": "assetType", "operator": "equals", "value": "<asset-type>" } ] } },
  "reset": { "mode": "auto", "sustainPolls": 2 },
  "actions": [ { "type": "notify", "channelId": "<email-channel-id>", "addresses": ["<recipient@example.com>"] }, { "type": "event" } ]
}
```

- One hold for the whole tree, one alert per device. No severity bands, `clearThreshold` or
  `groupByAsset` on a composite. Composites do not take part in carve-out.

## Add-ons for any recipe

- **Never at night except critical:** `"quietTime": { "ignoreGlobal": true }` keeps a rule paging
  through every global quiet time. See [actions-escalation-repeat.md](actions-escalation-repeat.md#quiet-time)
  for a policy of its own.
- **Book a reboot overnight on memory pressure:** add
  `{ "type": "reboot", "when": "at", "at": "02:00", "addresses": ["<recipient@example.com>"], "minGapHours": 24 }`
  to `actions` of a `memPct > 90` rule (needs `assets:write`). It books, never sends one inline, and never
  runs from a test (rule 115). **A human must review any automation that reboots production equipment.**
- **Webhook to a ticketing system:**
  `{ "type": "api_call", "method": "POST", "url": "https://tickets.example.com/api/incidents", "headers": { "Authorization": "<typed into the wizard, never in chat>" }, "bodyTemplate": "{\"title\": \"{rule}: {asset}\", \"severity\": \"{severity}\"}", "timeoutSec": 15 }`.
  Headers are sealed and masked (rule 114). Export drops this action.
- **Run a script:** `{ "type": "script", "scriptId": "<script-id>", "runOn": "server", "argsTemplate": "{asset.ip} {severity}" }`
  (needs `automationScripts:write`). The args arrive as **one** argument. Write the script with
  **`polaris-automation-scripts`**.
