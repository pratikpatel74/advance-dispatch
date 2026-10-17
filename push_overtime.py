#!/usr/bin/env python3
"""
push_overtime.py
=================
Sets Permit Overtime = 60 minutes for all 35 engineers directly in VISITOUR LIVE.
Preserves each engineer's existing radius/drive settings.

Run:
    python3 push_overtime.py
"""

import os, re, sys
import requests
from requests.auth import HTTPBasicAuth

_VT_ENV = os.environ.get("VT_ENV", "LIVE")
if _VT_ENV == "LIVE":
    VT_USER = os.environ.get("VT_USER", "INT.PROD")
    VT_PASS = os.environ.get("VT_PASS", "Programs-fitted-lengths")
    VT_BASE = "https://advgroup.vt-fls.com/VTS/WS"
else:
    VT_USER = os.environ.get("VT_USER", "INT.TEST")
    VT_PASS = os.environ.get("VT_PASS", "Taking-rach-robbers")
    VT_BASE = "https://advgroup-test.vt-fls.com/VTS/WS"

OVERTIME = 60  # minutes


def mi_to_km(mi):
    return round(float(mi) / 0.621371)


# (name, fmExtId, maxRadius_mi, maxDrive_mi)
ENGINEERS = [
    ("Tony Reid",               "487",   62, 150),
    ("Aristotelis Goudelis",    "858",   62, 150),
    ("Carl Mills",              "689",   80, 200),
    ("Charles Tidey",           "802",   62, 150),
    ("Chris Amor",              "240",  100, 200),
    ("Franc Genovese",          "348",   62, 150),
    ("Gareth Terrell",          "926",   62, 150),
    ("Gary Cant",               "501",   62, 150),
    ("Hossein Soltani-Tehrani", "776",   62, 150),
    ("Ian Scott",               "773",   83, 200),
    ("Jack Eagle",              "690",   62, 150),
    ("Lee Reynolds",            "233",   62, 150),
    ("Louis Holman",            "800",   62, 150),
    ("Mark Holmes",             "378",   72, 200),
    ("Mark Wilson",             "952",   62, 150),
    ("Michael Mutirwara",       "711",   62, 150),
    ("Mustafa Raza",            "855",   62, 150),
    ("Nick Green",              "820",   62, 150),
    ("Nigel Lomax",             "405",   62, 150),
    ("Paul Holman",             "808",   62, 150),
    ("Rhys Standing",           "982",   62, 150),
    ("Ricky Parrett",           "239",   62, 150),
    ("Rob Carlisle",            "799",   62, 150),
    ("Roy Aris",                "723",   50, 150),
    ("Scott Morgan",            "681",   62, 150),
    ("Sean Craig",              "308",   62, 150),
    ("Shane Sheppard",          "676",   62, 150),
    ("Stephen Martin",          "844",   62, 150),
    ("Terry Jones",             "884",   62, 150),
    ("Trymore Mavhangira",      "696",   62, 150),
    ("Umit Salah",              "731",   62, 150),
    ("Vincent Magombe",         "761",   62, 150),
    ("Wes Mwashaireni",         "694",   62, 150),
    ("Ryan Mongiovi",           "857",   62, 150),
    ("Derek Fisher",            "10009", 62, 150),
]


def push(fm_ext_id, max_radius_mi, max_drive_mi):
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FieldManager>
  <FMExtID>{fm_ext_id}</FMExtID>
  <Capacity>50</Capacity>
  <Capacity2>0</Capacity2>
  <SpeedPercent>100</SpeedPercent>
  <WorkPercent>100</WorkPercent>
  <Overtime>{OVERTIME}</Overtime>
  <MinDeployableRadius>0</MinDeployableRadius>
  <MaxDeployableRadius>{mi_to_km(max_radius_mi)}</MaxDeployableRadius>
  <MaxDrivingDistance>{mi_to_km(max_drive_mi)}</MaxDrivingDistance>
</FieldManager>"""
    s = requests.Session()
    s.auth = HTTPBasicAuth(VT_USER, VT_PASS)
    r = s.post(f"{VT_BASE}/FieldManager",
               headers={"Content-Type": "text/xml; charset=utf-8"},
               data=xml.encode("utf-8"), timeout=20)
    r.raise_for_status()
    m = re.search(r"<FieldManagerResult>(-?\d+)</FieldManagerResult>", r.text)
    code = int(m.group(1)) if m else None
    return code in (0, 10000), code


def main():
    env_label = "LIVE" if _VT_ENV == "LIVE" else "TEST"
    print(f"Pushing {OVERTIME} min overtime → VISITOUR {env_label} ({len(ENGINEERS)} engineers)\n")
    ok = err = 0
    for name, fm_id, radius, drive in ENGINEERS:
        try:
            success, code = push(fm_id, radius, drive)
            if success:
                print(f"  ✓ {name:<28} ({fm_id})")
                ok += 1
            else:
                print(f"  ✗ {name:<28} ({fm_id})  code={code}")
                err += 1
        except Exception as e:
            print(f"  ✗ {name:<28} ({fm_id})  {e}")
            err += 1

    print(f"\nDone — ✓ {ok} updated  ✗ {err} failed")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
