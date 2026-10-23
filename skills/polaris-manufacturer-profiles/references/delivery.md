# Delivering a profile

## The file format

A profile travels as Polaris's own export file. Build the deliverable in exactly this shape —
it imports through the UI (**Import…** beside **+ Add Manufacturer**) and through
`scripts/apply-profile.py`, and Polaris validates it on the way in.

```json
{
  "format": "polaris.manufacturer-profile",
  "version": 1,
  "manufacturer": "<Manufacturer>",
  "matchPattern": null,
  "mibs": [ { "moduleName": "<VENDOR-MIB>", "manufacturer": "<Manufacturer>", "model": null } ],
  "metrics": [
    {
      "metricKey": "temperature",
      "symbol": "<valueColumn>", "symbolB": null,
      "mib": { "moduleName": "<VENDOR-MIB>", "manufacturer": "<Manufacturer>", "model": null }, "mibStdKey": null,
      "type": "table", "transform": null, "aggregate": "none", "label": null,
      "parsePattern": null, "parseTemplate": null,
      "sensorColumns": { "nameSymbol": "<nameColumn>", "alarmSymbol": null, "alarmMap": null,
                         "sensorClass": "temperature", "transform": null },
      "overrides": []
    }
  ],
  "widgets": [],
  "layout": null
}
```

Every `<…>` is a placeholder: the symbols come from the operator's MIB (search it, or ask the
operator to), never from memory. For a complete real file, see
[../profiles/Fortinet.manufacturer-profile.json](../profiles/Fortinet.manufacturer-profile.json).

- **`metrics`** lists only the rows the profile sets; a row left out keeps "no opinion" on
  import. `metricKey` is `model`, `cpu`, `memory`, `temperature`, `interfaces`, `storage`,
  `lldp` or `wirelessStations`. Every field of a metric row is present (null when unused) —
  [profile-model.md](profile-model.md) has each one's rules.
- **`overrides`** under a metric carry the same fields plus `assetType`, `modelPattern`
  (at least one set) and `order`.
- **`mib` / `mibs`** name modules by `moduleName` + the manufacturer (and model) they are
  uploaded under. Import finds a module under the target profile's manufacturer, then the
  file's, then a generic upload.
- **`widgets`** each need a unique `key` (any short id, e.g. `w1`) — `layout` refers to
  widgets by key. A widget's credential is `{ "name": "…" }`, never an id.
- No `id` anywhere, no `exportedAt` needed, no secrets, no per-device widget switches.

## Applying it

**Upload the MIBs first, then import.** A row whose module is not uploaded at import time
imports with its MIB link empty — the symbol still resolves once the module arrives, but
readiness can no longer say which module to upload. A widget whose module is missing is
blocked from import.

With a token (role: `manufacturerProfiles` write, plus `mibDatabase` write to upload):

```bash
export POLARIS_URL=https://polaris.example.com
export POLARIS_TOKEN=polaris_…           # or --token-file
python3 scripts/apply-profile.py APC.manufacturer-profile.json --mibs ./apc-mibs --dry-run
python3 scripts/apply-profile.py APC.manufacturer-profile.json --mibs ./apc-mibs
```

The script uploads the modules the file names that the install lacks (from `--mibs`, a
module's dependencies first), previews the import, imports every item the preview does not
block, prints readiness and lists the widgets to switch on. Exit 0 = imported and READY.

The same thing over raw API calls, in order:

1. `GET /server-settings/mibs?manufacturer=<Name>` — what is uploaded.
2. `POST /server-settings/mibs` (multipart: `file`, `manufacturer`) per missing module, core
   module first; read `unresolvedRoots` in each answer.
3. `POST /server-settings/manufacturer-profiles/import/preview` `{ "file": … }` — the items,
   each `create` / `replace`, with `missingMibs` and `blocked`.
4. `POST /server-settings/manufacturer-profiles/import` `{ "file": …, "items": [ids] }`.
5. `GET /server-settings/manufacturer-profiles` — the profile's `ready` /
   `unresolvedSymbols`.
6. Per widget: `PUT /server-settings/manufacturer-profiles/<id>/widgets/<widgetId>/assets`
   `{ "enable": [assetId…] }` (also needs `assets` write).

## The UI walkthrough

Give the operator these steps, in these words:

1. **Server Settings → Credentials → MIB Database → Upload** each module, choosing the
   manufacturer from the picker (it lists inventory names with device counts). Upload the core
   module first; the result says if a module is still missing.
2. **Manufacturer Profiles → Import…** the file — tick the items, **Import** — *or* build by
   hand: **+ Add Manufacturer**, pick the name, expand the profile.
3. For each row: **Edit**, choose the **MIB**, the **Type** (scalar / double scalar / table),
   type the **Symbol** (the box filters the MIB's symbols as you type), set the transform /
   walk / label / parse fields under it, **Save**. A Hardware Sensors table row shows the
   table-column fields under its Symbol.
4. Per device family: under the row, pick a **device type** and / or type a **model regex**,
   fill the same fields, **Add**.
5. Widgets: **+ Add widget**, then tick the devices in the list Polaris opens, **Enable**.
6. **Also applies when** on the profile header, only for alias spellings no Manufacturer
   Alias covers.

## Verifying it

- Every configured row's **MIB** cell names the module it resolved from; the header says
  **READY**. An unresolved row names what to upload.
- Open one asset of the vendor: its **System** tab (CPU & memory, Hardware Sensors, Storage)
  fills within about a minute plus one poll; its **Custom MIB** tab shows switched-on widgets
  after the next hardware-sensor interval.
- The asset's **SNMP Walk** tab, with the uploaded MIB chosen, shows the raw answer to any
  symbol — the fastest way to tell "no such object on this device" from "wrong symbol".
- The Events log carries `manufacturer_profile.*` for every change, and
  `manufacturer_profile.unresolved` after a restart if a symbol stopped resolving.

## Exporting

`python3 scripts/export-profiles.py --out DIR [--manufacturer Name] [--tested-on "…"]` writes
each profile as a file (token role: `manufacturerProfiles` read). `--tested-on` records
provenance for the toolbox's [profiles/](../profiles/README.md) library.
