#!/usr/bin/env python3
"""Export manufacturer profiles from a Polaris install as profile files.

  python3 export-profiles.py --out DIR [--manufacturer NAME ...] [--tested-on "model, firmware"]

Writes one <Manufacturer>.manufacturer-profile.json per profile, in Polaris's own export
format: MIBs by module name, credentials by name, no ids, no secrets, no per-device widget
switches, no MIB text. The file imports into any install (Import… on the Manufacturer
Profiles card, or apply-profile.py).

--tested-on adds a "_toolbox" block (status "tested", what it was tested on, today's date)
that the toolbox's profiles/ library uses; apply-profile.py strips it before importing.

MIB files are NOT downloaded. A vendor's MIB is the vendor's copyright: fetch it from the
vendor, and never commit one to a public repository.

Token role needs: manufacturerProfiles read.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from polaris_client import Client, PolarisError, add_connection_args  # noqa: E402

PROFILES = "/server-settings/manufacturer-profiles"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", required=True, help="folder to write the files to")
    p.add_argument("--manufacturer", nargs="*", help="only these manufacturers (default: every profile)")
    p.add_argument("--tested-on", help='what the profile was tested on, e.g. "FortiGate 60F, FortiOS 7.4.8"')
    add_connection_args(p)
    args = p.parse_args()

    client = Client.from_args(args)
    os.makedirs(args.out, exist_ok=True)
    wanted = {m.lower() for m in (args.manufacturer or [])}
    profiles = client.get(PROFILES)["profiles"]
    written = 0
    for s in profiles:
        if wanted and s["manufacturer"].lower() not in wanted:
            continue
        file = client.get(f"{PROFILES}/{s['id']}/export")
        file.pop("exportedAt", None)  # keeps re-exports diff-clean
        if args.tested_on:
            file["_toolbox"] = {
                "status": "tested",
                "testedOn": args.tested_on,
                "date": datetime.date.today().isoformat(),
            }
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", file["manufacturer"])
        path = os.path.join(args.out, f"{safe}.manufacturer-profile.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(file, f, indent=2, ensure_ascii=False)
            f.write("\n")
        ready = "ready" if s["ready"] else f"{s['unresolvedCount']} unresolved"
        print(f"wrote {path}  ({s['metricCount']} rows, {s['overrideCount']} overrides, {s['widgetCount']} widgets; {ready})")
        written += 1
    if wanted and written < len(wanted):
        print("Some manufacturers had no profile: " + ", ".join(sorted(wanted - {s['manufacturer'].lower() for s in profiles})))
    return 0 if written else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PolarisError as e:
        sys.exit(f"Polaris refused: {e}")
