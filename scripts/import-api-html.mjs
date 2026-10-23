#!/usr/bin/env node
// import-api-html.mjs — regenerate skills/polaris-api-conventions/references/*.md from a Polaris
// checkout's public/api.html (the deliberately curated external API contract). One Markdown file
// per <section>, each endpoint block → "### METHOD /path" with its gate, prose and curl example.
// Records the source file's sha256 in .claude-plugin/plugin.json so drift is visible.
//
//   node scripts/import-api-html.mjs <path-to-polaris>/public/api.html
import { readFileSync, writeFileSync, mkdirSync, readdirSync, unlinkSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const PLUGIN = resolve(here, "..");
const OUT = join(PLUGIN, "skills", "polaris-api-conventions", "references");
const src = process.argv[2];
if (!src) { console.error("usage: node scripts/import-api-html.mjs <polaris>/public/api.html"); process.exit(2); }
const html = readFileSync(src, "utf8").replace(/\r\n/g, "\n");

// ---------- tiny HTML → Markdown for the subset api.html uses ----------
const ent = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&nbsp;/g, " ").replace(/&mdash;/g, "—").replace(/&rsquo;/g, "’").replace(/&quot;/g, '"');
const ws = (s) => s.replace(/\s+/g, " ").trim();
function inline(s) {
  return ent(
    s
      .replace(/<span class="js-base-url">[^<]*<\/span>/g, "$POLARIS_URL/api/v1")
      .replace(/<code>([\s\S]*?)<\/code>/g, (_, c) => "`" + ent(c).replace(/\s+/g, " ") + "`")
      .replace(/<strong>([\s\S]*?)<\/strong>/g, "**$1**")
      .replace(/<em>([\s\S]*?)<\/em>/g, "*$1*")
      .replace(/<a href="#([^"]+)">([\s\S]*?)<\/a>/g, (_, id, t) => `${ws(t)} (see ${id}.md)`)
      .replace(/<span class="method m-\w+"[^>]*>(\w+)<\/span>/g, "$1")
      .replace(/<[^>]+>/g, ""),
  );
}
function block(s) {
  // paragraphs, lists, notes, pre blocks → markdown
  const out = [];
  const re = /<(p|ul|div class="docs-note"|pre[^>]*)>([\s\S]*?)<\/(?:p|ul|div|pre)>/g;
  let m;
  while ((m = re.exec(s))) {
    const tag = m[1], body = m[2];
    if (tag === "p") out.push(ws(inline(body)));
    else if (tag === "ul") out.push([...body.matchAll(/<li>([\s\S]*?)<\/li>/g)].map((li) => "- " + ws(inline(li[1]))).join("\n"));
    else if (tag.startsWith("div")) out.push("> " + ws(inline(body)));
    else if (tag.startsWith("pre")) {
      const code = ent(body.replace(/<span class="js-base-url">[^<]*<\/span>/g, "$POLARIS_URL/api/v1").replace(/<\/?code>/g, "").replace(/<[^>]+>/g, ""));
      out.push("```" + (tag.includes("curl") ? "bash" : "") + "\n" + code.trim() + "\n```");
    }
  }
  return out.join("\n\n");
}

// ---------- sections ----------
const sections = [...html.matchAll(/<section id="([^"]+)">([\s\S]*?)<\/section>/g)];
if (!sections.length) { console.error("no <section id=...> blocks found — is this api.html?"); process.exit(1); }
mkdirSync(OUT, { recursive: true });
for (const f of readdirSync(OUT)) if (f.endsWith(".md")) unlinkSync(join(OUT, f));
const index = [];
for (const [, id, body] of sections) {
  const h2 = ws(inline((/<h2>([\s\S]*?)<\/h2>/.exec(body) || [, id])[1]));
  const parts = [];
  // split into: intro (before first .endpoint), endpoints, trailing text
  const endpointRe = /<div class="endpoint">([\s\S]*?)<\/div>\s*(?=<div class="endpoint">|<\/section>|<p>|$)/g;
  const firstEp = body.search(/<div class="endpoint">/);
  const intro = firstEp >= 0 ? body.slice(0, firstEp) : body;
  const introMd = block(intro.replace(/<h2>[\s\S]*?<\/h2>/, "").replace(/<h3>([\s\S]*?)<\/h3>/g, (_, t) => `</p><p>#### ${ws(inline(t))}</p><p>`));
  if (introMd) parts.push(introMd);
  if (firstEp >= 0) {
    const rest = body.slice(firstEp);
    const eps = rest.split(/<div class="endpoint">/).slice(1);
    for (const ep of eps) {
      const head = /<div class="endpoint-head">([\s\S]*?)<\/div>/.exec(ep);
      const methodM = /<span class="method m-\w+">(\w+)<\/span>\s*([^<\n]+)/.exec(head ? head[1] : "");
      const gate = /<span class="gate">([\s\S]*?)<\/span>/.exec(head ? head[1] : "");
      const title = methodM ? `### ${methodM[1]} ${ws(inline(methodM[2]))}` : "### (endpoint)";
      const gateLine = gate ? `_Gate: ${ws(inline(gate[1]))}_` : "";
      const bodyOnly = ep.replace(/<div class="endpoint-head">[\s\S]*?<\/div>/, "");
      // the endpoint div ends at its closing </div>; anything after belongs to the section (trailing <p>)
      const closeIdx = bodyOnly.search(/<\/div>\s*(?:<p>|<\/section>|$)/);
      const inner = closeIdx >= 0 ? bodyOnly.slice(0, closeIdx) : bodyOnly;
      const trailing = closeIdx >= 0 ? bodyOnly.slice(closeIdx).replace(/^<\/div>/, "") : "";
      parts.push([title, gateLine, block(inner)].filter(Boolean).join("\n\n"));
      const trailMd = block(trailing.replace(/<\/section>[\s\S]*$/, ""));
      if (trailMd) parts.push(trailMd);
    }
  }
  const md = `# ${h2}\n\n_Generated from Polaris \`public/api.html\` (section \`${id}\`). Do not edit by hand — re-run \`scripts/import-api-html.mjs\`._\n\n` + parts.join("\n\n") + "\n";
  writeFileSync(join(OUT, `${id}.md`), md, "utf8");
  index.push({ id, h2, endpoints: (md.match(/^### /gm) || []).length });
}

// stamp the source hash
const sha = createHash("sha256").update(readFileSync(src)).digest("hex");
const manifestPath = join(PLUGIN, ".claude-plugin", "plugin.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
manifest.sourceApiHtmlSha256 = sha;
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf8");
console.log(`wrote ${index.length} reference files to ${OUT} (source sha256 ${sha.slice(0, 12)}…)`);
for (const s of index) console.log(`  ${s.id}.md — ${s.h2} (${s.endpoints} endpoints)`);
