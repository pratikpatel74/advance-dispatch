#!/usr/bin/env python3
"""
load_advantage_data.py
======================
Merges Advantage spreadsheet exports and loads them into Supabase adv_* tables.

Tables loaded:
  adv_engineers      = our 35 active engineers (VISITOUR config)
  adv_customers      = Customers.xlsx
  adv_sites          = Sites.xlsx (with address/postcode/lat/lon)
  adv_calls          = Calls.xlsx joined with Sites + Customers + Engineers
                       Extra fields: cal_opened, cancelled, sla_due
  adv_equipment      = Equipment.xlsx joined with Sites + Customers
  adv_contracts      = Contracts.xlsx joined with Customers
  adv_contract_sites = Contract_Sites.xlsx (contract ↔ site junction)

Also available: adv_calls_open view — open calls with chatbot-compatible
field aliases (customerstatus, callopened, closedate, sladue, engineer).

Usage:
    pip install supabase openpyxl
    python3 load_advantage_data.py --xlsx-dir /path/to/spreadsheets

    # Dry-run (no inserts, just shows counts):
    python3 load_advantage_data.py --xlsx-dir /path/to/spreadsheets --dry-run

    # Truncate and reload from scratch:
    python3 load_advantage_data.py --xlsx-dir /path/to/spreadsheets --truncate

    # Load only specific tables:
    python3 load_advantage_data.py --xlsx-dir /path/to/spreadsheets --tables calls,equipment

Supabase credentials (edit below or set as env vars):
    SUPABASE_URL  / SUPABASE_KEY
"""

import os
import sys
import argparse
import openpyxl
from datetime import datetime

# ── Supabase credentials ──────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ehuhqzjnikvykldasygc.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_3Y96gLmPnl6I4Bk9kGJKXA_QRWT0gNt")
# For bulk inserts the service role key is needed. Set SUPABASE_KEY to your
# service role key, or use SUPABASE_DB_URL for direct psycopg2 connection.
# SUPABASE_DB_URL = "postgresql://postgres:YOUR_PASSWORD@db.ehuhqzjnikvykldasygc.supabase.co:5432/postgres"
# ─────────────────────────────────────────────────────────────────────────────

BATCH_SIZE = 500  # rows per upsert batch

