---
name: polaris-manufacturer-profiles
description: "Builds Polaris manufacturer profiles — the per-vendor SNMP telemetry mapping in Server Settings → Identification → Manufacturer Profiles — from the vendor's MIB text: which symbol each metric row (Model identity, CPU, Memory, Hardware Sensors, Storage) walks, its type / combiner / aggregate / label, device-type defaults and per-model exceptions, custom widgets (gauge / line / table / http) and state probes, and the MIB modules that must be uploaded for the symbols to resolve. Delivers a profile spec JSON, an apply script for /api/v1/server-settings/manufacturer-profiles, and a click-by-click UI walkthrough. Load whenever someone asks to add a vendor or device to Polaris monitoring, build or fix a manufacturer profile, map MIB objects to CPU / memory / temperature / storage, make a custom MIB widget or state probe, explain why a profile row shows unresolved or collects nothing, or reuse one of the tested profiles in this plugin."
---

# Polaris manufacturer profiles

Polaris ships the monitoring engine and the IETF/IEEE standard MIBs, and **no vendor OIDs at
all**. A vendor's OIDs come from the MIB the operator uploads. The mapping (which symbol means
CPU, which pair means memory) is a **manufacturer profile**: rows the operator owns and edits.
This skill writes that profile, so a new vendor needs a file, not a Polaris release.

A profile row names a **symbol**. It saves even when nothing resolves it ("type the symbol,
then upload the MIB" is the expected order), so a row can save cleanly and collect nothing.
Most of this skill is about avoiding that.

## A deliverable is four things

| # | What | Where it goes |
|---|---|---|
| 1 | **MIB list**: every module the symbols need, leaf *and* the core module it IMPORTS from, with the manufacturer scope to upload under | Server Settings → Identification → **MIB Database**, or `POST /server-settings/mibs` |
| 2 | **Profile spec**: one JSON file in the format in [references/delivery.md](references/delivery.md) | saved beside the MIBs; `scripts/apply-profile.py` reads it |
| 3 | **Apply command**: the `apply-profile.py` call for this spec, with the token's required role | run by the operator |
| 4 | **UI walkthrough**: the same profile as clicks | for an operator without a token |

Then the **verification step**: which asset to open, which tab should fill, and in how long.

## Which file

| You need… | Read |
|---|---|
| the data model: profile, the eight metric rows, override rows, widgets, every field and every validation the API applies | [references/profile-model.md](references/profile-model.md) |
| **what the collectors actually do with each row**: which rows are read, scalar vs walked, combiner meaning, fallbacks to the standard MIBs, override precedence, the traps | [references/runtime-semantics.md](references/runtime-semantics.md) |
| how to read a vendor MIB and choose symbols: scalar vs column, SYNTAX / UNITS / DISPLAY-HINT, enum polarity, IMPORTS and the core module | [references/reading-mibs.md](references/reading-mibs.md) |
| custom widgets and state probes: widget types, displayOptions, stateMap modes, label columns, HTTP checks | [references/widgets-and-state-probes.md](references/widgets-and-state-probes.md) |
| the spec format, the apply / export scripts, the API sequence, the UI walkthrough, readiness and verification | [references/delivery.md](references/delivery.md) |
| the profiles Polaris seeds on first boot, written as specs | [references/seeded-profiles.md](references/seeded-profiles.md) |
| profiles tested on real hardware: check here first | [profiles/](profiles/) (`README.md` lists them) |

## The ten things that are always true

1. **Check the tested library first.** If [profiles/](profiles/) has the vendor, start from that
   spec and say so. Only build from scratch when it doesn't.
2. **The manufacturer name is the key, and it must match the assets exactly.** A profile
   applies to assets whose alias-normalized `manufacturer` equals the profile's name
   (case-insensitive). Look up the spelling Polaris already uses (the **+ Add Manufacturer**
   typeahead, or `GET /server-settings/manufacturer-profiles/suggestions`) and use it.
   "Aruba Networks" and "Aruba" are two different keys. `matchPattern` ("Also applies when")
   is a fallback, consulted only when no profile is keyed by the asset's manufacturer, and
   **custom widgets ignore it**.
3. **A symbol resolves only from an uploaded MIB at that manufacturer's scope**, or from the
   bundled standard MIBs. Upload the leaf module *and* every vendor module its IMPORTS name
   (FORTINET-FORTIGATE-MIB needs FORTINET-CORE-MIB). Upload with the manufacturer set to the
   profile's exact name. A generic (no-manufacturer) upload works too but applies to every
   device.
4. **Only five metric rows are read**: Model identity, CPU, Memory, Hardware Sensors
   (`temperature`), Storage. `interfaces`, `lldp` and `wirelessStations` are display-only.
   Leave them empty: they save and do nothing.
5. **Don't override what the standard MIBs already do.** CPU and memory fall back to
   HOST-RESOURCES-MIB, storage reads `hrStorageTable` first, and sensors read ENTITY-SENSOR-MIB
   first. A device that implements those (most Linux-based gear: MikroTik, Synology, many
   appliances) needs no row for that metric. Write a row only where the vendor MIB is the
   **only** source.
6. **Scalar means `.0`.** A `scalar` row GETs `<oid>.0`. A table **column** must be walked
   (`aggregate` `avg`/`sum`, or CPU `type: table`). A column on a scalar row returns nothing.
7. **CPU must already be a percent (0–100).** There is no CPU transform. Memory is either a
   percent scalar, or a byte pair whose combiner names the pair: `a_over_b_as_percent` =
   (used, total), `a_over_a_plus_b_as_percent` = (used, free). Any other combiner leaves
   memory uncollected.
8. **Hardware Sensors `table` only works on Fortinet.** A `table` row walks Fortinet's
   `fgHwSensorTable` whatever symbol it names. For any other vendor, use a `scalar` row (one
   reading, optional `tenths_to_units`) or state probes / widgets.
9. **Every pattern is RE2, case-insensitive, ≤ 512 chars**: no lookaround, no
   backreferences. That covers `matchPattern`, `modelPattern` and `parsePattern`. The Model
   identity row needs a capture group, and it only stamps `Asset.model` while the asset's
   model is still empty.
10. **Profiles only drive SNMP collection.** An asset polled for CPU/memory by agent,
    FortiOS REST, vCenter etc. never reads its profile, and custom widgets need the asset's
    CPU/memory polling (or its custom-widget polling) set to SNMP, with an SNMP credential.

## How to work

1. Identify the vendor, the device families (switch / AP / firewall / UPS…), and the
   manufacturer spelling on the assets. Ask for the MIB files if you don't have them. Don't
   invent symbol names from memory: every symbol in a spec must appear in a MIB the operator
   can upload, and you cite the module.
2. For each of the five read rows, decide **standard MIB already covers it**, **vendor
   symbol**, or **not available**. Record the reason in the spec's `notes`.
3. If families differ (switch vs AP under one vendor), use device-type defaults first and
   model-pattern exceptions only where a model needs something different.
   [runtime-semantics.md](references/runtime-semantics.md) § overrides has the precedence
   trap.
4. Add widgets / state probes only for things the five rows can't carry (PSU, fan, battery,
   alarm bits, client counts).
5. Emit the four parts, then the verification step. Close with the reminder that **a human
   must review the profile and test it on one device before relying on it for alerting.** An
   unresolved or misread row means a metric that silently isn't collected, or an automation
   that never fires.

## Scope

Application behaviour only: what a profile row means to Polaris and how to write one that
collects. No install's hostnames, credentials, asset names or IDs belong in a spec. The export
script strips them, and a hand-written spec never needs them.
