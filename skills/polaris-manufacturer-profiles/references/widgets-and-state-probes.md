# Custom widgets and state probes

Widgets are how a profile carries what the five metric rows can't: battery runtime, PSU
state, fan tables, client counts, alarm bits, an HTTP health endpoint. They render on the
asset's **Custom MIB** tab and are collected on the telemetry cadence.

## When widgets are collected

All of these must hold, or the widget is silently skipped:

- The asset's `manufacturer` is **keyed** to this profile. `matchPattern` is not consulted
  for widgets.
- `modelPattern`, if set, matches `Asset.model` (RE2, case-insensitive). An empty model
  fails a set pattern.
- **SNMP widgets**: the asset's custom-widget polling (falling back to its CPU/memory
  polling) is `snmp`, it has an SNMP credential (custom-widget, then CPU/memory, then the
  monitor credential; Fortinet integrations can supply one), and the symbol resolves at the
  asset's scope.
- **HTTP widgets**: none of the SNMP conditions. They dial the asset's address, or its DNS
  name / hostname.

## widgetType

| widgetType | `type` | What is stored / shown |
|---|---|---|
| `gauge` | `scalar` | walk the symbol, take the first numeric value, apply `transform` → one number. A dial, with `displayOptions` `min`, `max`, `unit`, `warningAt`, `warningWhen`. |
| `line` | `scalar` | same reading, charted over time. `unit`, `warningAt`, `warningWhen`. |
| `table` | `table` | walk the subtree → `[{index, value}]` per row (numeric where possible). No display options. Point it at one **column**. |
| `state` | `scalar` or `table` | each reading mapped through `stateMap` to 0/1 and stored as a state sample, which **is alertable per row** in Automations ("…is Alarm"). |
| `http` | n/a | an HTTP(S) request and its verdict. No symbol, no MIB. |

`warningAt` / `warningWhen` only colour the card. Alerting on a value is an automation.

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
IDs are per-install, so a spec never carries one. It carries `"credential": "<description of
what to pick>"`, and the apply script leaves it null unless `--http-credential-id` is given.

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
