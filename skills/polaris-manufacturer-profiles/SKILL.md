---
name: polaris-manufacturer-profiles
description: "Builds Polaris manufacturer profiles — the per-vendor SNMP telemetry mapping in Server Settings → Credentials → Manufacturer Profiles — from the vendor's MIB text: which symbol each metric row (Model identity, CPU, Memory, Hardware Sensors, Storage) reads, its type / combiner / aggregate / label, a Hardware Sensors sensor TABLE (value, name and alarm columns), device-type defaults and per-model exceptions, custom widgets (gauge / line / value / table / http) and state probes, and the MIB modules to upload. Delivers a profile file in Polaris's own export format (polaris.manufacturer-profile v1), the apply script that uploads the MIBs and imports it, and a click-by-click UI walkthrough. Load whenever someone asks to add a vendor or device to Polaris monitoring, build, fix or review a manufacturer profile, map MIB objects to CPU / memory / temperature / storage, describe a vendor sensor table, make a custom MIB widget or state probe, explain why a profile row shows unresolved or collects nothing, export or import a profile, or reuse one of the profiles in this toolbox."
---

# Polaris manufacturer profiles

Polaris ships the monitoring engine and the IETF/IEEE standard MIBs, and **no vendor OIDs at
all**. A vendor's OIDs come from the MIB the operator uploads. The mapping (which symbol means
CPU, which table holds the sensors) is a **manufacturer profile**: rows the operator owns.
This skill writes that profile, so a new vendor needs a file, not a Polaris release.

A profile row names a **symbol**. It saves even when nothing resolves it ("type the symbol,
then upload the MIB" is the expected order), so a row can save cleanly and collect nothing.
Most of this skill is about avoiding that.

## A deliverable is four things

| # | What | Where it goes |
|---|---|---|
| 1 | **MIB list**: every module the symbols need (the leaf *and* the core module it IMPORTS), each with the manufacturer to upload it under, and where to download it | Server Settings → Credentials → **MIB Database**, or the apply script |
| 2 | **Profile file** in Polaris's export format, `polaris.manufacturer-profile` v1 ([references/delivery.md](references/delivery.md)) | **Import…** on the Manufacturer Profiles card, or the apply script |
| 3 | **Apply command**: `scripts/apply-profile.py` with the MIB folder and the file | run by the operator, with a token |
| 4 | **UI walkthrough**: the same profile as clicks | for an operator without a token |

Then the **verification step**: which asset to open, which tab should fill, and in how long.

## Which file

| You need… | Read |
|---|---|
| profiles in this toolbox: **check here first** | [profiles/README.md](profiles/README.md) |
| the data model: profile, the eight metric rows, override rows, widgets, every field and every validation | [references/profile-model.md](references/profile-model.md) |
| **what the collectors actually do with each row**: which rows are read, scalar vs walked, combiner meaning, standard-MIB fallbacks, the sensor table, override precedence, the traps | [references/runtime-semantics.md](references/runtime-semantics.md) |
| how to read a vendor MIB and choose symbols: scalar vs column, SYNTAX / UNITS / DISPLAY-HINT, enum polarity, IMPORTS and the core module | [references/reading-mibs.md](references/reading-mibs.md) |
| custom widgets and state probes: types, displayOptions, stateMap modes, label columns, HTTP checks, the per-device switch | [references/widgets-and-state-probes.md](references/widgets-and-state-probes.md) |
| the file format, the apply / export scripts, the API calls, the UI walkthrough, readiness and verification | [references/delivery.md](references/delivery.md) |

## The ten things that are always true

1. **Check the toolbox's profiles first.** If [profiles/](profiles/) has the vendor, start from
   that file and say so; build from scratch only when it doesn't.
2. **The manufacturer name decides which devices a profile covers.** A profile covers devices
   whose alias-normalized manufacturer is its name (case-insensitive). Only when no profile has
   a device's own name does a profile's `matchPattern` ("Also applies when") reach it — and then
   it reaches everything: rows, widgets, MIBs (Polaris rule 131). Use the spelling Polaris
   already shows (the **+ Add Manufacturer** suggestions, or
   `GET /server-settings/manufacturer-profiles/suggestions`).
3. **A symbol resolves only from an uploaded MIB**, or from the bundled standard MIBs. Upload
   the leaf module *and* every vendor module its IMPORTS name (FORTINET-FORTIGATE-MIB needs
   FORTINET-CORE-MIB), under the profile's manufacturer name. A device's own manufacturer and
   model uploads are tried first, then the profile's name.
4. **Only five metric rows are read**: Model identity, CPU, Memory, Hardware Sensors
   (`temperature`), Storage. `interfaces`, `lldp` and `wirelessStations` are display-only —
   leave them empty.
5. **Don't override what the standard MIBs already do.** CPU and memory fall back to
   HOST-RESOURCES-MIB; storage reads `hrStorageTable` first; sensors read ENTITY-SENSOR-MIB
   first. Write a row only where the vendor MIB is the **only** source.
6. **Scalar means `.0`.** A `scalar` row GETs `<oid>.0`. A table **column** must be walked
   (`aggregate` `avg` / `sum`, CPU `type: table`, or a Hardware Sensors table). A column on a
   scalar row returns nothing.
7. **CPU must already be a percent (0–100)** — there is no CPU transform. Memory is a percent
   scalar, or a byte pair whose combiner names the pair: `a_over_b_as_percent` = (used, total),
   `a_over_a_plus_b_as_percent` = (used, free). Any other combiner leaves memory uncollected.
8. **A Hardware Sensors `table` row is a whole sensor table** (Polaris rule 132): its symbol is
   the VALUE column, and `sensorColumns` names the name column, an optional alarm column with
   its mapping, an optional fixed class and a `tenths_to_units` scale. No vendor's table is
   built in — FortiGate's included.
9. **Every pattern is RE2, case-insensitive, ≤ 512 chars** — no lookaround, no backreferences.
   The Model identity row needs a capture group, and it stamps `Asset.model` only while the
   device's model is empty.
10. **Profiles drive SNMP collection only, and widgets poll only where switched on.** A device
    whose CPU/memory come from the agent, FortiOS REST or vCenter never reads its profile's
    rows. A custom widget polls a device only after it is switched on for it (Polaris rule
    130), using the device's first SNMP credential.

## How to work

1. Identify the vendor, the device families (switch / AP / firewall / UPS…), and the
   manufacturer spelling on the assets. Ask for the MIB files if you don't have them. Never
   write a symbol from memory: every symbol must appear in a MIB the operator can upload, and
   you name the module.
2. For each of the five read rows decide: **standard MIB already covers it**, **vendor
   symbol**, or **not available**, and say which in your answer.
3. If families differ (switch vs AP under one vendor), use device-type defaults first and
   model-pattern rows where a model needs something different —
   [runtime-semantics.md](references/runtime-semantics.md) § overrides has the precedence trap.
4. Add widgets / state probes only for what the five rows can't carry (PSU, fan, battery,
   alarm bits, client counts).
5. Emit the four parts, then the verification step. Close with the reminder that **a human must
   review the profile and test it on one device before relying on it for alerting** — an
   unresolved or misread row is a metric silently not collected, or an automation that never
   fires.

## Scope

Application behaviour only: what a profile row means to Polaris and how to write one that
collects. A profile file carries no install's hostnames, credentials, asset names or ids —
Polaris's export leaves them out, and a hand-written file never needs them.
