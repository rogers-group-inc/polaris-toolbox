# Reading a vendor MIB to choose symbols

The operator supplies the MIB text. Every symbol in a profile must be **defined in a module
the operator will upload**, and the profile file names that module. Don't write a symbol from memory you
can't point at in the file: a wrong name saves cleanly and shows as unresolved forever. If
the operator has no MIB, say which module to get and from where (the vendor's support site),
and stop short of guessing symbols.

The snippets below use a fictional module, `EXAMPLE-UPS-MIB`, to show the SMI shapes. They are
not any vendor's real objects.

## 1. Find the module and its dependencies

```
EXAMPLE-UPS-MIB DEFINITIONS ::= BEGIN
IMPORTS
   enterprises, Gauge, TimeTicks   FROM RFC1155-SMI
   DisplayString                   FROM RFC1213-MIB
   OBJECT-TYPE                     FROM RFC-1212
   TRAP-TYPE                       FROM RFC-1215;
```

- The module name (`EXAMPLE-UPS-MIB`) is what the profile file's `mibs[].moduleName` and every
  row's `mib.moduleName` carry.
- List every `FROM <MODULE>`. Resolution is by **symbol name**, so only imports that supply
  an OID *anchor* matter. These need **no upload**:
  - SMI / TC / macro modules (SNMPv2-SMI, SNMPv2-TC, SNMPv2-CONF, RFC1155-SMI, RFC-1212,
    RFC-1215, RFC1213-MIB's `DisplayString`). Their anchors (`enterprises`, `mib-2`,
    `private`, `snmpModules`, `experimental`…) are seeded, and types and macros carry no OID.
  - The eleven bundled standard modules: SNMPv2-MIB, IF-MIB, HOST-RESOURCES-MIB, ENTITY-MIB,
    ENTITY-SENSOR-MIB, LLDP-MIB, POWER-ETHERNET-MIB, BRIDGE-MIB, Q-BRIDGE-MIB, RSTP-MIB,
    IP-MIB.
- Any **vendor** module in the IMPORTS (`FORTINET-CORE-MIB`, `CISCO-SMI`, `JUNIPER-SMI`,
  `HP-ICF-OID`…) must be uploaded too, under the same manufacturer. Missing it leaves the
  leaf's root unresolved, and then **nothing** in the leaf resolves. The upload response's
  `unresolvedRoots` names it. Put it in `mibs[]` before the leaf.
- A non-vendor module that is neither scaffolding nor bundled (e.g. UPS-MIB, RFC 1628, which
  some UPS MIBs import) is uploaded as a **generic** MIB (manufacturer null).

## 2. Scalar or column?

```
exUpsBatteryCapacity OBJECT-TYPE
    SYNTAX  Gauge
    ACCESS  read-only
    STATUS  mandatory
    DESCRIPTION "The remaining battery capacity expressed in percent of full capacity."
    ::= { exUpsBattery 1 }
```

- Parent is a plain group (`exUpsBattery`) → **scalar**, instance `.0`. Use `type: scalar`,
  aggregate `none`.
- Parent is an `…Entry` whose own SYNTAX is a `SEQUENCE` and which carries an `INDEX` clause →
  **column**. One value per row. On a CPU or memory row use `aggregate: avg` / `sum` (or CPU
  `type: table`). On a widget use `type: table`. On a state probe use `type: table`, with a
  name column as `labelSymbol`.
- Never point a row at the `…Table` or `…Entry` itself. Name the **column**. A table root
  walks every column interleaved.

## 3. Units and scale: what the number means

Read SYNTAX, UNITS, DISPLAY-HINT (on the object or its TEXTUAL-CONVENTION) and the
DESCRIPTION together:

| What you see | Consequence |
|---|---|
| "percent", `UNITS "%"`, range `(0..100)` | usable directly as CPU / memory percent |
| `DISPLAY-HINT "d-1"` (e.g. MikroTik `Temperature`), or "tenths of degrees" | scalar temperature row with `transform: tenths_to_units`; on a widget, the same transform |
| `DISPLAY-HINT "d-2"` or hundredths | no transform for it on a metric row. A widget can't scale by 100 either (`percent_to_ratio` divides by 100 but labels the result a ratio); say so |
| "kilobytes", `UNITS "KB"` | memory percent is still right (both halves agree), but the chart's byte figures are 1/1024. Note it. Storage needs bytes, so a KB pair is wrong there. Prefer another object, or leave storage to HRM. |
| bytes as `Counter64` / `Gauge32` / `CounterBasedGauge64` | fine. Note a 32-bit gauge caps at 4 GiB. |
| `TimeTicks` | widget with `ticks_to_seconds` |
| Fahrenheit | **not usable** as Hardware Sensors (Polaris stores °C, no F→C transform). Use a widget and label the unit. |
| a load average, idle %, or "per-mille" | not a CPU percent; leave CPU empty |

## 4. Status objects: enum polarity

```
exUpsBatteryStatus OBJECT-TYPE
    SYNTAX INTEGER { unknown(1), batteryNormal(2), batteryLow(3), batteryInFaultCondition(4) }
```

This is a **state probe**, not a gauge, and the bad values are the *non-zero* ones. Map it
explicitly:

- "one good code" → `mode: notEquals`, `values: ["2"]`, labels `Fault` / `Normal`.
- "specific bad codes" → `mode: equals`, `values: ["3","4"]`.
- `TruthValue` is `true(1) false(2)`, never `0`/`1`. "Alarm when true" is `equals ["1"]`, not
  `nonzero` (`nonzero` would call `false(2)` an alarm).
- A 0/1 alarm bit where 1 is bad → `nonzero` (the default).
- Decide `trueIsProblem` from what the operator wants to hear about. For "link present",
  true is the good state, so `trueIsProblem: false`.

Treat `unknown(1)` deliberately. With `notEquals ["2"]` it reads as a fault, which is usually
what you want for a battery. Say which way you chose.

## 5. Choose per metric

For each of the five read rows, say in your answer which of these it is:

- *"CPU: standard (hrProcessorLoad), no row."* The device implements HOST-RESOURCES-MIB.
  Confirm with an SNMP walk of `std:host-resources` from the asset's SNMP Walk tool if
  unsure.
- *"Memory: vendor percent scalar `xMemUtil` (X-SYSTEM-MIB), because HRM reports no RAM
  row."*
- *"Hardware Sensors: ENTITY-SENSOR-MIB covers it, no row."*
- *"Storage: not available. The vendor exposes only a percent."*
- *"Model: discovery / sysDescr supplies it, no row."*

Prefer objects with "5 min", "1 min" or "average" in the DESCRIPTION over "5 sec" for CPU.
Polling is every telemetry pass, and a 5-second sample is mostly noise at that cadence.

## 6. Confirm on a device before shipping

In Polaris: open an asset of that vendor → **SNMP Walk** (the asset's tools), pick the
uploaded MIB, walk the chosen symbol. Check that it answers, the value's magnitude matches
your unit reading, and a column has the rows you expect. A profile whose symbols were never
walked against real hardware goes in the toolbox's `profiles/` as **untested** (see
delivery.md).
