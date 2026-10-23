# IPAM: IP blocks

_Generated from Polaris `public/api.html` (section `ipam-blocks`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

Top-level CIDR namespaces. Reads: `ipBlocks:read`; writes: `ipBlocks:write`.

### GET /blocks

_Gate: ipBlocks:read_

All blocks as a JSON array (no paging), each with a subnet count (`_count.subnets`) and `utilizationPercent` — the share (0–100) of the block's address space carved into non-deprecated networks. Filters: `ipVersion` (`v4`/`v6`), `tag`.

### GET /blocks/:id

_Gate: ipBlocks:read_

One block including its `subnets[]` (each with a reservation count).

### POST /blocks

_Gate: ipBlocks:write_

Body: `{ name, cidr, description?, tags? }`. The CIDR is normalized (host bits zeroed) and the IP version derived server-side. `201` with the block; `400` invalid CIDR; `409` duplicate CIDR.

### PUT /blocks/:id

_Gate: ipBlocks:write_

Body: `{ name?, description?, tags? }`. The CIDR itself is not updatable.

### DELETE /blocks/:id

_Gate: ipBlocks:write_

`204` on success; `409` while the block contains any network, whatever its status. Move networks out with `POST /subnets/:id/move`, archive or delete them first.
