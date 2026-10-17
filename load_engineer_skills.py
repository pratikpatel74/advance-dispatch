#!/usr/bin/env python3
"""
Engineer-Skills.xlsx → Supabase
================================
Loads Advantage engineer skills (Advantage taxonomy) into adv_engineer_skills,
replacing Fleet Manager taxonomy data.

Also corrects engineer name spellings in adv_engineers where the spreadsheet
differs from what was previously loaded.

Usage:
    python3 load_engineer_skills.py --xlsx /path/to/Engineer-Skills.xlsx
    python3 load_engineer_skills.py  # uses Engineer-Skills.xlsx in current dir
"""

import sys
import os
import argparse
import requests
import openpyxl

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://ehuhqzjnikvykldasygc.supabase.co"
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVodWhxempuaWt2eWtsZGFzeWdjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc5OTc3NzEsImV4cCI6MjEwMzU3Mzc3MX0.Kv7ko_u34u6ZTTU2QU50UULpG0bOX6jyOsA8-ry9ltU"
)
HDR = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=minimal",
}

# ── Name corrections: spreadsheet name → canonical adv_name in Supabase ──────
# The spreadsheet is authoritative; fix Supabase to match.
NAME_CORRECTIONS = {
    "Tony Reid":           "Anthony Reid",       # Supabase has Anthony
    "Aritotelis Gouldelis": "Aritotelis Goudelis",  # Supabase has single-l
}
# Reverse map: spreadsheet name → correct adv_name to use as the key
# We'll update adv_engineers so adv_name matches the spreadsheet's name.
# Actually: spreadsheet is Advantage-authoritative, so update Supabase TO match spreadsheet.
# i.e. rename "Anthony Reid" → "Tony Reid" and fix the Goudelis spelling.
ADV_NAME_UPDATES = {
    # supabase_current_name: spreadsheet_name (what it should be)
    "Anthony Reid":        "Tony Reid",
    "Aritotelis Goudelis": "Aritotelis Gouldelis",
}

# ── Skill column mapping (col index 0-based in spreadsheet row, skill name) ───
# Row structure: (eng_id, name, schedulable, gas, lpg, refrig, accessories,
#                 air_con, combi, gantry, holding_unit, insect_killer, prep,
#                 prime_cooking, warewashing, waste_disposal, water_boilers)
SKILL_COLS = {
    3:  "Gas",
    4:  "LPG",
    5:  "Refrigeration",
    6:  "Accessories",
    7:  "Air Con",
    8:  "Combi",
    9:  "Gantry",
    10: "Holding Unit",
    11: "Insect Killer",
    12: "Prep",
    13: "Prime Cooking",
    14: "Warewashing",
    15: "Waste Disposal",
    16: "Water Boilers",
}


def sb_get(path, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{path}{params}", headers=HDR)
    r.raise_for_status()
    return r.json()


def sb_patch(path, data):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=HDR, json=data)
    if not r.ok:
        print(f"  ⚠  PATCH error: {r.status_code} {r.text[:200]}")
    return r.ok


def sb_upsert(table, rows, on_conflict):
    if not rows:
        return 0
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}",
        headers=HDR,
        json=rows,
    )
    if not r.ok:
        print(f"  ⚠  Upsert error ({table}): {r.status_code} {r.text[:200]}")
    return len(rows)


