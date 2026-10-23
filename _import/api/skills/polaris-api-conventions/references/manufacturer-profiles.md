# Manufacturer profiles

_Generated from Polaris `public/api.html` (section `manufacturer-profiles`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

A **manufacturer profile** says which MIB symbol carries each SNMP telemetry metric for one vendor: model identity, CPU, memory, hardware sensors and storage (the `interfaces`, `lldp` and `wirelessStations` rows are descriptive and change nothing), with device-type defaults and per-model exceptions under each, plus **custom widgets** and **state probes**. A profile governs the devices whose manufacturer is its name (after aliases), and — only when no profile carries a device's own name — those its `matchPattern` ("also applies when") matches. Its symbols resolve from MIBs uploaded under its name. Endpoints gate on `manufacturerProfiles`; patterns are RE2 (no look-around or back-references), case-insensitive, ≤ 512 characters. Every write writes an Event, and the row-level writes return `warnings: []` naming any symbol that does not resolve — a warning, never a refusal.

### GET /server-settings/manufacturer-profiles

_Gate: manufacturerProfiles:read_

`{ profiles, transforms, combiners, metricTransforms }`. Each profile summary carries `id, manufacturer, metricCount, overrideCount, widgetCount` and its readiness: `ready` (every symbol resolves), `partial`, `unresolvedCount`, `unresolvedSymbols`. `GET …/suggestions` lists the manufacturer names already in use (with device counts) and not yet profiled — create profiles under one of these, or the profile matches no device.

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN" \
  "$POLARIS_URL/api/v1/server-settings/manufacturer-profiles"
```

### GET /server-settings/manufacturer-profiles/:id

_Gate: manufacturerProfiles:read_

`{ profile }`: `manufacturer`, `matchPattern`, `metrics` (eight rows, each with its `overrides`) and `widgets`. Every configured row carries `readiness: { a, b, columns? }` — per symbol, `resolved`, the module and layer it resolved from, or a `hint` naming what to upload.

### POST /server-settings/manufacturer-profiles

_Gate: manufacturerProfiles:write_

`{ manufacturer }` → `201` with the new profile and its eight empty metric rows. `409` when the (alias-normalized) name already has one. PUT `/:id` `{ matchPattern }` sets or (`null`) clears "also applies when", tested against `" "`.

### PUT /server-settings/manufacturer-profiles/:id/metrics/:metricKey

_Gate: manufacturerProfiles:write_

Set a metric row (`metricKey`: `model | cpu | memory | temperature | interfaces | storage | lldp | wirelessStations`; `temperature` is the Hardware Sensors row). Fields, all optional on a partial update:

- `defaultSymbol`, `defaultSymbolB`, `defaultType` — `scalar` (a GET of `.0`), `double_scalar` (two symbols, `defaultSymbolB` required) or `table`.
- `defaultTransform` — on `double_scalar` a combiner naming what the pair is (`a_over_b_as_percent` = used / total, `a_over_a_plus_b_as_percent` = used / free, …); on a scalar `temperature` row only `tenths_to_units`; none on a table.
- `defaultAggregate` — `none | avg | sum`: walk a column and average or sum its rows (CPU tables, memory pools).
- `defaultLabel` — the storage mount path or the single sensor's name.
- `defaultParsePattern` / `defaultParseTemplate` — `model` row only: a regex with a capture group and a `$1` template that turn the raw value into the device model. The model is adopted only while the device's model is empty.
- `defaultSensorColumns` — `temperature` rows of type `table` only, where `defaultSymbol` is the sensor table's value column: `{ nameSymbol, alarmSymbol, alarmMap, sensorClass, transform }` (`alarmMap` a state mapping such as `{ "mode": "nonzero" }`, the default; `sensorClass` fixes every row's class; `transform` only `tenths_to_units`). Cleared on a row that is not a table, refused on any other metric.
- `defaultMibId` (an uploaded module) or `defaultMibStdKey` (a bundled one) — which module the row's symbols come from, used to explain an unresolved symbol. Not both.

All three symbol fields cleared returns the row to "no opinion": the standard MIBs answer for that metric. `{ metric, warnings }`.

```bash
curl -X PUT -H "Authorization: Bearer $POLARIS_TOKEN" -H "Content-Type: application/json" \
  -d '{"defaultType":"table","defaultSymbol":"fgHwSensorEntValue",
       "defaultSensorColumns":{"nameSymbol":"fgHwSensorEntName","alarmSymbol":"fgHwSensorEntAlarmStatus"}}' \
  "$POLARIS_URL/api/v1/server-settings/manufacturer-profiles/$PROFILE_ID/metrics/temperature"
