#!/usr/bin/env python3
"""Export Polaris automations as rule files another install can apply.

  python3 export-automations.py --out DIR [--name TEXT ...]

Writes one <name>.rule.json per rule: the body POST /api/v1/automations accepts, without its id,
timestamps or alert-group link. (Not the UI's Export file — that is `.automation.json`, carries a
dependencies block and strips api_call / script / reboot actions; this keeps every action, with
api_call header values masked.) What is NOT portable is said, not hidden:

  - every email address becomes a numbered placeholder (<recipient-1@example.com>) — recipients
    are people, and a file meant for sharing must not carry them;
  - api_call header values arrive MASKED from Polaris and stay masked: enter the real value
    after applying, on the target install;
  - delivery channel, user, script and asset ids are per-install: remap them on the target
    (the file lists which it found under "_toolbox.remap").

Token role needs: automationManagement read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from polaris_client import Client, PolarisError, add_connection_args  # noqa: E402

DROP = {"id", "createdAt", "updatedAt", "createdBy", "updatedBy", "alertGroup", "alertGroupId"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ID_KEYS = {"channelId", "channelIds", "userId", "userIds", "scriptId", "assetId", "assetIds", "groupId"}


def scrub(value, emails: dict, remap: set, key: str = ""):
    if isinstance(value, dict):
        return {k: scrub(v, emails, remap, k) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, emails, remap, key) for v in value]
    if isinstance(value, str):
        if key in ID_KEYS:
            remap.add(key)

        def repl(m: re.Match) -> str:
            addr = m.group(0).lower()
            if addr.endswith("@example.com"):
                return m.group(0)
            emails.setdefault(addr, f"<recipient-{len(emails) + 1}@example.com>")
            return emails[addr]

        return EMAIL.sub(repl, value)
    return value


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", required=True, help="folder to write the files to")
    p.add_argument("--name", nargs="*", help="only rules whose name contains one of these")
    add_connection_args(p)
    args = p.parse_args()

    client = Client.from_args(args)
    os.makedirs(args.out, exist_ok=True)
    wanted = [n.lower() for n in (args.name or [])]
    written = 0
    for rule in client.get("/automations")["rules"]:
        if wanted and not any(w in rule["name"].lower() for w in wanted):
            continue
        emails: dict = {}
        remap: set = set()
        body = scrub({k: v for k, v in rule.items() if k not in DROP}, emails, remap)
        if remap or emails:
            body["_toolbox"] = {
                "remap": sorted(remap),
                "recipientsReplaced": len(emails),
                "note": "Placeholders and per-install ids must be set on the target install before enabling.",
            }
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", rule["name"]).strip("_")[:80] or "automation"
        path = os.path.join(args.out, f"{safe}.rule.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(body, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {path}" + (f"  ({len(emails)} recipient(s) replaced)" if emails else ""))
        written += 1
    return 0 if written else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PolarisError as e:
        sys.exit(f"Polaris refused: {e}")
