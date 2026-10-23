# Authentication

_Generated from Polaris `public/api.html` (section `authentication`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

External callers authenticate with a long-lived bearer token, created by a Polaris administrator under **Server Settings → API Tokens**. The raw token is shown once at creation and looks like `polaris_`. Send it on every request:

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN" \
  $POLARIS_URL/api/v1/assets?limit=5
```

Every token is bound to a **Role** at creation and can do exactly what that role's permission matrix allows — the same permission gates Polaris applies to logged-in users. For least privilege, have your administrator create a purpose-built role (for example, assets read-only) rather than binding an admin-equivalent role.

- Bearer requests are exempt from CSRF checks — no CSRF token or cookie is needed.
- A missing, revoked, expired, or malformed token gets the same `401` as no token at all; the API does not distinguish.
- A token may be limited to **trusted hosts** — a list of IP addresses and CIDRs set when it is created. A valid token sent from any other address gets a `403` whose message names the source address Polaris saw (behind a reverse proxy, check that it forwards the client address). A token with no list is accepted from anywhere.
- A request the token's role does not permit gets a `403` — except on the handful of aggregate endpoints documented as *filter-don't-403*, which return the sections the role can read and leave the rest empty.
- There is no token-introspection endpoint: `GET /auth/me` answers `{"authenticated": false}` for bearer callers. To smoke-test a token, call a cheap endpoint its role can read (for example `GET /assets?limit=1`) and check for `200`.
- Writes made with a token are attributed in the Polaris audit log as `api:`.

> **Ownership-scoped resources need `fullwrite`.** Networks (subnets), reservations, and contacts carry an ownership dimension: `write` lets a caller edit only rows they created, identified by the session username. A bearer token has no username, so a token bound to a role with plain `write` on those keys can *create* rows but gets `403` on every edit/delete of an existing row. Bind tokens that must manage IPAM rows to a role granting `fullwrite` on `subnets` / `reservations`.
