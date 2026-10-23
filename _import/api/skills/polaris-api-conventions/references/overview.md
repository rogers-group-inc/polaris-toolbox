# Overview

_Generated from Polaris `public/api.html` (section `overview`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

Polaris exposes a JSON REST API for external systems — SIEM-driven quarantine, NOC kiosks and wallboards, inventory consumers, and automation scripts. Every endpoint lives under the versioned base /api/v1, requests and responses are JSON (`Content-Type: application/json`), and authentication is a bearer token minted in Polaris (see Authentication (see authentication.md)).

This reference covers the endpoint groups intended for external callers. Polaris has many more endpoints backing its own UI; those are internal, undocumented here, and may change without notice — build against what this page documents.

#### Deprecated path aliases

Three resource groups were renamed and keep their old paths mounted as deprecated aliases: `/notifications` → `/alerts`, `/notification-rules` → `/automations`, and `/notification-channels` → `/delivery-channels`. Responses on the old paths carry a `Deprecation: true` header plus a `Link: ; rel="successor-version"` header naming the replacement. Use the new paths in new integrations.
