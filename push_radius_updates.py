#!/usr/bin/env python3
"""
push_radius_updates.py
========================
Pushes approved radius/drive changes directly to VISITOUR (bypasses
the backend API's change-detection so already-saved values still push).

Run:
    python3 push_radius_updates.py

Changes:
    Mark Holmes   (378) — Max Radius: 72mi, Max Drive: 200mi
    Tyler Speight (461) — Max Radius: 72mi, Max Drive: 200mi
    Carl Mills    (689) — Max Radius: 80mi, Max Drive: 200mi
    Ian Scott     (773) — Max Radius: 83mi, Max Drive: 200mi
    Roy Aris      (723) — Max Radius: 50mi, Max Drive: 150mi
"""

import os, re, sys
import requests
from requests.auth import HTTPBasicAuth

VT_USER = os.environ.get("VT_USER", "INT.TEST")
VT_PASS = os.environ.get("VT_PASS", "Taking-rach-robbers")
VT_BASE = "https://advgroup-test.vt-fls.com/VTS/WS"

UPDATES = [
    ("Mark Holmes",   "378", {"vtMaxRadius": 72,  "vtMaxDrive": 200}),
    ("Carl Mills",    "689", {"vtMaxRadius": 80,  "vtMaxDrive": 200}),
    ("Ian Scott",     "773", {"vtMaxRadius": 83,  "vtMaxDrive": 200}),
    ("Roy Aris",      "723", {"vtMaxRadius": 50,  "vtMaxDrive": 150}),
]

# Defaults for fields not being changed
DEFAULTS = {"vtCapacity": 50, "vtCapacity2": 0, "vtSpeedPct": 100,
            "vtWorkPct": 100, "vtOvertime": 0, "vtMinRadius": 0}


def mi_to_km(mi):
    return round(float(mi) / 0.621371)


def push(fm_ext_id: str, cfg: dict) -> bool:
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FieldManager>
  <FMExtID>{fm_ext_id}</FMExtID>
  <Capacity>{cfg.get('vtCapacity', 50)}</Capacity>
  <Capacity2>{cfg.get('vtCapacity2', 0)}</Capacity2>
  <SpeedPercent>{cfg.get('vtSpeedPct', 100)}</SpeedPercent>
  <WorkPercent>{cfg.get('vtWorkPct', 100)}</WorkPercent>
  <Overtime>{cfg.get('vtOvertime', 0)}</Overtime>
  <MinDeployableRadius>{mi_to_km(cfg.get('vtMinRadius', 0))}</MinDeployableRadius>
  <MaxDeployableRadius>{mi_to_km(cfg.get('vtMaxRadius', 50))}</MaxDeployableRadius>
  <MaxDrivingDistance>{mi_to_km(cfg.get('vtMaxDrive', 100))}</MaxDrivingDistance>
</FieldManager>"""
    s = requests.Session()
    s.auth = HTTPBasicAuth(VT_USER, VT_PASS)
    r = s.post(f"{VT_BASE}/FieldManager",
               headers={"Content-Type": "text/xml; charset=utf-8"},
               data=xml.encode("utf-8"), timeout=20)
    r.raise_for_status()
    m = re.search(r"<FieldManagerResult>(\d+)</FieldManagerResult>", r.text)
    if not m:
        m = re.search(r"<return>(-?\d+)</return>", r.text)
    return bool(m and int(m.group(1)) in (0, 10000))


def main():
    print("Pushing radius/drive updates directly to VISITOUR...\n")
    ok = err = 0
    for name, fm_id, changes in UPDATES:
        cfg = {**DEFAULTS, **changes}
        try:
            success = push(fm_id, cfg)
            r = changes.get("vtMaxRadius", "?")
            d = changes.get("vtMaxDrive", "?")
            if success:
                print(f"  ✓ {name:<22} ({fm_id})  MaxRadius={r}mi  MaxDrive={d}mi  → VISITOUR ✓")
                ok += 1
            else:
                print(f"  ✗ {name:<22} ({fm_id})  → VISITOUR returned error")
                err += 1
        except Exception as e:
            print(f"  ✗ {name:<22} ({fm_id})  {e}")
            err += 1

    print(f"\nDone — ✓ {ok} pushed  ✗ {err} failed")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
