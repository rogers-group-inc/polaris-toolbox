# What the collectors do with a profile

Source in the Polaris repo: `src/services/profileResolver.ts → pickDbProfile` (rows → runtime
shape) and the SNMP collectors in `src/services/monitoringService.ts` (`collectCpuVendor`,
`collectMemoryVendor`, `collectHardwareSensorsSnmpCore`, `collectSystemInfoSnmp`,
`collectManufacturerWidgetSamples`). The validation in profile-model.md decides what *saves*.
This file decides what *collects*.

## Which profile an asset gets

1. The profile whose `manufacturer` equals the asset's alias-normalized manufacturer.
2. Only if none: the first profile, alphabetically by manufacturer, whose `matchPattern`
   matches `"<manufacturer> <os> <pinned MIB module>"`.
3. Otherwise none, and every stream uses the standard MIBs.

Profiles are cached per process and refreshed within 60 s on the monitor process, so allow a
minute after a save before judging a row.

Which assets read a profile at all: those whose CPU/memory (and sensors / system info) are
polled over **SNMP**. An asset whose stream comes from the agent, FortiOS REST, vCenter etc.
never consults it.

## The rows that are read

### CPU (`cpu`), vendor first, HOST-RESOURCES-MIB fallback

| Row | Collector does |
|---|---|
| `scalar`, aggregate `none` | GET `<oid>.0` → number → clamped to 0–100 |
| `table`, or any aggregate `avg`/`sum` | walk the subtree, **average** every numeric value (`sum` still averages; no vendor needs a summed CPU) |

There is no CPU transform, so the object must already be a percent. A load average, a
per-mille, or an idle percentage is not usable as CPU: a symbol whose values are 0–1000 clamps
to 100. If the vendor publishes only *idle*, leave CPU empty and say so.
If the vendor symbol doesn't resolve or returns nothing, `hrProcessorLoad` is tried.

### Memory (`memory`), vendor first, HOST-RESOURCES-MIB fallback

| Row | Collector does |
|---|---|
| `scalar` (percent symbol), aggregate `none` | GET `.0` → percent |
| `scalar`, aggregate `avg`/`sum` | walk, sum, **divide by row count** → an averaged percent |
| `double_scalar` + `a_over_b_as_percent` | A = **used bytes**, B = **total bytes** |
| `double_scalar` + `a_over_a_plus_b_as_percent` | A = **used bytes**, B = **free bytes** |
| `double_scalar` + any other combiner | **memory not collected** |
| `double_scalar` + aggregate `sum` | walk each symbol and sum the rows (memory pools: Cisco `ciscoMemoryPoolUsed` / `Free`) |
| `table` | treated as the percent form (same as scalar, walked if aggregated). Prefer `scalar` + aggregate for clarity. |

The percent is computed from the pair, so units only need to *agree* (KB/KB is fine). But
the stored byte counts are charted as bytes: a KB pair shows 1/1024 of the real size. There
is no transform on memory rows. Note it in the spec's `notes` when the vendor's unit isn't
bytes.

### Hardware Sensors (`temperature`), only after the standard sources come back empty

Order the collector tries:

1. **Fortinet's `fgHwSensorTable`**, if the manufacturer matches /fortinet/ **or** the row is
   `type: table`. That walk uses hardcoded Fortinet columns, and **the row's symbol is
   ignored**, so a `table` row on any other vendor walks nothing useful and wastes a walk.
2. **ENTITY-SENSOR-MIB** (`entPhySensorTable`), on every device. Temperatures, fans,
   voltages and optics, with the agent's own oper status as the alarm bit. If the device
   implements it, leave this row empty.
3. **The profile's `scalar` row**: GET `.0`, apply `tenths_to_units` if set (the only
   transform allowed), round to 0.1, and store one sensor named `label` (default `System`)
   in °C.

So outside Fortinet, Hardware Sensors carries **one** scalar temperature. Multi-sensor vendor
tables (UPS probes, PDU banks, chassis fan tables) belong in **widgets** (table) or **state
probes** (alarm columns).

### Storage (`storage`), only when `hrStorageTable` has no disk rows

| Row | Collector does |
|---|---|
| `double_scalar` + `a_over_b_as_percent` or `a_over_b_ratio` | A = used, B = total |
| `double_scalar` + `a_over_a_plus_b_as_percent` or `a_plus_b` | A = used, B = free |
| `double_scalar` + `b_minus_a_over_b_as_percent` | A = free, B = total |
| `double_scalar` + `a_minus_b` | A = total, B = free |
| `scalar` or `table` | **ignored**: a lone percent can't make a storage row |

Both symbols are scalar GETs (`.0`), in **bytes**, giving one storage row whose mount path is
`label` (default `system`). One volume per profile; a multi-volume vendor table is a widget.

### Model identity (`model`)

`scalar` GET of the symbol → `parsePattern` (RE2, case-insensitive, group 1 = the model
token) → `parseTemplate` with `$1` (or the bare token). Rules:

- No match, or an empty capture → nothing stamped ("unrecognized, never a guess").
- A token that already starts with the template's literal prefix is kept as-is
  (`FortiSwitchRugged-112D` doesn't become `FortiSwitch FortiSwitchRugged-112D`).
- It is **adopted onto `Asset.model` only while the asset's model is empty** (or still a
  generic `FortiSwitch…`). An operator-typed or discovery-supplied model is never
  overwritten. Writes an `asset.model_detected` Event.
- Use it only when the hardware model is reachable nowhere else. `sysDescr` parsing and
  discovery already supply most models.

## Overrides: precedence and the one trap

Per metric, most-specific first:

1. this device type **and** a matching model pattern
2. a matching model pattern with **no** device type
3. this device type's default (type set, no pattern)
4. the metric row's own defaults
5. nothing, so the standard MIBs answer

A stated model outranks an inferred type (2 above 3), on purpose: a mis-typed asset whose
model names its family still routes by model.

**The trap: a device is one family.** Before resolving any metric, Polaris asks once: *does
any tier-2 row (model pattern, no type) on any metric of this profile match this device?* If
yes, **tier 3 is skipped for every metric** of that device. Example: model rows
`FortiAP` on cpu/memory/temperature, plus a `switch` type default on storage. A FortiAP
mis-typed as `switch` reads storage from the profile default (or nothing), never the switch's
flash OIDs. Design consequence: **when a family is identified by a model pattern, give it a
row on every metric it needs.** Don't rely on a type default to fill the gap.

Recommended shape for a multi-family vendor (Polaris's own Fortinet seed does this): for each
family, a type default **and** a no-type model-pattern row with the same content. The type
default catches the asset with an empty model; the model row catches the mis-typed one.

## Rows that save and do nothing

Name these in the spec's `notes` if a requester asks for them:

- anything on `interfaces`, `lldp`, `wirelessStations`
- a metric-row transform other than `tenths_to_units` on scalar temperature (refused anyway)
- `table` Hardware Sensors on a non-Fortinet vendor
- `scalar` / `table` Storage
- a `double_scalar` memory with a combiner other than the two listed
- a symbol from a MIB uploaded under a *different* manufacturer spelling
- a `scalar` row naming a table column (GET `.0` finds nothing)
- widgets on a profile reached only through `matchPattern`

## Scale

Each read row is one GET, or one walk per symbol, per monitored asset per telemetry pass. A
walked CPU or memory row over a large table (hundreds of rows) is paid for by every asset of
that vendor, every pass. Point walks at the narrowest column, never at an entry or a table
root. State probes are capped at 500 rows per probe per scrape; beyond that they truncate with
a warning.
