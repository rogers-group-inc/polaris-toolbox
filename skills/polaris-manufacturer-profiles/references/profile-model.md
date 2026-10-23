# The profile data model

Source of truth in the Polaris repo: `prisma/schema.prisma` (models `ManufacturerProfile`,
`ManufacturerProfileMetric`, `ManufacturerProfileMetricOverride`, `ManufacturerCustomWidget`,
`MibFile`) and `src/services/manufacturerProfileService.ts` (every validation below).

## ManufacturerProfile: one per canonical manufacturer

| Field | Meaning |
|---|---|
| `manufacturer` | Unique. Stored through the alias normalizer, so creating "Hewlett Packard Enterprise" may store "HPE" if an alias maps it. A second profile for the same name is `409`. |
| `matchPattern` | **"Also applies when"**: an RE2 regex, case-insensitive, tested against `"<asset manufacturer> <asset os> <pinned MIB module name>"`, and **only** when no profile is keyed by the asset's manufacturer. Use it for spellings no alias folds in, OS-only identity ("Cisco IOS" with an empty manufacturer), or a device that reports nothing but speaks a recognizable MIB. ≤ 512 chars. Null clears it. |

Creating a profile pre-creates **all eight metric rows**, empty. You never create a metric
row, you only `PUT` it.

## Metric rows: eight fixed keys, five are read

| `metricKey` | UI label | Read at probe time? |
|---|---|---|
| `model` | Model identity | **yes** |
| `cpu` | CPU | **yes** |
| `memory` | Memory | **yes** |
| `temperature` | Hardware Sensors | **yes** |
| `interfaces` | Interfaces | no, display-only |
| `storage` | Storage | **yes** |
| `lldp` | LLDP | no, display-only |
| `wirelessStations` | Wireless stations | no, display-only |

