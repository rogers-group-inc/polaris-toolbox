# Search

_Generated from Polaris `public/api.html` (section `search`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

### GET /search?q=

_Gate: per-group read keys · filter-don't-403_

Global typeahead across seven groups. Response: `{ query, blocks, subnets, reservations, assets, ips, sites, ipsec }` — every group always present; groups the role can't read (or that didn't match) are empty arrays. Group gates: blocks→`ipBlocks`, subnets→`subnets`, reservations→`reservations`, assets→`assets`, sites→`deviceMap`, ipsec→`assets`; the `ips` cross-reference needs both `subnets` and `reservations` read.

- Minimum 2 characters (1 when scoped). Terms are AND-combined; `"quoted phrases"` stay whole; single terms get IP/CIDR/MAC special-casing.
- Scope prefixes: `block:`/`b:`, `network:`/`n:`, `asset:`/`a:`, `reservation:`/`r:`, `map:`/`m:`, `tag:`/`t:` (tag spans blocks + networks + assets), `ipsec:`/`vpn:`/`v:`.
- `ipsec` hits are a FortiGate's phase-1 tunnels (newest state at or after the gate's last full system-info pass) and the peers / VPN users connected through them, matched on tunnel name, remote gateway, peer id, user name, underlay or overlay address. `type` is `"ipsec"`, `id` is `|tunnel|` or `|conn|`, `status` is `up`/`down`/`partial`, and `context` carries `assetId` (the gate), `kind`, `tunnelName` or `name`, `remoteGateway`, `userName`, and `peerAssetId`/`peerHostname` when the far end resolves to an asset. The gate's own hostname is not a searched column.
- A query of 8+ characters that reads as a thumbprint — a TLS SHA-256 fragment (hex, colons / spaces / dashes ignored) or an SSH host-key fingerprint fragment (with or without `SHA256:`) — also returns the asset(s) that pin belongs to, live or archived on decommission, first in `assets`, with `context.pinMatch` `{ kind: "ssh"|"tls", host, port, archived }`. Needs `serverSettingsSystem` read as well as `assets`.
- Caps: 8 hits per group unscoped; 200 for a scoped query. No paging — scope the query instead.
