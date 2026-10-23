#!/usr/bin/env python3
"""Apply a manufacturer profile file to a Polaris install.

  python3 apply-profile.py PROFILE.json [--mibs DIR] [--dry-run] [--only ID ...]

PROFILE.json is a Polaris profile file (format "polaris.manufacturer-profile", version 1) —
what Export on a profile downloads, and what the files under ../skills/polaris-manufacturer-profiles/
profiles/ are. The script:

  1. checks which MIB modules the file needs are already uploaded, and uploads the missing ones
     from --mibs DIR (any file whose text declares "<MODULE> DEFINITIONS ::= BEGIN"), a
     module's dependencies first, under the file's manufacturer;
  2. previews the import (what each item would create or replace, what is missing);
  3. unless --dry-run, imports every item the preview does not block (or only --only IDs);
  4. reports the profile's readiness: every symbol resolves, or which do not and why;
  5. lists the custom widgets, which poll NO device until switched on per device.

Token role needs: manufacturerProfiles write, plus mibDatabase write when --mibs uploads.
Exit status: 0 = imported and every symbol resolves; 2 = something failed or is unresolved.
A human must review the profile and test it on one device before relying on it for alerts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from polaris_client import Client, PolarisError, add_connection_args  # noqa: E402

PROFILES = "/server-settings/manufacturer-profiles"
MIBS = "/server-settings/mibs"
MODULE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]*)\s+DEFINITIONS\s*::=\s*BEGIN", re.M)
IMPORTS_RE = re.compile(r"\bIMPORTS\b(.*?);", re.S)
FROM_RE = re.compile(r"\bFROM\s+([A-Za-z][A-Za-z0-9-]*)")


def scan_mib_dir(path: str) -> dict:
    """module name -> (file path, imported module names)."""
    found = {}
    for root, _dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            try:
                with open(full, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            m = MODULE_RE.search(text)
            if not m:
                continue
            imp = IMPORTS_RE.search(text)
            imports = FROM_RE.findall(imp.group(1)) if imp else []
            found.setdefault(m.group(1), (full, imports))
    return found


def uploaded_modules(client: Client, manufacturer: str) -> set:
    names = set()
    for scope in ({"manufacturer": manufacturer}, {"scope": "generic"}):
        q = "&".join(f"{k}={quote(v)}" for k, v in scope.items())
        for row in client.get(f"{MIBS}?{q}") or []:
            names.add(row["moduleName"].lower())
    return names


def upload_missing(client: Client, needed: list, mib_dir: str, manufacturer: str, dry_run: bool) -> bool:
    have = uploaded_modules(client, manufacturer)
    local = scan_mib_dir(mib_dir) if mib_dir else {}
    missing = [m for m in needed if m.lower() not in have]
    if not missing:
        print("MIBs: every module the file names is already uploaded.")
        return True
    ok = True
    done: set = set()

    def upload(module: str, depth: int = 0) -> None:
        nonlocal ok
        if module.lower() in done or module.lower() in have or depth > 10:
            return
        entry = local.get(module)
        if not entry:
            if module in missing:
                print(f"MIBs: {module} is not uploaded and not in {mib_dir or '(no --mibs given)'} — upload it, "
                      f"or rows that need it will read unresolved.")
                ok = False
            return
        path, imports = entry
        for dep in imports:  # a vendor core module before the leaf that imports it
            if dep in local:
                upload(dep, depth + 1)
        if dry_run:
            print(f"MIBs: would upload {module} from {path} under {manufacturer}")
            done.add(module.lower())
            return
        with open(path, "rb") as f:
            content = f.read()
        try:
            res = client.upload(MIBS, "file", os.path.basename(path), content, {"manufacturer": manufacturer})
            roots = res.get("unresolvedRoots") or []
            print(f"MIBs: uploaded {module} ({res.get('symbolCount', 0)} symbols)"
                  + (f" — still missing: {', '.join(sorted({r.get('module') or r.get('symbol') for r in roots}))}" if roots else ""))
        except PolarisError as e:
            print(f"MIBs: upload of {module} failed — {e.message}")
            ok = False
        done.add(module.lower())

    for m in missing:
        upload(m)
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("profile", help="profile file (polaris.manufacturer-profile v1)")
    p.add_argument("--mibs", help="folder holding the MIB files to upload when missing")
    p.add_argument("--dry-run", action="store_true", help="preview only: upload and import nothing")
    p.add_argument("--only", nargs="*", help="import only these preview item ids")
    add_connection_args(p)
    args = p.parse_args()

    with open(args.profile, encoding="utf-8") as f:
        file = json.load(f)
    if file.get("format") != "polaris.manufacturer-profile" or file.get("version") != 1:
        return print("Not a Polaris profile file (format polaris.manufacturer-profile, version 1).") or 2
    file.pop("_toolbox", None)  # toolbox metadata, not part of Polaris's format
    client = Client.from_args(args)
    manufacturer = file["manufacturer"]
    needed = [m["moduleName"] for m in file.get("mibs", [])]

    healthy = upload_missing(client, needed, args.mibs, manufacturer, args.dry_run)

    preview = client.post(f"{PROFILES}/import/preview", {"file": file})
    target = "a new profile" if not preview.get("targetProfileId") else "the existing profile"
    print(f"\nImport into {target} for {preview['manufacturer']}:")
    for item in preview["items"]:
        flag = "BLOCKED" if item.get("blocked") else item["action"]
        extra = []
        if item.get("missingMibs"):
            extra.append("missing MIB " + ", ".join(m["moduleName"] for m in item["missingMibs"]))
        if item.get("missingCredential"):
            extra.append(f"no credential named {item['missingCredential']} (imports unauthenticated)")
        if item.get("blocked"):
            extra.append(item["blocked"])
        print(f"  [{flag:7}] {item['id']}: {item['label']}" + (f"  — {'; '.join(extra)}" if extra else ""))
    if args.dry_run:
        print("\nDry run: nothing imported.")
        return 0 if healthy else 2

    chosen = args.only if args.only else [i["id"] for i in preview["items"] if not i.get("blocked")]
    result = client.post(f"{PROFILES}/import", {"file": file, "items": chosen})
    failed = [r for r in result["results"] if not r["ok"]]
    print(f"\nImported {len(result['results']) - len(failed)} of {len(result['results'])} item(s).")
    for r in failed:
        print(f"  FAILED {r['id']}: {r.get('error')}")
        healthy = False

    summary = next((s for s in client.get(PROFILES)["profiles"] if s["id"] == result["profileId"]), None)
    if summary:
        if summary["ready"]:
            print("Readiness: every symbol resolves.")
        else:
            healthy = False
            print(f"Readiness: {summary['unresolvedCount']} symbol(s) do not resolve — "
                  f"{', '.join(summary['unresolvedSymbols'])}. Upload the MIB that defines them.")

    widgets = file.get("widgets") or []
    if widgets:
        print("\nCustom widgets poll NO device until switched on for it — on each card of the asset's "
              "Custom MIB tab, the widget's Devices… button, or PUT "
              f"{PROFILES}/{result['profileId']}/widgets/<widgetId>/assets {{\"enable\": [assetId…]}}:")
        for w in widgets:
            print(f"  - {w['name']} ({w['widgetType']})")
    print("\nReview the profile and test it on one device before relying on it for alerts.")
    return 0 if healthy else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PolarisError as e:
        sys.exit(f"Polaris refused: {e}")
