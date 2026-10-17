#!/usr/bin/env python3
"""
One-off script: push VISITOUR skills (from FLS_Scheduling Test_Template_070526.xlsx
Static Data - Resources tab) to the live engineer config API.

Run once:
    python3 patch_vt_skills.py

Reads the current config from /api/engineer-config, matches by fmExtId,
and PATCHes vtSkills for each matched engineer.
"""

import json, sys
import urllib.request, urllib.error, urllib.parse

API = "http://167.233.160.227:3004"

# ── Skills extracted from "Static Data - Resources" (Subcontractor=N only) ──
# Key: fmExtId (string)  Value: list of skill strings
VT_SKILLS_BY_FM_ID = {
    "487": ["Blast Chiller","Cold Room","Combi","Electric","Fitting Compressor","Gas",
            "Hot Trolleys","Ice Machine","Ice Machines","Induction",
            "Install Cold Room Equipment","LPG","Microwave","Refrigeration","Thermodyne",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Warewashing",
            "Water Boilers","Wiring"],
    "858": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne",
            "Warewashing","Water Boilers","Wiring"],
    "689": ["Air Con","Blast Chiller","Cold Room","Electric","Fitting Compressor",
            "Hot Trolleys","Ice Machine","Ice Machines","Pressure Testing","Refrigeration",
            "Thermodyne","Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Water Boilers"],
    "802": ["Combi","Electric","Gas","Hot Trolleys","Warewashing","Water Boilers","Wiring"],
    "348": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne",
            "Warewashing","Water Boilers"],
    "926": ["Combi","Gas","Gas Pipework","Hot Trolleys","Induction","Thermodyne",
            "Warewashing","Water Boilers","Wiring"],
    "501": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne",
            "Warewashing","Water Boilers","Wiring"],
    "776": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Ice Machines","Pressure Testing","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "773": ["Blast Chiller","Cold Room","Combi","Electric","Gas","Hot Trolleys",
            "Ice Machine","Ice Machines","Induction","LPG","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Warewashing","Water Boilers"],
    "690": ["Air Con","Blast Chiller","Cold Room","Electric","Fitting Compressor",
            "Hot Trolleys","Ice Machine","Ice Machines","Pressure Testing","Refrigeration",
            "Thermodyne","Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Water Boilers"],
    "233": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne","Warewashing"],
    "800": ["Combi","Electric","Hot Trolleys","Warewashing","Water Boilers","Wiring"],
    "378": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne",
            "Warewashing","Water Boilers","Wiring"],
    "952": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Ice Machines","Pressure Testing","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "711": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Ice Machines","Pressure Testing","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "855": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Ice Machines","Pressure Testing","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "820": ["Combi","Electric","Gas","Gas Pipework","Hot Trolleys","Induction","LPG",
            "Warewashing","Water Boilers","Wiring"],
    "405": ["Combi","Electric","Gas","Gas Pipework","Hot Trolleys","Induction","Thermodyne",
            "Warewashing","Water Boilers","Wiring"],
    "808": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Microwave",
            "Thermodyne","Warewashing","Water Boilers","Wiring"],
    "239": ["Blast Chiller","Cold Room","Combi","Electric","Fitting Compressor","Gas",
            "Hot Trolleys","Ice Machine","Ice Machines","Induction",
            "Install Cold Room Equipment","LPG","Microwave","Refrigeration","Thermodyne",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Warewashing",
            "Water Boilers","Wiring"],
    "799": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Ice Machines","Pressure Testing","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "723": ["Air Con","Blast Chiller","Cold Room","Electric","Fitting Compressor",
            "Hot Trolleys","Ice Machines","Pressure Testing","Refrigeration","Thermodyne",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Water Boilers"],
    "308": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne",
            "Warewashing","Water Boilers","Wiring"],
    "676": ["Combi","Electric","Hot Trolleys","Induction","Microwave","Thermodyne",
            "Warewashing","Water Boilers","Wiring"],
    "844": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne",
            "Warewashing","Water Boilers"],
    "884": ["Combi","Gas","Gas Pipework","Hot Trolleys","Induction","Thermodyne",
            "Warewashing","Water Boilers","Wiring"],
    "696": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Ice Machines","Pressure Testing","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "731": ["Cold Room","Ice Machines","Refrigeration"],
    "761": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Ice Machines","Pressure Testing","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "694": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Ice Machines","Pressure Testing","Refrigeration",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "10009": ["Warewashing"],
    # Callum Milnes & Ryan Mongiovi have no fmExtId yet — patched by name below
}

# Engineers with no fmExtId in live config — match by name
VT_SKILLS_BY_NAME = {
    "Callum Milnes":  ["Combi","Electric","Hot Trolleys","Induction","Microwave","Thermodyne",
                       "Warewashing","Water Boilers","Wiring"],
    "Ryan Mongiovi":  ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
                       "Ice Machines","Pressure Testing","Refrigeration",
                       "Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    # Mark Holmes & Roy Aris have fmExtId in VISITOUR but config shows null — patch by name
    "Mark Holmes":    ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne",
                       "Warewashing","Water Boilers","Wiring"],
    "Roy Aris":       ["Air Con","Blast Chiller","Cold Room","Electric","Fitting Compressor",
                       "Hot Trolleys","Ice Machines","Pressure Testing","Refrigeration",
                       "Thermodyne","Undercounter Fridge/Freezer","Walk In Chiller/Freezer",
                       "Water Boilers"],
}


def api_get(path):
    req = urllib.request.Request(f"{API}{path}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def api_patch(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{API}{path}", data=body, method="PATCH",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def main():
    print("Loading current engineer config from API…")
    try:
        cfg = api_get("/api/engineer-config")
    except Exception as e:
        print(f"  ✗ Could not reach API: {e}")
        sys.exit(1)

    # Build fmExtId → name lookup
    fm_to_name = {v.get("fmExtId"): k for k, v in cfg.items() if v.get("fmExtId")}

    ok = err = skipped = 0

    # Patch by fmExtId
    for fm_id, skills in VT_SKILLS_BY_FM_ID.items():
        name = fm_to_name.get(fm_id)
        if not name:
            print(f"  ? fmExtId {fm_id} not found in config (skipped)")
            skipped += 1
            continue
        try:
            api_patch(f"/api/engineer-config/{urllib.parse.quote(name)}", {"vtSkills": skills})
            print(f"  ✓ {name} ({len(skills)} skills)")
            ok += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            err += 1

    # Patch by name
    for name, skills in VT_SKILLS_BY_NAME.items():
        if name not in cfg:
            print(f"  ? '{name}' not in config (skipped)")
            skipped += 1
            continue
        try:
            api_patch(f"/api/engineer-config/{urllib.parse.quote(name)}", {"vtSkills": skills})
            print(f"  ✓ {name} ({len(skills)} skills, by name)")
            ok += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            err += 1

    print(f"\nDone — ✓ {ok}  ✗ {err}  skipped {skipped}")


if __name__ == "__main__":
    main()
