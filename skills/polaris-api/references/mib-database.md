# MIB Database

_Generated from Polaris `public/api.html` (section `mib-database`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

The SNMP MIB modules Polaris resolves symbol names against. Polaris bundles the IETF / IEEE standard MIBs (SNMPv2-MIB, IF-MIB, HOST-RESOURCES-MIB, ENTITY-MIB, ENTITY-SENSOR-MIB, LLDP-MIB, POWER-ETHERNET-MIB, BRIDGE-MIB, Q-BRIDGE-MIB, RSTP-MIB, IP-MIB) and no vendor's: a vendor's objects resolve only from the module you upload, under that vendor's manufacturer name. Endpoints gate on `mibDatabase`.

### GET /server-settings/mibs

_Gate: mibDatabase:read_

Uploaded modules: `[{ id, filename, moduleName, manufacturer, model, imports, size, notes, uploadedBy, uploadedAt }]`. Filters: `scope=all|device|generic`, `manufacturer`, `model` (case-insensitive exact). `manufacturer: null` is a generic module, resolved for every device.

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN" \
  "$POLARIS_URL/api/v1/server-settings/mibs?manufacturer=APC"
```

### POST /server-settings/mibs

_Gate: mibDatabase:write_

Upload one module as `multipart/form-data`: `file` (the MIB text, ≤ 6 MiB — `413` beyond), optional `manufacturer`, `model` (needs a manufacturer) and `notes`. The text must parse as an SMI module (` DEFINITIONS ::= BEGIN … END`); binaries are refused. `(manufacturer, model, moduleName)` is unique — `409` on a second copy. `201` with the stored row plus `symbolCount`, `unresolvedCount` and `unresolvedRoots: [{ symbol, module }]`: a non-empty list names the module still missing (a vendor leaf module usually IMPORTs a core module — upload both, the core one first).

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN" \
  -F "file=@FORTINET-CORE-MIB.mib" -F "manufacturer=Fortinet" \
  "$POLARIS_URL/api/v1/server-settings/mibs"
```

### GET /server-settings/mibs/:id/structure

_Gate: mibDatabase:read_

The module parsed: `symbols: [{ name, parentName, fullOid, kind, syntax, baseType, enumValues, access, status, description, isTableRow, indexNames }]` and `tables: [{ name, rowSymbol, columns, indexNames }]`, each symbol's `fullOid` resolved (or `null`), plus `unresolvedCount` and `unresolvedRootDetails` naming what to upload. This is the endpoint to read when choosing which symbol a profile row should walk. `GET /server-settings/mibs/:id` returns the row with its `contents`; `/:id/download` the raw file.

### POST /server-settings/mibs/:id/walk

_Gate: mibDatabase:read_

Walk one object of this module on a device: `{ assetId, credentialId, objectName, maxRows? }` (`maxRows` ≤ 5000, default 500; the credential is an SNMP one). Returns the values decoded against the module — enum labels such as `onLine(2)`, and a table grouped into rows when the object is a table. Use it to confirm a symbol answers before putting it in a profile.

### GET /server-settings/mibs/std

_Gate: mibDatabase:read_

The bundled standard modules by key (`std:system`, `std:interfaces`, `std:host-resources`, `std:entity-sensor`, …). `/std/:key/structure` and POST `/std/:key/walk` work like the uploaded-module pair. `GET /server-settings/mibs/facets` lists the manufacturers and models in the inventory with device counts — the names to upload under.

### DELETE /server-settings/mibs/:id

_Gate: mibDatabase:write_

`204`. Profile rows that resolved through it read unresolved until it is uploaded again.