Fields (on the metric row they carry a `default` prefix; on an override row they don't):

| Field (metric / override) | Values | Rule |
|---|---|---|
| `defaultSymbol` / `symbol` | MIB symbol name | Override: required. Metric row: an all-empty row (symbol, symbolB and transform all null) is legal and means "no opinion". |
| `defaultSymbolB` / `symbolB` | second symbol | Required on `double_scalar`, must be null otherwise (forced null on write). |
| `defaultType` / `type` | `scalar` \| `double_scalar` \| `table` | `table` takes no `symbolB` and no transform. |
| `defaultTransform` / `transform` | see below | Type-aware: a **combiner** on `double_scalar`; a **unary transform** on `scalar` only where the metric allows one; nothing on `table`. |
| `defaultAggregate` / `aggregate` | `none` \| `avg` \| `sum` | How a walked subtree collapses. Anything but `none` means "walk it". |
| `defaultLabel` / `label` | text | Storage: the `mountPath` of the synthesized storage row (e.g. `flash`). Hardware Sensors scalar: the sensor name (default `System`). |
| `defaultParsePattern` / `parsePattern` | RE2 regex with ≥ 1 capture group | `model` row only (400 on any other). Required when a `model` symbol is set. ≤ 512. |
| `defaultParseTemplate` / `parseTemplate` | text containing `$1` | `model` row only. Optional; ≤ 200. |
| `defaultSensorColumns` / `sensorColumns` | `{ nameSymbol, alarmSymbol, alarmMap, sensorClass, transform }` | `temperature` rows of type `table` only (Polaris rule 132): the sensor table's sibling columns beside the value column the row's symbol names. `alarmMap` is a state mapping (`{ "mode": "nonzero" }` when omitted); `sensorClass` one of `temperature`, `fan`, `voltage`, `current`, `optical`, `poe`, `power`, `disk`, `other` or null; `transform` only `tenths_to_units`. Cleared on a non-table temperature row, 400 on any other metric. In an export file the field is `sensorColumns` on both metric and override rows. |
| `defaultMibId` / `mibId` | uploaded `MibFile` id | Display / explanation only. The resolver does not need it, but readiness uses it to say *why* a symbol is unresolved. |
| `defaultMibStdKey` / `mibStdKey` | `std:system`, `std:interfaces`, `std:if-ext`, `std:host-resources`, `std:entity`, `std:entity-sensor`, `std:lldp`, `std:poe`, `std:bridge`, `std:q-bridge`, `std:rstp`, `std:ip` | Display-only hint for a symbol from a bundled standard MIB. **Mutually exclusive with the MIB id** (400 if both are set). |

### Transforms

Unary (`TransformKind`): `bytes_to_mb`, `bytes_to_gb`, `mb_to_bytes`, `ticks_to_seconds`,
`ratio_to_percent`, `percent_to_ratio`, `signed_to_unsigned`, `tenths_to_units`.

- On a **metric or override row**, only `METRIC_ROW_TRANSFORMS` is accepted. Today that is
  exactly **`tenths_to_units` on a `scalar` `temperature` row**. Everything else is a 400.
- On a **widget**, the whole unary list is accepted and applied.
- There is no Celsius↔Fahrenheit transform, on purpose. Polaris stores °C and converts at
  render.

Combiners (`CombinerKind`, `double_scalar` only): `a_over_b_as_percent`,
`a_over_a_plus_b_as_percent`, `b_minus_a_over_b_as_percent`, `a_minus_b`, `a_plus_b`,
`a_over_b_ratio`. **A combiner is read as a statement of which two quantities A and B are,
not executed as arithmetic.** [runtime-semantics.md](runtime-semantics.md) has the per-metric
table of which combiners mean anything.

## Override rows: scoped exceptions under one metric

Scope is the pair `(assetType, modelPattern)`, and **at least one half must be set**:

| `assetType` | `modelPattern` | Meaning |
|---|---|---|
| set | null | the **device-type default**: every asset of that type under this manufacturer. Max **one per (metric, type)**; a second is `409`. |
| set | set | a per-model exception *under* that type |
| null | set | a per-model exception for *any* type. Also settles the device's family (see runtime-semantics § overrides). |

- `assetType` must be a registered device type: built-ins `server`, `switch`, `router`,
  `firewall`, `workstation`, `printer`, `access_point`, `other`, `hypervisor`,
  `kubernetes_cluster`, `container`, plus any custom type the install added under Device
  Types. Unknown → 400.
- `modelPattern` is RE2, case-insensitive, matched against `Asset.model` plus the pinned MIB
  module name (plus "FortiSwitch"/"FortiAP" class hints on Fortinet). ≤ 512.
- `order` (int, default 0) breaks ties inside a precedence tier, ascending.

## Custom widgets

| Field | Rule |
|---|---|
| `name` | required |
| `widgetType` | `gauge` \| `line` \| `value` \| `table` \| `state` \| `http` |
| `symbol` | required for every type but `http` (null there) |
| `mibId` | **required** for every type but `http`, and it must be an *uploaded* `MibFile`. A widget on a standard-MIB symbol needs that module uploaded too, usually as a generic MIB. |
| `type` | `scalar` \| `table` (no `double_scalar` on widgets) |
| `transform` | any unary transform, or null |
| `displayOptions` | gauge: `min`, `max`, `unit`, `format`, `warningAt`, `warningWhen` (`"below"`, or absent = above). line and value: `unit`, `format`, `warningAt`, `warningWhen`. table: none. `format` is `""`, `duration_s` or `duration_ticks`. These paint the card only; alerting is an automation's job. |
| `modelPattern` | optional RE2 gate against `Asset.model` |
| `stateMap`, `labelSymbol` | `state` only; `stateMap` required there. Forced null on other types. |
| `httpCheck`, `credentialId` | `http` only. Forced null on other types. |
| `order` | int |

A widget polls only the devices it is switched on for (Polaris rule 130) — the switch is per
(device, widget), is not part of a profile file, and starts OFF. Full widget semantics:
[widgets-and-state-probes.md](widgets-and-state-probes.md).

## MibFile: an uploaded module

`(manufacturer, model, moduleName)` is unique, so uploading the same module twice under the
same scope is a 409. `manufacturer` null = generic (resolves for every device). `model`
requires a manufacturer. `manufacturer` is alias-normalized on write, like `Asset.manufacturer`.
Limit 6 MiB per file. Text only, and it must parse as SMI (`<NAME> DEFINITIONS ::= BEGIN … END`).
The upload response carries `symbolCount`, `unresolvedCount` and
`unresolvedRoots[{symbol, module}]`. A non-zero `unresolvedRoots` names the module still
missing.

## Readiness

`GET /server-settings/manufacturer-profiles/:id` stamps every configured row with
`readiness: { a, b }`. Each side is `{ symbol, resolved, oid, fromScope, fromModuleName, hint }`,
where `hint` is `{kind:"no-module"}` (nothing loaded defines it) or
`{kind:"imports", mibModuleName, roots}` (the pinned MIB is missing a dependency). The list
endpoint rolls this up as `ready` / `partial` / `unresolvedCount` / `unresolvedSymbols`. Every
write returns `warnings[]` naming unresolved symbols. **Readiness is evaluated at the
manufacturer scope. It does not check widgets**; check a widget's symbol by eye against the
uploaded module.

At boot, Polaris writes one warning Event, `manufacturer_profile.unresolved`, per profile
with unresolved symbols.
