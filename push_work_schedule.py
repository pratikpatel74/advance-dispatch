#!/usr/bin/env python3
"""
push_work_schedule.py
======================
Pushes engineer shift start/end times directly to VISITOUR via the
WorkSchedule endpoint (discovered in live WSDL).

Run against TEST:
    python3 push_work_schedule.py

Run against LIVE:
    VT_ENV=LIVE python3 push_work_schedule.py

The schedule is set for Mon–Fri (Days="12345") from today for 2 years.
Shift times come from the confirmed values in backend.py (_ENG_CONFIG_SEED).
"""

import os, re, sys
from datetime import date, timedelta
import requests
from requests.auth import HTTPBasicAuth

_VT_ENV = os.environ.get("VT_ENV", "TEST")
if _VT_ENV == "LIVE":
    VT_USER = os.environ.get("VT_USER", "INT.PROD")
    VT_PASS = os.environ.get("VT_PASS", "Programs-fitted-lengths")
    VT_BASE = "https://advgroup.vt-fls.com/VTS/WS"
else:
    VT_USER = os.environ.get("VT_USER", "INT.TEST")
    VT_PASS = os.environ.get("VT_PASS", "Taking-rach-robbers")
    VT_BASE = "https://advgroup-test.vt-fls.com/VTS/WS"

# Date range: today → 2 years
START_DATE = date.today().strftime("%Y-%m-%dT00:00:00")
END_DATE   = (date.today() + timedelta(days=730)).strftime("%Y-%m-%dT00:00:00")
REF_DATE   = date.today().strftime("%Y-%m-%d")  # date part for time fields


def shift_dt(hhmm: str) -> str:
    """Convert 'HH:MM' to a full dateTime string using today's date."""
    return f"{REF_DATE}T{hhmm}:00"


# Engineer list: (name, fmExtId, shiftStart, shiftEnd)
ENGINEERS = [
    ("Tony Reid",               "487", "07:00", "15:00"),
    ("Aristotelis Goudelis",    "858", "07:00", "15:00"),
    ("Carl Mills",              "689", "08:00", "16:00"),
    ("Charles Tidey",           "802", "06:30", "14:30"),
    ("Chris Amor",              "240", "08:00", "17:00"),
    ("Franc Genovese",          "348", "06:00", "14:00"),
    ("Gareth Terrell",          "926", "06:00", "14:00"),
    ("Gary Cant",               "501", "08:00", "16:00"),
    ("Hossein Soltani-Tehrani", "776", "08:00", "16:00"),
    ("Ian Scott",               "773", "07:00", "15:00"),
    ("Jack Eagle",              "690", "07:00", "15:00"),
    ("Lee Reynolds",            "233", "05:30", "13:30"),
    ("Louis Holman",            "800", "07:30", "15:30"),
    ("Mark Holmes",             "378", "06:00", "14:00"),
    ("Mark Wilson",             "952", "09:00", "17:00"),
    ("Michael Mutirwara",       "711", "09:00", "17:00"),
    ("Mustafa Raza",            "855", "07:00", "15:00"),
    ("Nick Green",              "820", "06:30", "14:30"),
    ("Nigel Lomax",             "405", "07:00", "15:00"),
    ("Paul Holman",             "808", "06:00", "14:00"),
    ("Rhys Standing",           "982", "06:30", "14:30"),
    ("Ricky Parrett",           "239", "05:00", "13:00"),
    ("Rob Carlisle",            "799", "08:30", "16:30"),
    ("Roy Aris",                "723", "07:30", "15:30"),
    ("Scott Morgan",            "681", "08:00", "16:00"),
    ("Sean Craig",              "308", "05:30", "13:30"),
    ("Shane Sheppard",          "676", "09:00", "17:00"),
    ("Stephen Martin",          "844", "07:00", "15:00"),
    ("Terry Jones",             "884", "05:00", "13:00"),
    ("Trymore Mavhangira",      "696", "09:00", "17:00"),
    ("Umit Salah",              "731", "08:00", "16:00"),
    ("Vincent Magombe",         "761", "08:00", "16:00"),
    ("Wes Mwashaireni",         "694", "09:00", "17:00"),
    ("Ryan Mongiovi",           "857", "07:00", "15:00"),
    ("Derek Fisher",            "10009", "09:00", "17:00"),
]


def push(fm_ext_id: str, shift_start: str, shift_end: str) -> bool:
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<WorkSchedule xmlns="http://www.tourenserver.de/">
  <FMExtID>{fm_ext_id}</FMExtID>
  <StartDate>{START_DATE}</StartDate>
  <EndDate>{END_DATE}</EndDate>
  <StartTime>{shift_dt(shift_start)}</StartTime>
  <EndTime>{shift_dt(shift_end)}</EndTime>
  <Days>12345</Days>
</WorkSchedule>"""
    s = requests.Session()
    s.auth = HTTPBasicAuth(VT_USER, VT_PASS)
    r = s.post(f"{VT_BASE}/WorkSchedule",
               headers={"Content-Type": "text/xml; charset=utf-8",
                        "SOAPAction": f"{VT_BASE}/WorkSchedule"},
               data=xml.encode("utf-8"), timeout=20)
    r.raise_for_status()
    # Success code is in <WorkScheduleResult>
    m = re.search(r"<WorkScheduleResult>(-?\d+)</WorkScheduleResult>", r.text)
    if not m:
        m = re.search(r"<return>(-?\d+)</return>", r.text)
    code = int(m.group(1)) if m else None
    return code in (0, 10000), code, r.text


def main():
    env_label = "LIVE" if _VT_ENV == "LIVE" else "TEST"
    print(f"Pushing shift times → VISITOUR {env_label}\n"
          f"  Schedule valid: {START_DATE[:10]} → {END_DATE[:10]}\n"
          f"  Days: Mon–Fri (12345)\n")
    ok = err = 0
    for name, fm_id, start, end in ENGINEERS:
        try:
            success, code, body = push(fm_id, start, end)
            if success:
                print(f"  ✓ {name:<28} ({fm_id})  {start}–{end}")
                ok += 1
            else:
                print(f"  ✗ {name:<28} ({fm_id})  code={code}")
                print(f"      Response: {body[:300]}")
                err += 1
        except Exception as e:
            print(f"  ✗ {name:<28} ({fm_id})  {e}")
            err += 1

    print(f"\nDone — ✓ {ok} pushed  ✗ {err} failed")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