# ── Our 35 VISITOUR/Advance engineers ─────────────────────────────────────────
# (id, adv_name, vt_name, company, department, postcode, lat, lon, shift_start, shift_end)
OUR_ENGINEERS = [
    (487,  "Anthony Reid",              "Tony Reid",               "Advance",             "Catering",  "GU11 1BJ", 51.2482, -0.7680, "07:00", "15:00"),
    (858,  "Aritotelis Goudelis",       "Aristotelis Goudelis",    "Advance",             "Catering",  "CR0 7HH",  51.3560, -0.0701, "07:00", "15:00"),
    (689,  "Carl Mills",                "Carl Mills",              "Cooling by Advance",  "Cooling",   "GL7 1EJ",  51.7105, -1.9810, "08:00", "16:00"),
    (802,  "Charles Tidey",             "Charles Tidey",           "Advance",             "Catering",  "TN39 3HN", 50.8440, 0.4690,  "06:30", "14:30"),
    (240,  "Chris Amor",                "Chris Amor",              "Advance",             "Catering",  "SO50 9LP", 50.9600, -1.3500, "08:00", "17:00"),
    (348,  "Franc Genovese",            "Franc Genovese",          "Advance",             "Catering",  "SE18 1NJ", 51.4850, 0.0780,  "06:00", "14:00"),
    (926,  "Gareth Terrell",            "Gareth Terrell",          "Cooling by Advance",  "Cooling",   "CF62 4JR", 51.3940, -3.3540, "06:00", "14:00"),
    (501,  "Gary Cant",                 "Gary Cant",               "Advance",             "Catering",  "ME10 4PL", 51.3410, 0.7480,  "08:00", "16:00"),
    (776,  "Hossein Soltain-Tehrani",   "Hossein Soltani-Tehrani", "Cooling by Advance",  "Cooling",   "WD23 2QX", 51.6530, -0.3090, "08:00", "16:00"),
    (773,  "Ian Scott",                 "Ian Scott",               "Advance",             "Catering",  "RH15 9BJ", 50.9890, -0.1230, "07:00", "15:00"),
    (690,  "Jack Eagle",                "Jack Eagle",              "Cooling by Advance",  "Cooling",   "MK18 1LJ", 51.9980, -0.9820, "07:00", "15:00"),
    (233,  "Lee Reynolds",              "Lee Reynolds",            "Advance",             "Catering",  "RM14 1AB", 51.5580, 0.2450,  "05:30", "13:30"),
    (800,  "Louis Holman",              "Louis Holman",            "Advance",             "Catering",  "PO19 7PB", 50.8360, -0.7720, "07:30", "15:30"),
    (378,  "Mark Holmes",               "Mark Holmes",             "Advance",             "Catering",  "SL6 5BN",  51.5160, -0.7400, "06:00", "14:00"),
    (952,  "Mark Wilson",               "Mark Wilson",             "Cooling by Advance",  "Cooling",   "LS27 7JU", 53.7400, -1.5810, "09:00", "17:00"),
    (711,  "Michael Mutirwara",         "Michael Mutirwara",       "Cooling by Advance",  "Cooling",   "SW16 3RL", 51.4080, -0.1260, "09:00", "17:00"),
    (855,  "Mustafa Raza",              "Mustafa Raza",            "Cooling by Advance",  "Cooling",   "UB5 4LT",  51.5420, -0.3680, "07:00", "15:00"),
    (820,  "Nick Green",                "Nick Green",              "Advance",             "Catering",  "SO16 4QS", 50.9390, -1.4270, "06:30", "14:30"),
    (405,  "Nigel Lomax",               "Nigel Lomax",             "Advance",             "Catering",  "LS26 0JJ", 53.7380, -1.4720, "07:00", "15:00"),
    (808,  "Paul Holman",               "Paul Holman",             "Advance",             "Catering",  "PO19 5SU", 50.8300, -0.7740, "06:00", "14:00"),
    (982,  "Rhys Standing",             "Rhys Standing",           "Advance",             "Catering",  "CF24 0PE", 51.4890, -3.1530, "06:30", "14:30"),
    (239,  "Ricky Parrett",             "Ricky Parrett",           "Advance",             "Catering",  "BR8 7AL",  51.3770, 0.1760,  "05:00", "13:00"),
    (799,  "Rob Carlisle",              "Rob Carlisle",            "Cooling by Advance",  "Cooling",   "LS15 0PT", 53.8020, -1.4460, "08:30", "16:30"),
    (723,  "Roy Aris",                  "Roy Aris",                "Cooling by Advance",  "Cooling",   "CV2 3GS",  52.4300, -1.4580, "07:30", "15:30"),
    (681,  "Scott Morgan",              "Scott Morgan",            "Advance",             "Catering",  "CF35 5DY", 51.5200, -3.5810, "08:00", "16:00"),
    (308,  "Sean Craig",                "Sean Craig",              "Advance",             "Catering",  "IG6 2UQ",  51.5990, 0.0930,  "05:30", "13:30"),
    (676,  "Shane Sheppard",            "Shane Sheppard",          "Advance",             "Catering",  "BS16 2QH", 51.4910, -2.5090, "09:00", "17:00"),
    (844,  "Stephen Martin",            "Stephen Martin",          "Advance",             "Catering",  "SO40 9FL", 50.9060, -1.5700, "07:00", "15:00"),
    (884,  "Terry Jones",               "Terry Jones",             "Advance",             "Catering",  "TN11 0AN", 51.2200, 0.2390,  "05:00", "13:00"),
    (696,  "Trymore Mavhangira",        "Trymore Mavhangira",      "Cooling by Advance",  "Cooling",   "LS12 4LH", 53.7920, -1.5730, "09:00", "17:00"),
    (731,  "Umit Salah",                "Umit Salah",              "Cooling by Advance",  "Cooling",   "N4 2PX",   51.5720, -0.1110, "08:00", "16:00"),
    (761,  "Vincent Magombe",           "Vincent Magombe",         "Cooling by Advance",  "Cooling",   "HA8 6ND",  51.6090, -0.2530, "08:00", "16:00"),
    (694,  "Wes Mwashaireni",           "Wes Mwashaireni",         "Cooling by Advance",  "Cooling",   "OX4 6NS",  51.7300, -1.2070, "09:00", "17:00"),
    (857,  "Ryan Mongiovi",             "Ryan Mongiovi",           "Cooling by Advance",  "Cooling",   "LS17 6LB", 53.8610, -1.5490, "07:00", "15:00"),
    (10009,"Derek Fisher",              "Derek Fisher",            "Advance",             "Catering",  "GU12 4PS", 51.2480, -0.7630, "09:00", "17:00"),
]

