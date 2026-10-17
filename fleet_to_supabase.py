#!/usr/bin/env python3
"""
Fleet Manager → Supabase Sync
==============================
Reads engineer skills, certifications, absences and department info
from the Fleet Manager SQLite database and pushes it to Supabase.

Run:
    python3 fleet_to_supabase.py

Schedule (optional, after BrightHR sync):
    */5 * * * * python3 /path/to/fleet_to_supabase.py >> /var/log/fleet_supabase_sync.log 2>&1

Requirements:
    pip3 install supabase
"""

import sqlite3
import sys
import os
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
FLEET_DB = os.path.expanduser(
    "~/Documents/Projects/Advance-Apps/fleet-app/backend/prisma/prisma/fleet.db"
)
SUPABASE_URL = "https://ehuhqzjnikvykldasygc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVodWhxempuaWt2eWtsZGFzeWdjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc5OTc3NzEsImV4cCI6MjEwMzU3Mzc3MX0.Kv7ko_u34u6ZTTU2QU50UULpG0bOX6jyOsA8-ry9ltU"

BATCH_SIZE = 200

# ── VISITOUR skills (from scheduling spreadsheet) ─────────────────────────────
# Key: fmExtId  Value: list of VISITOUR skill strings
VT_SKILLS_BY_FM_ID = {
    "487": ["Blast Chiller","Cold Room","Combi","Electric","Gas","Hot Trolleys","Ice Machine",
            "Induction","LPG","Microwave","Refrigeration","Thermodyne",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Warewashing","Water Boilers","Wiring"],
    "858": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "689": ["Air Con","Blast Chiller","Cold Room","Electric","Fitting Compressor","Hot Trolleys",
            "Ice Machine","Pressure Testing","Refrigeration","Thermodyne",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Water Boilers"],
    "802": ["Combi","Electric","Gas","Hot Trolleys","Warewashing","Water Boilers","Wiring"],
    "348": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne","Warewashing","Water Boilers"],
    "926": ["Combi","Gas","Gas Pipework","Hot Trolleys","Induction","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "501": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "776": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "773": ["Blast Chiller","Cold Room","Combi","Electric","Gas","Hot Trolleys","Ice Machine",
            "Induction","LPG","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Warewashing","Water Boilers"],
    "690": ["Air Con","Blast Chiller","Cold Room","Electric","Fitting Compressor","Hot Trolleys",
            "Ice Machine","Pressure Testing","Refrigeration","Thermodyne",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Water Boilers"],
    "233": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne","Warewashing"],
    "800": ["Combi","Electric","Hot Trolleys","Warewashing","Water Boilers","Wiring"],
    "952": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "711": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "855": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "820": ["Combi","Electric","Gas","Gas Pipework","Hot Trolleys","Induction","LPG","Warewashing","Water Boilers","Wiring"],
    "405": ["Combi","Electric","Gas","Gas Pipework","Hot Trolleys","Induction","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "808": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Microwave","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "239": ["Blast Chiller","Cold Room","Combi","Electric","Fitting Compressor","Gas","Hot Trolleys",
            "Ice Machine","Induction","LPG","Microwave","Refrigeration","Thermodyne",
            "Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Warewashing","Water Boilers","Wiring"],
    "799": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "308": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "676": ["Combi","Electric","Hot Trolleys","Induction","Microwave","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "844": ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne","Warewashing","Water Boilers"],
    "884": ["Combi","Gas","Gas Pipework","Hot Trolleys","Induction","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "696": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "731": ["Cold Room","Ice Machine","Refrigeration"],
    "761": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "694": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
            "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
}
# Engineers not in VISITOUR config by fmExtId — patched by name
VT_SKILLS_BY_NAME = {
    "Ryan Mongiovi": ["Air Con","Blast Chiller","Cold Room","Fitting Compressor","Ice Machine",
                      "Pressure Testing","Refrigeration","Undercounter Fridge/Freezer","Walk In Chiller/Freezer"],
    "Mark Holmes":   ["Combi","Electric","Gas","Hot Trolleys","Induction","LPG","Thermodyne","Warewashing","Water Boilers","Wiring"],
    "Roy Aris":      ["Air Con","Blast Chiller","Cold Room","Electric","Fitting Compressor","Hot Trolleys",
                      "Pressure Testing","Refrigeration","Thermodyne","Undercounter Fridge/Freezer","Walk In Chiller/Freezer","Water Boilers"],
    "Derek Fisher":  ["Combi","Electric","Gas","Hot Trolleys","Induction","Thermodyne","Warewashing","Water Boilers","Wiring"],
}

# ── Name normalisation: Fleet Manager name → adv_engineers canonical name ─────
# adv_engineers was seeded from index.html ALL_ENGS list; Fleet Manager spellings differ.
NAME_MAP = {
    "Tony Reid":            "Anthony Reid",
    "Aristotelis Goudelis": "Aritotelis Goudelis",   # keep the ALL_ENGS typo
    "Mike Mutirwara":       "Michael Mutirwara",
    "Mustafa Raza (Nigel)": "Mustafa Raza",
    "Ricky Parret":         "Ricky Parrett",
    "Stephan Martin":       "Stephen Martin",
    "Scott Morgan":         "Scott Morgan",           # same, listed for completeness
}

# ── Department derived from VISITOUR skill sets ───────────────────────────────
# Engineers whose VT skills are purely cooling/refrigeration
COOLING_FM_IDS = {"689","776","690","952","711","855","799","696","731","761","694"}
# Names with no fmExtId but known to be Cooling
COOLING_NAMES  = {"Ryan Mongiovi", "Roy Aris"}
# Everyone else with a VT skill entry is Catering

def dept_from_vt(vt_id, canonical_name):
    if vt_id in COOLING_FM_IDS or canonical_name in COOLING_NAMES:
        return "Cooling"
    if vt_id or canonical_name in VT_SKILLS_BY_NAME:
        return "Catering"
    return ""

# ── VISITOUR FMExtID mapping ──────────────────────────────────────────────────
VISITOUR_IDS = {
    "tony reid":"487","aristotelis goudelis":"858","carl mills":"689",
    "charles tidey":"802","chris amor":"240","franc genovese":"348",
    "gareth terrell":"926","gary cant":"501","hossein soltain-tehrani":"776",
    "ian scott":"773","jack eagle":"690","lee reynolds":"233",
    "louis holman":"800","mark wilson":"952","michael mutirwara":"711",
    "mustafa raza":"855","nick green":"820","nigel lomax":"405",
    "paul holman":"808","rhys standing":"982","ricky parrett":"239",
    "rob carlisle":"799","scott morgan":"681","sean craig":"308",
    "shane sheppard":"676","stephen martin":"844","terry jones":"884",
    "trymore mavhangira":"696","umit salah":"731","vincent magombe":"761",
    "wes mwashaireni":"694",
}


def batch_upsert(sb, table, rows, conflict):
    """Upsert rows in batches."""
    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i+BATCH_SIZE]
        sb.table(table).upsert(chunk, on_conflict=conflict).execute()
        total += len(chunk)
    return total


def main():
    print("=" * 60)
    print("Fleet Manager → Supabase Sync")
    print("=" * 60)

    # Connect to Fleet Manager SQLite
    if not os.path.exists(FLEET_DB):
        print(f"❌  Fleet DB not found: {FLEET_DB}")
        sys.exit(1)

    conn = sqlite3.connect(FLEET_DB)
    conn.row_factory = sqlite3.Row

    # Init Supabase client
    try:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    except ImportError:
        print("Installing supabase…")
        os.system("pip3 install --break-system-packages --quiet supabase")
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ── Ensure migration columns exist on the live fleet.db ──────────────────
    # The sandbox working copy had these added; the production db may not.
    # Engineer table columns
    for col, typedef in [
        ("department",   "TEXT"),
        ("engineerType", "TEXT"),
        ("brighthrId",   "TEXT"),
        ("isActive",     "INTEGER DEFAULT 1"),
    ]:
        try:
            conn.execute(f'ALTER TABLE Engineer ADD COLUMN "{col}" {typedef}')
            conn.commit()
            print(f"  ℹ  Added missing column: Engineer.{col}")
        except Exception:
            pass  # already exists

    # Absence table columns
    for col, typedef in [
        ("brighthrId",          "TEXT"),
        ("durationDays",        "INTEGER"),
        ("absenceTypeCategory", "TEXT"),
    ]:
        try:
            conn.execute(f'ALTER TABLE Absence ADD COLUMN "{col}" {typedef}')
            conn.commit()
            print(f"  ℹ  Added missing column: Absence.{col}")
        except Exception:
            pass  # already exists

    for ddl in [
        """CREATE TABLE IF NOT EXISTS "EquipmentSkill" (
            "id" TEXT NOT NULL PRIMARY KEY,
            "engineerId" TEXT NOT NULL,
            "category" TEXT NOT NULL DEFAULT 'general',
            "name" TEXT NOT NULL,
            "hasSkill" INTEGER NOT NULL DEFAULT 1,
            "notes" TEXT,
            "updatedAt" TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE("engineerId","name"),
            FOREIGN KEY("engineerId") REFERENCES "Engineer"("id") ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS "Certification" (
            "id" TEXT NOT NULL PRIMARY KEY,
            "engineerId" TEXT NOT NULL,
            "type" TEXT NOT NULL,
            "name" TEXT NOT NULL,
            "certNumber" TEXT,
            "issueDate" TEXT,
            "expiryDate" TEXT,
            "status" TEXT NOT NULL DEFAULT 'pending',
            "notes" TEXT,
            "updatedAt" TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE("engineerId","type"),
            FOREIGN KEY("engineerId") REFERENCES "Engineer"("id") ON DELETE CASCADE
        )""",
    ]:
        try:
            conn.execute(ddl)
            conn.commit()
        except Exception:
            pass

    # ── 1. Engineers ──────────────────────────────────────────────────────────
    print("\n[1/4] Syncing engineers…")
    engineers = conn.execute(
        "SELECT id, firstName, lastName, email, department, engineerType, brighthrId, isActive FROM Engineer"
    ).fetchall()

    eng_rows = []
    for e in engineers:
        full_raw = f"{e['firstName']} {e['lastName']}"
        full = NAME_MAP.get(full_raw, full_raw)          # canonical name
        full_lower = full.lower()
        vt_id = VISITOUR_IDS.get(full_lower)
        dept = e["department"] or dept_from_vt(vt_id, full)
        # Write department back to fleet.db if it was missing
        if dept and not e["department"]:
            conn.execute('UPDATE Engineer SET department=? WHERE id=?', (dept, e["id"]))
        eng_rows.append({
            "name": full,
            "department": dept,
            "engineer_type": e["engineerType"],
            "email": e["email"],
            "visitour_id": vt_id,
            "brighthr_id": e["brighthrId"],
            "active": bool(e["isActive"]),
        })

    conn.commit()  # flush any department backfills

    # Update adv_engineers (match by name)
    ok = 0
    for row in eng_rows:
        try:
            sb.table("adv_engineers").update({
                "department": row["department"],
                "engineer_type": row["engineer_type"],
                "email": row["email"],
                "visitour_id": row["visitour_id"],
                "brighthr_id": row["brighthr_id"],
            }).eq("adv_name", row["name"]).execute()
            ok += 1
        except Exception as ex:
            print(f"  ⚠  {row['name']}: {ex}")

    print(f"  ✅  {ok}/{len(eng_rows)} engineers updated")

    # ── 2. Equipment Skills (from Fleet Manager DB) ────────────────────────────
    print("\n[2/4] Syncing equipment skills…")
    # EquipmentSkill table may not exist yet on unmigrated db
    has_eq_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='EquipmentSkill'"
    ).fetchone()
    if has_eq_table:
        skill_rows_db = conn.execute("""
            SELECT e.firstName||' '||e.lastName as eng_name,
                   s.category, s.name as skill_name, s.hasSkill, s.notes
            FROM EquipmentSkill s JOIN Engineer e ON s.engineerId=e.id
        """).fetchall()
    else:
        skill_rows_db = []
        print("  ℹ  EquipmentSkill table not found — using VISITOUR data only")

    # Also add VISITOUR skills for engineers missing from Fleet Manager skills
    vt_skill_rows = []
    for e in engineers:
        full_raw = f"{e['firstName']} {e['lastName']}"
        full = NAME_MAP.get(full_raw, full_raw)
        full_lower = full.lower()
        vt_id = VISITOUR_IDS.get(full_lower)
        skills = VT_SKILLS_BY_FM_ID.get(vt_id, []) if vt_id else []
        if not skills:
            skills = VT_SKILLS_BY_NAME.get(full, [])
        for s in skills:
            vt_skill_rows.append({
                "engineer_name": full,
                "category": "visitour",
                "skill_name": s,
                "has_skill": True,
                "notes": "From VISITOUR scheduling",
            })

    # Fleet Manager skills (normalise names)
    fm_skill_rows = [{
        "engineer_name": NAME_MAP.get(r["eng_name"], r["eng_name"]),
        "category": r["category"],
        "skill_name": r["skill_name"],
        "has_skill": bool(r["hasSkill"]),
        "notes": r["notes"],
    } for r in skill_rows_db]

    all_skills = fm_skill_rows + vt_skill_rows
    n = batch_upsert(sb, "adv_engineer_skills", all_skills, "engineer_name,skill_name")
    print(f"  ✅  {n} skill rows upserted ({len(fm_skill_rows)} FM + {len(vt_skill_rows)} VISITOUR)")

    # ── 3. Certifications ─────────────────────────────────────────────────────
    print("\n[3/4] Syncing certifications…")
    has_cert_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Certification'"
    ).fetchone()
    if has_cert_table:
        cert_rows_db = conn.execute("""
            SELECT e.firstName||' '||e.lastName as eng_name,
                   c.type, c.name, c.certNumber, c.issueDate, c.expiryDate, c.status, c.notes
            FROM Certification c JOIN Engineer e ON c.engineerId=e.id
        """).fetchall()
    else:
        cert_rows_db = []
        print("  ℹ  Certification table not found — skipping")

    cert_rows = [{
        "engineer_name": NAME_MAP.get(r["eng_name"], r["eng_name"]),
        "cert_type": r["type"],
        "cert_name": r["name"],
        "cert_number": r["certNumber"],
        "issue_date": r["issueDate"][:10] if r["issueDate"] else None,
        "expiry_date": r["expiryDate"][:10] if r["expiryDate"] else None,
        "status": r["status"],
        "notes": r["notes"],
    } for r in cert_rows_db]

    n = batch_upsert(sb, "adv_engineer_certs", cert_rows, "engineer_name,cert_type")
    print(f"  ✅  {n} certification rows upserted")

    # ── 4. Absences ───────────────────────────────────────────────────────────
    print("\n[4/4] Syncing absences…")
    # Check which optional columns exist in Absence table
    abs_cols = {row[1] for row in conn.execute("PRAGMA table_info(Absence)").fetchall()}
    brighthr_col  = "a.brighthrId"  if "brighthrId"   in abs_cols else "NULL"
    duration_col  = "a.durationDays" if "durationDays" in abs_cols else "NULL"

    absence_rows_db = conn.execute(f"""
        SELECT e.firstName||' '||e.lastName as eng_name,
               {brighthr_col} as brighthrId,
               a.startDate, a.endDate, a.absenceType,
               {duration_col} as durationDays
        FROM Absence a JOIN Engineer e ON a.engineerId=e.id
        WHERE a.startDate >= date('now', '-90 days')
    """).fetchall()

    absence_rows = [{
        "engineer_name": NAME_MAP.get(r["eng_name"], r["eng_name"]),
        "brighthr_id": r["brighthrId"],
        "start_date": r["startDate"],
        "end_date": r["endDate"],
        "absence_type": r["absenceType"],
        "duration_days": r["durationDays"],
    } for r in absence_rows_db]

    n = batch_upsert(sb, "adv_engineer_absences", absence_rows, "engineer_name,brighthr_id")
    print(f"  ✅  {n} absence rows upserted")

    conn.close()
    print(f"\n{'='*60}")
    print("✅  Sync complete!")
    print(f"{'='*60}")
    print("\nTo refresh absence data, run BrightHR sync first:")
    print("  python3 ~/Documents/Projects/Advance-Apps/fleet-app/brighthr_sync.py")
    print("Then re-run this script to push to Supabase.")


if __name__ == "__main__":
    main()