```

### POST /server-settings/manufacturer-profiles/:id/metrics/:metricKey/overrides

_Gate: manufacturerProfiles:write_

Add a scoped row under a metric: the same fields without the `default` prefix (`symbol` required), plus its scope — `assetType` (a device type), `modelPattern`, or both, never neither — and `order`. A device type with no pattern is that type's default; one per type per metric (`409` for a second). For each metric the most specific row wins: type + model, then model, then the type's default, then the metric row. A model-pattern row with no type also settles the device's family for every metric of the profile, so give a family a row on every metric it needs. `201` with `{ override, warnings }`. PUT and DELETE `…/overrides/:overrideId` edit and remove one.

### POST /server-settings/manufacturer-profiles/:id/widgets

_Gate: manufacturerProfiles:write_

Add a custom widget: `name`, `widgetType` (`gauge | line | table | state | http`), `symbol` and `mibId` (an **uploaded** module; both omitted on `http`), `type` (`scalar | table`), `transform?`, `displayOptions?` (`min`, `max`, `unit`, `warningAt`, `warningWhen: "below"`), `modelPattern?`. A `state` widget (a state probe, alertable per row through the `customStateValue` metric) needs `stateMap: { mode, values?, trueLabel?, falseLabel?, trueIsProblem? }` (`nonzero | zero | equals | notEquals | gte | lte`) and takes `labelSymbol?`, the sibling column naming each row. An `http` widget takes `httpCheck: { useHttps?, port?, path?, expectStatus?, expectBody?, matchMode?, verifyTls?, … }` and `credentialId?` (an `http` credential). A new widget polls no device until it is switched on for it (below). PUT and DELETE `…/widgets/:widgetId` edit and remove one; an edit keeps the widget's id, so automations on a state probe keep working.

### PUT /server-settings/manufacturer-profiles/:id/widgets/:widgetId/assets

_Gate: manufacturerProfiles:write + assets:write_

`{ enable?: [assetId], disable?: [assetId] }` (≤ 5000 each) — switch the widget on or off per device. Switching on a device the widget does not apply to is a `400`; off always succeeds. → `{ enabled, disabled }` (rows changed). GET the same path (`manufacturerProfiles:read + assets:read`) lists the devices it applies to, each with `enabled`.

### GET /server-settings/manufacturer-profiles/:id/export

_Gate: manufacturerProfiles:read_

The whole profile as a portable file, `{ format: "polaris.manufacturer-profile", version: 1, manufacturer, matchPattern, mibs, metrics, widgets, layout }` — MIBs as `{ moduleName, manufacturer, model }`, a widget's credential as `{ name }`, no ids, no secrets, no per-device switches, no MIB text. `GET …/:id/code` is the same with each override's and widget's `id`, and PUT `…/:id/code` `{ file }` makes the profile match it — a **full replace**: rows left out are cleared or deleted. Returns `{ changes }`.

### POST /server-settings/manufacturer-profiles/import/preview

_Gate: manufacturerProfiles:write_

`{ file }` → `{ manufacturer, targetProfileId, items, mibs }`: every importable item (`id, kind, label, action: "create" | "replace", missingMibs, missingCredential, blocked`) and each MIB the file names with `present`. Writes nothing. Then POST `…/import` `{ file, items: [id] }` imports only the chosen items into the profile for that manufacturer (created when there is none) and returns `{ profileId, results: [{ id, ok, error? }] }` — one failure never stops the rest. Upload the MIBs it reports missing first: a widget whose MIB is missing is blocked, a metric row imports but reads unresolved.

### DELETE /server-settings/manufacturer-profiles/:id

_Gate: manufacturerProfiles:write_

`204`. Its devices fall back to the standard MIBs for every metric.

### GET /manufacturer-aliases

_Gate: manufacturerProfiles:read_

The alias map that folds vendor spellings into one name before any profile is looked up (`[{ id, alias, canonical }]`). POST `{ alias, canonical }`, PUT and DELETE `/:id` at `manufacturerProfiles:write`; a change rewrites the manufacturer on existing devices and MIBs.
