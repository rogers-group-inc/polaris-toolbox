# Custom widgets and state probes

Widgets are how a profile carries what the five metric rows can't: battery runtime, PSU
state, fan tables, client counts, alarm bits, an HTTP health endpoint. They render on the
asset's **Custom MIB** tab and are collected on their own cadence, at the device's
hardware-sensor interval (Polaris rule 130).

## When a widget is collected

All of these must hold, or the widget is silently skipped:

- **The profile governs the device**: keyed by the device's manufacturer, or reached through
  the profile's `matchPattern` when no profile has the device's own name (rule 131).
- `modelPattern`, if set, matches `Asset.model` (RE2, case-insensitive). An empty model
  fails a set pattern.
- **The widget is switched ON for that device.** A new widget starts OFF everywhere. It is
  switched on per device from the "enable on these devices" list Polaris opens when it is
  saved, its **Devices…** button, the switch on each card of the asset's Custom MIB tab, or
  `PUT /server-settings/manufacturer-profiles/:id/widgets/:widgetId/assets` with
  `{ "enable": [assetId…] }` (needs `assets:write` too). Say so in every deliverable: a
  widget nobody switched on never collects.
- **SNMP widgets** need an SNMP credential on the device — the first SNMP one of custom-widget
  → hardware-sensor → CPU/memory → monitor credential, then a Fortinet integration's — and the
  symbol must resolve (the device's own uploads, then the profile's). There is no
  polling-method gate any more: a UPS with no CPU stream still polls its battery widgets.
- **HTTP widgets**: none of the SNMP conditions. They dial the asset's address, or its DNS
  name / hostname.

## widgetType

| widgetType | `type` | What is stored / shown |
|---|---|---|
| `gauge` | `scalar` | walk the symbol, take the first numeric value, apply `transform` → one number. A dial, with `displayOptions` `min`, `max`, `unit`, `format`, `warningAt`, `warningWhen`. |
| `line` | `scalar` | same reading, charted over time. `unit`, `format`, `warningAt`, `warningWhen`. |
| `value` | `scalar` | the same reading shown as the latest number alone. `unit`, `format`, `warningAt`, `warningWhen`. |
| `table` | `table` | walk the subtree → `[{index, value}]` per row (numeric where possible). No display options. Point it at one **column**. |
| `state` | `scalar` or `table` | each reading mapped through `stateMap` to 0/1 and stored as a state sample, which **is alertable per row** in Automations ("…is Alarm"). |
| `http` | n/a | an HTTP(S) request and its verdict. No symbol, no MIB. |

`format` is `""` (a number with its unit, the default), `duration_s` (the value is seconds,
shown as "1 h 23 m") or `duration_ticks` (SNMP TimeTicks, hundredths of a second). A `unit`
of `°C` or `°F` marks a temperature: it is shown in the install's temperature unit,
converted when they differ. `warningAt` / `warningWhen` only colour the card; alerting on a
value is an automation. A profile's card layout on the Custom MIB tab (`layout` in the
export) is optional.

A widget's `mibId` must name an **uploaded** MIB, even when the symbol comes from a bundled
standard module. In that case upload that standard module as a generic MIB first.

## State probes

`stateMap`:

```json
{ "mode": "notEquals", "values": ["2"], "trueLabel": "Fault", "falseLabel": "Normal", "trueIsProblem": true }
```

| mode | true when | values |
|---|---|---|
| `nonzero` (default) | value ≠ 0 | none |
| `zero` | value = 0 | none |
| `equals` | value ∈ values | 1–20 |
| `notEquals` | value ∉ values | 1–20 |
| `gte` | value ≥ values[0] | exactly 1, numeric |
| `lte` | value ≤ values[0] | exactly 1, numeric |

- Comparison is numeric when both sides parse as numbers, else case-insensitive string, so
  `["2","alarm"]` covers a device answering either.
- Labels are ≤ 32 chars, must differ, and default to `Alarm` / `OK`.
- An unreadable or empty value yields **no reading**, never "OK". The row stops reporting
  rather than clearing an alert.
- `type: scalar` → one device-wide flag (the first readable row).
- `type: table` → one flag per row. Set `labelSymbol` to the sibling **name column** of the
  same table (e.g. `upsPhaseInputName` beside a status column). It joins on the shared index
  so alerts name the row ("PSU 2 is Fault"), not `.3`. Without it rows are named by bare
  index, which varies by model.
- Max 500 rows per probe per scrape; beyond that it truncates with a warning. Point it at a
  narrow column.
- After creating a probe, the automation builder lists it by name under that manufacturer.

## HTTP widgets

`httpCheck`: `useHttps` (bool), `port` (1–65535), `path` (e.g. `/healthz`), `expectStatus`
(100–599, absent = any 2xx), `expectBody`, `matchMode` (`contains` | `regex`, RE2),
`caseSensitive`, `failOnMismatch`, `verifyTls`. `{}` is a valid check: GET `/`, expecting any
2xx.

`credentialId` names an **`http`-typed** Credential (bearer / basic / digest). Null =
unauthenticated. A device *form* login (the firmware-repository kind) is refused. Credential
ids are per-install, so the profile file carries the credential's NAME (`"credential":
{ "name": "…" }`); import matches it by name, and a check whose credential has no match
imports unauthenticated (the preview says so).

## Good widget candidates by device class

Name the actual symbols from the operator's MIB. These are starting points, not symbols to
assume:

- **UPS**: battery capacity % (gauge), runtime remaining (line, `ticks_to_seconds`), battery
  status (state, enum), output load % (gauge), on-battery flag (state).
- **PDU**: per-outlet or per-bank load (table), overload status (state, table + name
  column).
- **Switch / router chassis**: PSU status table (state + name column), fan status table
  (state + name column), stack member state.
- **Wireless controller / AP**: associated client count (line).
- **Storage appliance**: per-volume status (state, table), RAID state (state).
- **Appliance with a web health endpoint**: `http`.
