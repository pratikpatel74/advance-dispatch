"""
core_visitour.py
================
Standalone module with the core VISITOUR push/pull functions.
Import this into your own backend, or run directly for a quick test.

Usage:
    from core_visitour import push_field_manager, get_field_managers
"""

import os, re
import requests
from requests.auth import HTTPBasicAuth

VT_USER = os.environ.get("VT_USER", "INT.TEST")
VT_PASS = os.environ.get("VT_PASS", "")        # set via env var
VT_BASE = "https://advgroup-test.vt-fls.com/VTS/WS"


def vt_session():
    s = requests.Session()
    s.auth = HTTPBasicAuth(VT_USER, VT_PASS)
    return s


def mi_to_km(mi: float) -> int:
    """Convert miles to kilometres (rounded) for VISITOUR."""
    return round(float(mi) / 0.621371)


def km_to_mi(km) -> int | None:
    """Convert kilometres to miles (rounded) from VISITOUR."""
    try:
        return round(float(km) * 0.621371)
    except (ValueError, TypeError):
        return None


def push_field_manager(fm_ext_id: str, config: dict) -> bool:
    """
    Push one engineer's FieldManager settings to VISITOUR.

    config dict keys (all optional, defaults shown):
        vtCapacity   int  50   — work time units
        vtCapacity2  int   0   — second time units
        vtSpeedPct   int 100   — travel speed %
        vtWorkPct    int 100   — work time %
        vtOvertime   int   0   — max overtime (minutes/day)
        vtMinRadius  int   0   — min deployable radius (miles)
        vtMaxRadius  int  50   — max deployable radius (miles)
        vtMaxDrive   int 100   — max driving distance (miles)

    Returns True on success (VISITOUR result code 0 or 10000).
    """
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FieldManager>
  <FMExtID>{fm_ext_id}</FMExtID>
  <Capacity>{config.get('vtCapacity', 50)}</Capacity>
  <Capacity2>{config.get('vtCapacity2', 0)}</Capacity2>
  <SpeedPercent>{config.get('vtSpeedPct', 100)}</SpeedPercent>
  <WorkPercent>{config.get('vtWorkPct', 100)}</WorkPercent>
  <Overtime>{config.get('vtOvertime', 0)}</Overtime>
  <MinDeployableRadius>{mi_to_km(config.get('vtMinRadius', 0))}</MinDeployableRadius>
  <MaxDeployableRadius>{mi_to_km(config.get('vtMaxRadius', 50))}</MaxDeployableRadius>
  <MaxDrivingDistance>{mi_to_km(config.get('vtMaxDrive', 100))}</MaxDrivingDistance>
</FieldManager>"""

    try:
        r = vt_session().post(
            f"{VT_BASE}/FieldManager",
            headers={"Content-Type": "text/xml; charset=utf-8"},
            data=xml.encode("utf-8"),
            timeout=20,
        )
        r.raise_for_status()
        # Accept result code 0 or 10000 as success
        m = re.search(r"<FieldManagerResult>(\d+)</FieldManagerResult>", r.text)
        if not m:
            m = re.search(r"<return>(-?\d+)</return>", r.text)
        return bool(m and int(m.group(1)) in (0, 10000))
    except Exception as e:
        print(f"  push_field_manager error ({fm_ext_id}): {e}")
        return False


def _parse_tag(xml: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
    return m.group(1).strip() if m else ""

def _parse_all(xml: str, tag: str):
    return re.findall(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)


def get_field_managers() -> list[dict]:
    """
    Pull all FieldManager records from VISITOUR.
    Returns list of dicts with keys:
        fmExtId, firstName, lastName, capacity, capacity2,
        speedPct, workPct, overtime,
        minRadiusMi, maxRadiusMi, maxDriveMi, skills
    Radius/distance values are converted from km → miles.
    """
    xml_body = """<?xml version="1.0" encoding="utf-8"?>
<GetFieldManagers>
  <SubcontractorOnly>false</SubcontractorOnly>
</GetFieldManagers>"""

    r = vt_session().post(
        f"{VT_BASE}/GetFieldManagers",
        headers={"Content-Type": "text/xml; charset=utf-8"},
        data=xml_body.encode("utf-8"),
        timeout=30,
    )
    r.raise_for_status()

    xml_text = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', '', r.text)
    blocks = _parse_all(xml_text, "FieldManager") or _parse_all(xml_text, "Resource")

    managers = []
    for block in blocks:
        fm_id = _parse_tag(block, "FMExtID") or _parse_tag(block, "ExtID")
        if not fm_id:
            continue

        skills_str  = _parse_tag(block, "Skills") or ""
        skills_tags = _parse_all(block, "Skill")
        skills = ([s.strip() for s in skills_tags if s.strip()]
                  if skills_tags
                  else [s.strip() for s in skills_str.split(",") if s.strip()])

        managers.append({
            "fmExtId":     fm_id,
            "firstName":   _parse_tag(block, "FirstName") or _parse_tag(block, "Name"),
            "lastName":    _parse_tag(block, "LastName") or "",
            "capacity":    int(_parse_tag(block, "Capacity") or 0),
            "capacity2":   int(_parse_tag(block, "Capacity2") or 0),
            "speedPct":    int(_parse_tag(block, "SpeedPercent") or 100),
            "workPct":     int(_parse_tag(block, "WorkPercent") or 100),
            "overtime":    int(_parse_tag(block, "Overtime") or 0),
            "minRadiusMi": km_to_mi(_parse_tag(block, "MinDeployableRadius")),
            "maxRadiusMi": km_to_mi(_parse_tag(block, "MaxDeployableRadius")),
            "maxDriveMi":  km_to_mi(_parse_tag(block, "MaxDrivingDistance")),
            "skills":      skills,
        })
    return managers


if __name__ == "__main__":
    # Quick connectivity test — prints first 5 field managers returned
    print("Fetching VISITOUR FieldManagers…")
    try:
        mgrs = get_field_managers()
        print(f"  Got {len(mgrs)} records")
        for m in mgrs[:5]:
            print(f"  {m['fmExtId']:>5}  {m['firstName']} {m['lastName']}"
                  f"  cap={m['capacity']}  maxR={m['maxRadiusMi']}mi  maxD={m['maxDriveMi']}mi")
    except Exception as e:
        print(f"  Error: {e}")
