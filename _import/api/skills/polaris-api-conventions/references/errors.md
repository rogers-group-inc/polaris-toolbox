# Errors & rate limits

_Generated from Polaris `public/api.html` (section `errors`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

Every error is JSON with a single `error` string:

```
{ "error": "Reservation not found" }
```

Status conventions:

- `400` — validation failure; the message names the offending field.
- `401` — missing or unusable credentials.
- `403` — authenticated, but the token's role lacks the required permission, or the token was sent from outside its trusted hosts.
- `404` — no such resource, or one outside the caller's visibility scope (Polaris deliberately answers 404 rather than 403 for scoped-away resources).
- `409` — the request conflicts with current state (overlapping subnet, deleting a block with active reservations, duplicate reservation).
- `429` — rate-limited; back off and retry. Machine-facing surfaces such as quarantine verify have generous per-IP budgets sized far above healthy polling cadences, so a 429 usually means a runaway loop.
- `5xx` — server-side failure; the body still carries `{ "error": ... }` where possible.

> Aggregate feeds (`/dashboard/*`) are cached server-side for ~10 s and shared across callers — poll them at a wallboard cadence (every 10–30 s), not in a tight loop.
