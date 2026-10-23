// Minimal Polaris API client (Node 20+, no dependencies). Copy and adapt.
//
//   const polaris = createPolarisClient({ baseUrl: process.env.POLARIS_URL!, token: process.env.POLARIS_TOKEN! });
//   const { assets, total } = await polaris.get<{ assets: unknown[]; total: number }>("/assets", { search: "fw-", limit: 25 });
//
// Conventions encoded here: bearer auth on every call, JSON error envelope { error }, page with
// `total` (never .length), 429 backoff with retry, 404 means "not visible to you" as much as "absent".

export class PolarisError extends Error {
  constructor(public status: number, message: string, public body: unknown) {
    super(`${status} ${message}`);
  }
}

export interface PolarisClientOptions {
  baseUrl: string; // e.g. https://polaris.example.com  (no trailing /api/v1)
  token: string;   // polaris_<32-char tail>, from Server Settings → API Tokens
  maxRetries?: number;
  fetchImpl?: typeof fetch;
}

export function createPolarisClient(opts: PolarisClientOptions) {
  const base = opts.baseUrl.replace(/\/+$/, "") + "/api/v1";
  const f = opts.fetchImpl ?? fetch;
  const maxRetries = opts.maxRetries ?? 3;

  async function request<T>(method: string, path: string, query?: Record<string, string | number | boolean | undefined>, body?: unknown): Promise<T> {
    const url = new URL(base + path);
    for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined) url.searchParams.set(k, String(v));
    for (let attempt = 0; ; attempt++) {
      const res = await f(url, {
        method,
        headers: { Authorization: `Bearer ${opts.token}`, ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      if (res.status === 429 && attempt < maxRetries) {
        const retryAfter = Number(res.headers.get("retry-after")) || 2 ** attempt;
        await new Promise((r) => setTimeout(r, retryAfter * 1000));
        continue;
      }
      if (res.status === 204) return undefined as T;
      const text = await res.text();
      const json = text ? safeJson(text) : undefined;
      if (!res.ok) {
        const msg = (json && typeof json === "object" && "error" in json && typeof (json as { error: unknown }).error === "string") ? (json as { error: string }).error : res.statusText;
        throw new PolarisError(res.status, msg, json ?? text);
      }
      return json as T;
    }
  }

  return {
    get: <T>(path: string, query?: Record<string, string | number | boolean | undefined>) => request<T>("GET", path, query),
    post: <T>(path: string, body?: unknown) => request<T>("POST", path, undefined, body),
    put: <T>(path: string, body?: unknown) => request<T>("PUT", path, undefined, body),
    delete: <T>(path: string) => request<T>("DELETE", path),

    /** Iterate a paged list ({ <key>: [], total }) to exhaustion using total, not .length. */
    async *pages<T>(path: string, key: string, query: Record<string, string | number | boolean | undefined> = {}, limit = 200) {
      let offset = 0;
      for (;;) {
        const page = await request<Record<string, unknown> & { total: number }>("GET", path, { ...query, limit, offset });
        const items = (page[key] as T[]) ?? [];
        yield* items;
        offset += items.length;
        if (offset >= page.total || items.length === 0) return;
      }
    },

    /** SIEM flow: quarantine by MAC / IP / hostname. Returns the per-FortiGate targets. */
    async quarantineByIdentifier(identifier: string, reason: string) {
      const avail = await request<{ pushEnabled: boolean }>("GET", "/assets/quarantine-availability");
      if (!avail.pushEnabled) throw new Error("quarantine push is not enabled on any integration");
      const found = await request<{ assets: Array<{ id: string; hostname?: string }>; total: number }>("GET", "/assets", { search: identifier, limit: 5 });
      if (found.total !== 1) throw new Error(`expected exactly one asset for ${identifier}, found ${found.total}`);
      return request<{ assetId: string; status: string; targets: unknown[]; succeededCount: number; failedCount: number; message: string }>(
        "POST", `/assets/${found.assets[0].id}/quarantine`, { reason });
    },
  };
}

function safeJson(text: string): unknown {
  try { return JSON.parse(text); } catch { return undefined; }
}