def sb_delete_all(table):
    """Delete all rows from table (used to clear old skill data before reload)."""
    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}?id=neq.00000000-0000-0000-0000-000000000000",
        headers=HDR,
    )
    if not r.ok:
        print(f"  ⚠  Delete error ({table}): {r.status_code} {r.text[:200]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", default="Engineer-Skills.xlsx",
                        help="Path to Engineer-Skills.xlsx")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without writing to Supabase")
    args = parser.parse_args()

    if not os.path.exists(args.xlsx):
        print(f"❌  File not found: {args.xlsx}")
        sys.exit(1)

    print("=" * 60)
    print("Engineer-Skills.xlsx → Supabase")
    print(f"File: {args.xlsx}")
    if args.dry_run:
        print("DRY RUN — no changes will be written")
    print("=" * 60)

    # ── 1. Load spreadsheet ───────────────────────────────────────────────────
    wb = openpyxl.load_workbook(args.xlsx)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    # Skip header rows (first two)
    data_rows = [r for r in rows[2:] if isinstance(r[0], int)]
    print(f"\n[1/4] Spreadsheet: {len(data_rows)} engineers found")

    # ── 2. Load current adv_engineers from Supabase ───────────────────────────
    print("\n[2/4] Loading current adv_engineers from Supabase…")
    eng_rows = sb_get("adv_engineers", "?select=id,adv_name&limit=100")
    id_to_name = {r["id"]: r["adv_name"] for r in eng_rows}
    name_to_id = {r["adv_name"]: r["id"] for r in eng_rows}
    print(f"      {len(eng_rows)} engineers in Supabase")

    # ── 3. Apply name corrections in adv_engineers ────────────────────────────
    print("\n[3/4] Applying name corrections in adv_engineers…")
    for old_name, new_name in ADV_NAME_UPDATES.items():
        if old_name in name_to_id:
            eng_id = name_to_id[old_name]
            print(f"  → Rename '{old_name}' → '{new_name}' (id={eng_id})")
            if not args.dry_run:
                ok = sb_patch(
                    f"adv_engineers?id=eq.{eng_id}",
                    {"adv_name": new_name}
                )
                if ok:
                    # Update local maps
                    id_to_name[eng_id] = new_name
                    name_to_id[new_name] = eng_id
                    del name_to_id[old_name]
        else:
            print(f"  ✓ '{old_name}' not found in Supabase (already correct or missing)")

    # ── 4. Build and load adv_engineer_skills ─────────────────────────────────
    print("\n[4/4] Building new adv_engineer_skills rows…")

    skill_rows = []
    skipped = []

    for row in data_rows:
        eng_id   = row[0]
        xls_name = row[1]

        # Resolve to canonical name (post-correction)
        resolved_name = ADV_NAME_UPDATES.get(xls_name, xls_name)

        # Verify engineer exists in Supabase
        if eng_id not in id_to_name and resolved_name not in name_to_id:
            skipped.append(f"{xls_name} (id={eng_id})")
            continue

        # Use resolved name (after any rename applied above)
        eng_name = id_to_name.get(eng_id, resolved_name)
        # Post-rename: if we just renamed it, use the new name
        if eng_name in ADV_NAME_UPDATES:
            eng_name = ADV_NAME_UPDATES[eng_name]

        for col_idx, skill_name in SKILL_COLS.items():
            has_skill = bool(row[col_idx]) if col_idx < len(row) else False
            skill_rows.append({
                "engineer_name": eng_name,
                "category":      "Equipment",
                "skill_name":    skill_name,
                "has_skill":     has_skill,
                "notes":         "Loaded from Advantage Engineer-Skills export",
            })

    total_skills = len([r for r in skill_rows if r["has_skill"]])
    print(f"      {len(skill_rows)} skill rows built ({total_skills} active skills)")
    if skipped:
        print(f"  ⚠  Skipped (not in Supabase): {', '.join(skipped)}")

    if not args.dry_run:
        print("\n  Clearing existing adv_engineer_skills…")
        sb_delete_all("adv_engineer_skills")

        print(f"  Upserting {len(skill_rows)} rows…")
        batch_size = 200
        for i in range(0, len(skill_rows), batch_size):
            sb_upsert(
                "adv_engineer_skills",
                skill_rows[i:i+batch_size],
                "engineer_name,skill_name"
            )
        print("  ✓ Done")
    else:
        print("\n  [DRY RUN] Would clear adv_engineer_skills and insert:")
        for r in skill_rows[:10]:
            print(f"    {r['engineer_name']:30s} {r['skill_name']:20s} {'✓' if r['has_skill'] else '✗'}")
        print(f"    … and {len(skill_rows)-10} more rows")

    print(f"\n{'='*60}")
    print("✅  Complete!")
    print(f"   {len(data_rows)} engineers processed")
    print(f"   {len(ADV_NAME_UPDATES)} name corrections applied")
    print(f"   {total_skills} active skill assignments loaded")
    if skipped:
        print(f"   ⚠  {len(skipped)} engineers skipped (not in adv_engineers)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
