#!/usr/bin/env python3
"""
Set vtMaxRadius=50mi and vtMaxDrive=100mi for every engineer with a VISITOUR
fmExtId, then push each change to VISITOUR FieldManager.

Run:
    python3 set_radius_all.py
"""

import json, urllib.request, urllib.parse, urllib.error, sys

API = "http://167.233.160.227:3004"
MAX_RADIUS = 50   # miles
MAX_DRIVE  = 100  # miles


def api_get(path):
    with urllib.request.urlopen(f"{API}{path}", timeout=15) as r:
        return json.loads(r.read())


def api_patch(path, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(
        f"{API}{path}", data=body, method="PATCH",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def main():
    print("Loading engineer config…")
    try:
        cfg = api_get("/api/engineer-config")
    except Exception as e:
        print(f"  ✗ Could not reach API: {e}")
        sys.exit(1)

    engineers = [(name, v) for name, v in cfg.items() if v.get("fmExtId")]
    print(f"  {len(engineers)} engineers with VISITOUR IDs found\n")

    ok = err = 0
    for name, v in engineers:
        current_r = v.get("vtMaxRadius", "?")
        current_d = v.get("vtMaxDrive",  "?")
        try:
            result = api_patch(
                f"/api/engineer-config/{urllib.parse.quote(name)}",
                {"vtMaxRadius": MAX_RADIUS, "vtMaxDrive": MAX_DRIVE},
            )
            vt = result.get("visitour", "")
            vt_str = " → VISITOUR ✓" if vt == "pushed" else (f" → VISITOUR ✗ ({vt})" if vt else "")
            print(f"  ✓ {name:<30} {current_r}mi/{current_d}mi → {MAX_RADIUS}mi/{MAX_DRIVE}mi{vt_str}")
            ok += 1
        except Exception as e:
            print(f"  ✗ {name:<30} {e}")
            err += 1

    print(f"\nDone — ✓ {ok} updated  ✗ {err} failed")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
