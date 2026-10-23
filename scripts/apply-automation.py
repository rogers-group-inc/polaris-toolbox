#!/usr/bin/env python3
"""Create (or replace) Polaris automations from rule files.

  python3 apply-automation.py RULE.json [RULE2.json ...] [--dry-run] [--update]

A rule file is one automation body as POST /api/v1/automations accepts it, or a JSON list of
them (what export-automations.py writes, and the recipes in
../skills/polaris-automations/references/recipes.md). For each rule the script:

  1. dry-runs it with POST /automations/preview — how many devices it covers and how many
     readings meet it right now (event and change triggers have no current reading);
  2. unless --dry-run, creates it; a rule whose NAME already exists is skipped, or replaced
     with --update (PUT is a full replace of the stored rule);
  3. prints the new rule's id.

A rule carrying a `script` action needs automationScripts:write on the token's role, a `reboot`
action needs assets:write. A rule on `monitorStatus == down` defines down detection for its
devices. Create rules disabled ("enabled": false) when in doubt, and have a human review a
rule before enabling it in production.

Token role needs: automationManagement write (read is enough for --dry-run).
Exit status: 0 = every rule applied (or previewed), 2 = something failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from polaris_client import Client, PolarisError, add_connection_args  # noqa: E402

AUTOMATIONS = "/automations"


def load_rules(paths: list) -> list:
    rules = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for rule in data if isinstance(data, list) else [data]:
            rule = dict(rule)
            rule.pop("_toolbox", None)  # toolbox metadata, not part of the rule body
            rules.append((path, rule))
    return rules


def describe_preview(pv: dict) -> str:
    if not pv.get("supported", True):
        return pv.get("note") or "no current reading to preview (event / change trigger)"
    parts = [f"{pv.get('totalAssets', pv.get('totalEvaluated', 0))} device(s) covered"]
    if pv.get("coveredAssets") is not None:
        parts.append(f"{pv['coveredAssets']} after more specific rules take theirs")
    if pv.get("unmonitoredCount"):
        parts.append(f"{pv['unmonitoredCount']} selected but not monitored (never alert)")
    parts.append(f"{pv.get('meetsCount', 0)} reading(s) meet it now")
    return ", ".join(parts)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("rules", nargs="+", help="rule file(s): one rule or a list")
    p.add_argument("--dry-run", action="store_true", help="preview only: create nothing")
    p.add_argument("--update", action="store_true", help="replace a rule that already has the same name")
    add_connection_args(p)
    args = p.parse_args()

    client = Client.from_args(args)
    existing = {r["name"].lower(): r["id"] for r in client.get(AUTOMATIONS)["rules"]}
    ok = True
    for path, rule in load_rules(args.rules):
        name = rule.get("name", "(unnamed)")
        print(f"\n{name}  ({path})")
        try:
            pv = client.post(f"{AUTOMATIONS}/preview", {k: rule[k] for k in ("name", "trigger", "scope") if k in rule})
            print("  preview: " + describe_preview(pv))
        except PolarisError as e:
            print(f"  preview refused: {e.message}")
            ok = False
            continue
        if args.dry_run:
            continue
        rid = existing.get(name.lower())
        try:
            if rid and not args.update:
                print("  skipped: a rule with this name exists (pass --update to replace it)")
                continue
            if rid:
                saved = client.put(f"{AUTOMATIONS}/{rid}", rule)["rule"]
                print(f"  replaced {saved['id']}" + ("" if saved.get("enabled") else " (disabled)"))
            else:
                saved = client.post(AUTOMATIONS, rule)["rule"]
                print(f"  created {saved['id']}" + ("" if saved.get("enabled") else " (disabled)"))
        except PolarisError as e:
            print(f"  refused: {e.message}")
            ok = False
    print("\nHave a human review each rule before enabling it in production.")
    return 0 if ok else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PolarisError as e:
        sys.exit(f"Polaris refused: {e}")
