# Manufacturer profiles in this toolbox

Each file is a Polaris profile file (`polaris.manufacturer-profile`, version 1): what
**Export** on a profile downloads, and what **Import…** or `scripts/apply-profile.py` reads.
No MIB text is included — a vendor's MIB is the vendor's copyright. Each file names the
modules it needs; download them from the vendor.

A `_toolbox` block says how far each profile can be trusted. Polaris ignores it on import,
and `apply-profile.py` removes it first.

| `_toolbox.status` | Means |
|---|---|
| `tested` | exported from an install where it collects, on the hardware in `testedOn` |
| `shipped-seed` | the profile Polaris itself seeds on a fresh install |
| `polaris-definition` | built from the vendor mapping Polaris ships in its source; not exported from a working install |
| `untested` | written from the MIB alone; never walked against real hardware |

## The profiles

| Manufacturer | Status | Covers | MIBs to upload (under the same manufacturer) |
|---|---|---|---|
| [Cisco](Cisco.manufacturer-profile.json) | shipped-seed | CPU (`cpmCPUTotal5secRev`, averaged), memory pools (`ciscoMemoryPoolUsed` + `Free`, summed); also applies to `cisco\|ios-?xe\|nx-?os` | none — Polaris ships CISCO-SMI, CISCO-PROCESS-MIB and CISCO-MEMORY-POOL-MIB on a fresh install (an upgraded install uploads them) |
| [Fortinet](Fortinet.manufacturer-profile.json) | polaris-definition | FortiGate CPU / memory / hardware-sensor table; FortiSwitch CPU / memory / flash / model identity; FortiAP CPU / memory / temperature — each family as a device-type default AND a model-pattern row | FORTINET-CORE-MIB, FORTINET-FORTIGATE-MIB, FORTINET-FORTISWITCH-MIB, FORTINET-FORTIAP-MIB |

## Adding one

1. Build it on a lab or production install and check every row reads **READY** and the
   device's tabs fill.
2. Export it with the provenance recorded:
   `python3 scripts/export-profiles.py --out skills/polaris-manufacturer-profiles/profiles --manufacturer <Name> --tested-on "<model>, <firmware>"`
3. Read the file before committing: it must name no hostname, address, credential or person
   (an HTTP widget's credential travels by NAME — rename it to something generic).
4. Add its row to the table above, with the modules it needs.
