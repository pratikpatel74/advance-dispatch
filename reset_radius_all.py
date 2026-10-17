#!/usr/bin/env python3
"""
reset_radius_all.py
=====================
Resets ALL engineers to Max Radius=62mi and Max Drive=150mi directly in VISITOUR.

Run:
    python3 reset_radius_all.py
"""

import os, re, sys
import requests
from requests.auth import HTTPBasicAuth

VT_USER = os.environ.get("VT_USER", "INT.TEST")
VT_PASS = os.environ.get("VT_PASS", "Taking-rach-robbers")
VT_BASE = "https://advgroup-test.vt-fls.com/VTS/WS"

MAX_RADIUS = 62   # miles
MAX_DRIVE  = 150  # miles

# Excluded — these have custom radius/drive settings already pushed:
#   Mark Holmes  (378) 72mi / 200mi
#   Carl Mills   (689) 80mi / 200mi
#   Ian Scott    (773) 83mi / 200mi
#   Roy Aris     (723) 50mi / 150mi
ENGINEERS = [
    ("Aristotelis Goudelis",    "858"),
    ("Charles Tidey",           "802"),
    ("Chris Amor",              "240"),
    ("Franc Genovese",          "348"),
    ("Gareth Terrell",          "926"),
    ("Gary Cant",               "501"),
    ("Hossein Soltani-Tehrani", "776"),
    ("Jack Eagle",              "690"),
    ("Lee Reynolds",            "233"),
    ("Louis Holman",            "800"),
    ("Mark Wilson",             "952"),
    ("Michael Mutirwara",       "711"),
    ("Mustafa Raza",            "855"),
    ("Nick Green",              "820"),
    ("Nigel Lomax",             "405"),
    ("Paul Holman",             "808"),
    ("Rhys Standing",           "982"),
    ("Ricky Parrett",           "239"),
    ("Rob Carlisle",            "799"),
    ("Ryan Mongiovi",           "857"),
    ("Scott Morgan",            "681"),
    ("Sean Craig",              "308"),
    ("Shane Sheppard",          "676"),
    ("Stephen Martin",          "844"),
    ("Terry Jones",             "884"),
    ("Tony Reid",               "487"),
    ("Trymore Mavhangira",      "696"),
    ("Umit Salah",              "731"),
    ("Vincent Magombe",         "761"),
    ("Wes Mwashaireni",         "694"),
    ("Derek Fisher",            "10009"),
]

DEFAULTS = {"vtCapacity": 50, "vtCapacity2": 0, "vtSpeedPct": 100,
            "vtWorkPct": 100, "vtOvertime": 0, "vtMinRadius": 0}


def mi_to_km(mi):
    return round(float(mi) / 0.621371)


def push(fm_ext_id: str) -> bool:
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FieldManager>
  <FMExtID>{fm_ext_id}</FMExtID>
  <Capacity>{DEFAULTS['vtCapacity']}</Capacity>
  <Capacity2>{DEFAULTS['vtCapacity2']}</Capacity2>
  <SpeedPercent>{DEFAULTS['vtSpeedPct']}</SpeedPercent>
  <WorkPercent>{DEFAULTS['vtWorkPct']}</WorkPercent>
  <Overtime>{DEFAULTS['vtOvertime']}</Overtime>
  <MinDeployableRadius>{mi_to_km(DEFAULTS['vtMinRadius'])}</MinDeployableRadius>
  <MaxDeployableRadius>{mi_to_km(MAX_RADIUS)}</MaxDeployableRadius>
  <MaxDrivingDistance>{mi_to_km(MAX_DRIVE)}</MaxDrivingDistance>
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
    print(f"Resetting all engineers to MaxRadius={MAX_RADIUS}mi / MaxDrive={MAX_DRIVE}mi...\n")
    ok = err = 0
    for name, fm_id in ENGINEERS:
        try:
            if push(fm_id):
                print(f"  ✓ {name:<28} ({fm_id})")
                ok += 1
            else:
                print(f"  ✗ {name:<28} ({fm_id})  VISITOUR returned error")
                err += 1
        except Exception as e:
            print(f"  ✗ {name:<28} ({fm_id})  {e}")
            err += 1

    print(f"\nDone — ✓ {ok} reset  ✗ {err} failed")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