OUR_ENGINEER_IDS = {e[0] for e in OUR_ENGINEERS}


def load_wb(path):
    print(f"  Loading {os.path.basename(path)}…")
    return openpyxl.load_workbook(path, read_only=True, data_only=True)


def dt_to_iso(val):
    if isinstance(val, datetime):
        return val.isoformat()
    return None


def str_or_none(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def to_date(val):
    if isinstance(val, datetime):
        return val.date().isoformat()
    return None


import re as _re

def infer_skills_from_description(desc):
    """Mirror of the SQL infer_skills_from_description() function.
    Returns a list of skill names inferred from the job description text."""
    if not desc:
        return []
    d = desc.lower()
    skills = []
    if _re.search(r'(fridge|refrigerat|freezer|cold room|bottle cooler|ice machine|chiller|cold stor|walk.in.cold)', d):
        skills.append('Refrigeration')
    if _re.search(r'(dishwasher|glasswasher|warewasher|rack washer|dish wash|glass wash)', d):
        skills.append('Warewashing')
    if _re.search(r'(combi|rational|convotherm|combination oven|combisteamer|combi oven|combimaster|icombi)', d):
        skills.append('Combi')
    if _re.search(r'(microwave)', d):
        skills.append('Microwave')
    if _re.search(r'(boiler|water boiler|hot water urn|hot water unit|table.?top boiler|wall.?mount.?boiler)', d):
        skills.append('Water Boilers')
    if _re.search(r'(extract|canopy|ventilat|exhaust fan|ductwork)', d):
        skills.append('Extraction')
    if _re.search(r'(air con|air-con|aircon|a/c unit|hvac|split unit|air conditioning)', d):
        skills.append('Air Con')
    if _re.search(r'(insect|fly trap|flytrap|fly killer|fly strip|executor|exocutor|electrocutor|uv lamp|insect.?cutor|bug killer)', d):
        skills.append('Insect Killer')
    if _re.search(r'(waste disposal|macerator|food waste|garbage disposal)', d):
        skills.append('Waste Disposal')
    if _re.search(r'(gantry)', d):
        skills.append('Gantry')
    if _re.search(r'(holding unit|hot cupboard|thermodyne|holding cabinet|bain marie|hot hold)', d):
        skills.append('Holding Unit')
    if _re.search(r'(fryer|griddle|bratt pan|wok|range|burner|salamander|convect|oven|grill|planchas|broiler|char.?grill|steamer|pasta cooker|chip scuttle)', d):
        skills.append('Prime Cooking')
    if _re.search(r'(mixer|blender|food processor|slicer|cutter|peeler|rumbler|mince|dough|mincer|grinder|chopper|mandolin)', d):
        skills.append('Prep')
    if _re.search(r'(gas leak|gas supply|gas pressure|gas pipe|gas main|lpg|natural gas|gas interlock)', d):
        skills.append('Gas')
    return skills


def batch_upsert(client, table, rows, dry_run=False, on_conflict="id"):
    """Upsert rows in batches. Returns total inserted."""
    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        if not dry_run:
            client.table(table).upsert(chunk, on_conflict=on_conflict).execute()
        total += len(chunk)
        print(f"    {table}: {min(i+BATCH_SIZE, len(rows)):,}/{len(rows):,} rows", end="\r")
    print()
    return total


def main():
    parser = argparse.ArgumentParser(description="Load Advantage data into Supabase")
    parser.add_argument("--xlsx-dir",  default=".", help="Directory containing xlsx files")
    parser.add_argument("--calls",      default=None)
    parser.add_argument("--sites",      default=None)
    parser.add_argument("--customers",  default=None)
    parser.add_argument("--engineers",  default=None)
    parser.add_argument("--equipment",  default=None)
    parser.add_argument("--contracts",  default=None)
    parser.add_argument("--contract-sites", default=None)
    parser.add_argument("--dry-run",    action="store_true", help="Show counts only, no inserts")
    parser.add_argument("--truncate",   action="store_true", help="Truncate tables before loading")
    parser.add_argument("--tables",     default=None,
                        help="Comma-separated list of tables to load: engineers,customers,sites,calls,equipment,contracts (default: all)")
    args = parser.parse_args()

    d = args.xlsx_dir
    calls_path          = args.calls           or os.path.join(d, "Calls.xlsx")
    sites_path          = args.sites           or os.path.join(d, "Sites.xlsx")
    customers_path      = args.customers       or os.path.join(d, "Customers.xlsx")
    engineers_path      = args.engineers       or os.path.join(d, "Engineers.xlsx")
    equipment_path      = args.equipment       or os.path.join(d, "Equipment.xlsx")
    contracts_path      = args.contracts       or os.path.join(d, "Contracts.xlsx")
    contract_sites_path = args.contract_sites  or os.path.join(d, "Contract_Sites.xlsx")

    load_tables = set(args.tables.split(",")) if args.tables else \
                  {"engineers", "customers", "sites", "calls", "equipment", "contracts"}

    for p in [calls_path, sites_path, customers_path, engineers_path,
              equipment_path, contracts_path, contract_sites_path]:
        if not os.path.exists(p):
            print(f"WARNING: File not found: {p}")  # warn but don't abort

    # ── Supabase client ───────────────────────────────────────────────────────
    if not args.dry_run:
        try:
            from supabase import create_client
        except ImportError:
            print("ERROR: supabase not installed. Run: pip install supabase")
            sys.exit(1)
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        if args.truncate:
            print("Truncating adv_* tables…")
            for t in ["adv_contract_sites", "adv_calls", "adv_equipment",
                      "adv_contracts", "adv_sites", "adv_customers", "adv_engineers"]:
                sb.table(t).delete().neq("id", -999999).execute()
                print(f"  Truncated {t}")
    else:
        sb = None
        print("[DRY RUN — no data will be written]\n")

    # ── 1. Load lookup tables into memory ────────────────────────────────────
    print("\n--- Loading reference data ---")
    load_tables_all = {"engineers", "customers", "sites", "calls", "equipment", "contracts"}

    # Customers: col[0]=id, col[1]=name, col[2]=parent_id, col[3]=parent_name,
    #            col[4]=account_scope, col[5]=sector, col[6]=account_manager, col[19]=active
    wb_c = load_wb(customers_path)
    customers = {}
    adv_customers_rows = []
    for row in wb_c.active.iter_rows(values_only=True):
        cid = row[0]
        if not isinstance(cid, int):
            continue
        name = str_or_none(row[1]) or ""
        customers[cid] = name
        active_raw = row[19] if len(row) > 19 else None
        adv_customers_rows.append({
            "id":              cid,
            "name":            name,
            "parent_id":       row[2] if isinstance(row[2], int) else None,
            "parent_name":     str_or_none(row[3]),
            "account_scope":   str_or_none(row[4]),
            "sector":          str_or_none(row[5]),
            "account_manager": str_or_none(row[6]),
            "active":          bool(active_raw) if active_raw is not None else True,
        })
    print(f"  Customers: {len(adv_customers_rows):,}")

    # Sites: col[0]=id, col[1]=customer_id, col[2]=name, col[3]=fuel_type,
    #        col[4]=address, col[5]=town, col[6]=county, col[7]=postcode,
    #        col[8]=lat, col[9]=lon, col[10]=contact, col[11]=phone,
    #        col[13]=email, col[18]=active
    wb_s = load_wb(sites_path)
    sites = {}  # id → (name, address, town, county, postcode, lat, lon)
    adv_sites_rows = []
    for row in wb_s.active.iter_rows(values_only=True):
        sid = row[0]
        if not isinstance(sid, int):
            continue
        full_addr = ", ".join(filter(None, [
            str_or_none(row[4]),
            str_or_none(row[5]),
            str_or_none(row[6]),
        ]))
        postcode = str_or_none(row[7])
        lat = row[8] if isinstance(row[8], (int, float)) else None
        lon = row[9] if isinstance(row[9], (int, float)) else None
        sites[sid] = {
            "name":    str_or_none(row[2]),
            "address": full_addr or None,
            "postcode": postcode,
            "lat": lat,
            "lon": lon,
        }
        active_raw = row[18] if len(row) > 18 else None
        adv_sites_rows.append({
            "id":           sid,
            "customer_id":  row[1] if isinstance(row[1], int) else None,
            "name":         str_or_none(row[2]),
            "address":      full_addr or None,
            "town":         str_or_none(row[5]),
            "county":       str_or_none(row[6]),
            "postcode":     postcode,
            "latitude":     lat,
            "longitude":    lon,
            "contact_name": str_or_none(row[10]),
            "phone":        str_or_none(row[11]),
            "email":        str_or_none(row[13]) if len(row) > 13 else None,
            "active":       bool(active_raw) if active_raw is not None else True,
        })
    print(f"  Sites: {len(adv_sites_rows):,}")

    # ── 2. adv_engineers ──────────────────────────────────────────────────────
    print("\n--- Building adv_engineers ---")
    # Load Advantage engineer types for reference
    wb_e = load_wb(engineers_path)
    adv_eng_types = {r[0]: (r[1], r[2], r[3]) for r in wb_e.active.iter_rows(values_only=True)
                     if isinstance(r[0], int)}

    adv_engineers_rows = []
    for (eid, adv_name, vt_name, company, dept, postcode, lat, lon,
         shift_start, shift_end) in OUR_ENGINEERS:
        eng_info = adv_eng_types.get(eid, (None, None, None))
        adv_engineers_rows.append({
            "id":            eid,
            "adv_name":      adv_name,
            "vt_name":       vt_name,
            "engineer_type": eng_info[1],   # 'Internal Engineer', 'Subcontractor'
            "company":       company,
            "department":    dept,
            "postcode":      postcode,
            "home_lat":      lat,
            "home_lon":      lon,
            "shift_start":   shift_start,
            "shift_end":     shift_end,
            "active":        True,
        })
    print(f"  Engineers: {len(adv_engineers_rows)}")

    # ── 3. adv_calls (merged) ─────────────────────────────────────────────────
    print("\n--- Building adv_calls (merging Calls + Sites + Customers) ---")
    # Calls cols (0-indexed):
    # 0=call_id, 3=customer_id, 4=site_id, 5=visit_id(PK),
    # 6=status(customerstatus), 8=call_type, 9=cal_opened, 10=scheduled_time,
    # 11=actual_start, 12=completed_at(closedate), 15=engineer_id,
    # 16=engineer_name, 17=eng_start, 18=eng_end, 19=description,
    # 20=eng_notes, 21=completion_status, 22=fault_outcome, 23=category,
    # 25=cancelled (0/1)
    wb_calls = load_wb(calls_path)
    adv_calls_rows = []
    skipped = 0
    for row in wb_calls.active.iter_rows(values_only=True):
        eng_id = row[15]
        if eng_id not in OUR_ENGINEER_IDS:
            skipped += 1
            continue
        visit_id = row[5]
        if not isinstance(visit_id, int):
            skipped += 1
            continue

        site_id = row[4]
        cust_id = row[3]
        site = sites.get(site_id, {})
        cust_name = customers.get(cust_id)

        adv_calls_rows.append({
            "id":                visit_id,
            "call_id":           row[0] if isinstance(row[0], int) else None,
            "customer_id":       cust_id if isinstance(cust_id, int) else None,
            "customer_name":     cust_name,
            "site_id":           site_id if isinstance(site_id, int) else None,
            "site_name":         site.get("name"),
            "address":           site.get("address"),
            "postcode":          site.get("postcode"),
            "latitude":          site.get("lat"),
            "longitude":         site.get("lon"),
            "engineer_id":       eng_id,
            "engineer_name":     str_or_none(row[16]),
            "status":            str_or_none(row[6]),
            "call_type":         str_or_none(row[8]),
            "cal_opened":        dt_to_iso(row[9]),   # callopened in chatbot CSV
            "scheduled_time":    dt_to_iso(row[10]),
            "actual_start":      dt_to_iso(row[11]),
            "actual_end":        dt_to_iso(row[18]),
            "completed_at":      dt_to_iso(row[12]),  # closedate in chatbot CSV
            "cancelled":         int(row[25]) if isinstance(row[25], (int, float)) else 0,
            "description":       str_or_none(row[19]),
            "engineer_notes":    str_or_none(row[20]),
            "completion_status": str_or_none(row[21]),
            "fault_outcome":     str_or_none(row[22]),
            "category":          str_or_none(row[23]),
            "required_skills":   infer_skills_from_description(str_or_none(row[19])),
        })

    print(f"  Calls matched to our engineers: {len(adv_calls_rows):,}")
    print(f"  Calls skipped (other engineers): {skipped:,}")

    # ── 4. adv_equipment (merged) ─────────────────────────────────────────────
    print("\n--- Building adv_equipment (merging Equipment + Sites + Customers) ---")
    # Equipment cols:
    # 0=id, 1=site_id, 2=customer_id, 3=serial_ref, 4=asset_no,
    # 5=make, 6=model, 7=description, 8=category, 9=asset_type,
    # 10=condition, 12=install_date, 13=purchase_date, 14=warranty_end,
    # 15=warranty_status, 16=active
    wb_eq = load_wb(equipment_path)
    adv_equipment_rows = []
    for row in wb_eq.active.iter_rows(values_only=True):
        eq_id = row[0]
        if not isinstance(eq_id, int):
            continue
        site_id = row[1]
        cust_id = row[2]
        site = sites.get(site_id, {})
        cust_name = customers.get(cust_id)

        adv_equipment_rows.append({
            "id":              eq_id,
            "site_id":         site_id if isinstance(site_id, int) else None,
            "customer_id":     cust_id if isinstance(cust_id, int) else None,
            "serial_ref":      str_or_none(row[3]),
            "asset_no":        int(row[4]) if isinstance(row[4], (int, float)) and abs(int(row[4])) <= 9223372036854775807 else None,
            "make":            str_or_none(row[5]),
            "model":           str_or_none(row[6]),
            "description":     str_or_none(row[7]),
            "category":        str_or_none(row[8]),
            "asset_type":      str_or_none(row[9]),
            "condition":       str_or_none(row[10]),
            "install_date":    to_date(row[12]),
            "purchase_date":   to_date(row[13]),
            "warranty_end":    to_date(row[14]),
            "warranty_status": str_or_none(row[15]),
            "active":          bool(row[16]) if row[16] is not None else True,
            # Joined fields
            "site_name":       site.get("name"),
            "customer_name":   cust_name,
            "postcode":        site.get("postcode"),
        })
    print(f"  Equipment: {len(adv_equipment_rows):,}")

    # ── 5. adv_contracts + adv_contract_sites ────────────────────────────────
    print("\n--- Building adv_contracts ---")
    # Contracts cols:
    # 0=id, 1=name, 2=customer_id, 3=start_date, 4=end_date,
    # 5=status, 6=coverage_type, 7=site_count
    wb_co = load_wb(contracts_path)
    adv_contracts_rows = []
    for row in wb_co.active.iter_rows(values_only=True):
        co_id = row[0]
        if not isinstance(co_id, int):
            continue
        cust_id = row[2] if isinstance(row[2], int) else None
        adv_contracts_rows.append({
            "id":            co_id,
            "name":          str_or_none(row[1]),
            "customer_id":   cust_id,
            "customer_name": customers.get(cust_id) if cust_id else None,
            "start_date":    to_date(row[3]) if isinstance(row[3], datetime) else None,
            "end_date":      to_date(row[4]) if isinstance(row[4], datetime) else None,
            "status":        str_or_none(row[5]),
            "coverage_type": str_or_none(row[6]),
            "site_count":    int(row[7]) if isinstance(row[7], (int, float)) else 0,
        })
    print(f"  Contracts: {len(adv_contracts_rows):,}")

    print("\n--- Building adv_contract_sites ---")
    wb_cs = load_wb(contract_sites_path)
    adv_contract_sites_rows = []
    seen_cs = set()
    for row in wb_cs.active.iter_rows(values_only=True):
        co_id, site_id = row[0], row[1]
        if not (isinstance(co_id, int) and isinstance(site_id, int)):
            continue
        key = (co_id, site_id)
        if key not in seen_cs:
            seen_cs.add(key)
            adv_contract_sites_rows.append({"contract_id": co_id, "site_id": site_id})
    print(f"  Contract-site links: {len(adv_contract_sites_rows):,}")

    # ── 6. Summary / insert ──────────────────────────────────────────────────
    if args.dry_run:
        print("\n[DRY RUN] Would insert:")
        print(f"  adv_engineers:      {len(adv_engineers_rows)} rows")
        print(f"  adv_customers:      {len(adv_customers_rows):,} rows")
        print(f"  adv_sites:          {len(adv_sites_rows):,} rows")
        print(f"  adv_calls:          {len(adv_calls_rows):,} rows")
        print(f"  adv_equipment:      {len(adv_equipment_rows):,} rows")
        print(f"  adv_contracts:      {len(adv_contracts_rows):,} rows")
        print(f"  adv_contract_sites: {len(adv_contract_sites_rows):,} rows")
        return

    # Deduplicate by primary key before inserting (Advantage data can have duplicate IDs)
    def dedup(rows, key="id"):
        seen = {}
        for r in rows:
            seen[r[key]] = r
        return list(seen.values())

    adv_engineers_rows      = dedup(adv_engineers_rows)
    adv_customers_rows      = dedup(adv_customers_rows)
    adv_sites_rows          = dedup(adv_sites_rows)
    adv_calls_rows          = dedup(adv_calls_rows)
    adv_equipment_rows      = dedup(adv_equipment_rows)
    adv_contracts_rows      = dedup(adv_contracts_rows)

    print("\n--- Inserting into Supabase ---")
    if "engineers"  in load_tables: batch_upsert(sb, "adv_engineers",      adv_engineers_rows)
    if "customers"  in load_tables: batch_upsert(sb, "adv_customers",      adv_customers_rows)
    if "sites"      in load_tables: batch_upsert(sb, "adv_sites",          adv_sites_rows)
    if "calls"      in load_tables: batch_upsert(sb, "adv_calls",          adv_calls_rows)
    if "equipment"  in load_tables: batch_upsert(sb, "adv_equipment",      adv_equipment_rows)
    if "contracts"  in load_tables:
        batch_upsert(sb, "adv_contracts",      adv_contracts_rows)
        batch_upsert(sb, "adv_contract_sites", adv_contract_sites_rows, on_conflict="contract_id,site_id")

    print("\n✓ All done.")
    print(f"  adv_engineers:      {len(adv_engineers_rows)} rows")
    print(f"  adv_customers:      {len(adv_customers_rows):,} rows")
    print(f"  adv_sites:          {len(adv_sites_rows):,} rows")
    print(f"  adv_calls:          {len(adv_calls_rows):,} rows")
    print(f"  adv_equipment:      {len(adv_equipment_rows):,} rows")
    print(f"  adv_contracts:      {len(adv_contracts_rows):,} rows")
    print(f"  adv_contract_sites: {len(adv_contract_sites_rows):,} rows")
    print(f"\nNote: SUPABASE_KEY used: {SUPABASE_KEY[:20]}...")
    print("If you see permission errors, set SUPABASE_KEY to your service role key.")
    print("Get it from: Supabase dashboard → Settings → API → service_role")


if __name__ == "__main__":
    main()
