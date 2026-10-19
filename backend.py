#!/usr/bin/env python3
"""
Advance Dispatch — VISITOUR Backend API
========================================
Flask app that proxies VISITOUR SOAP calls and serves JSON to the frontend.

Endpoints:
  GET /api/schedule?date=YYYY-MM-DD   — calls scheduled for a date (or range)
  GET /api/engineers                  — engineer list with config
  GET /health                         — liveness check

Run:
  python3 backend.py
  (listens on port 3004 by default)
"""

import re
import os
import jwt as pyjwt
from datetime import date, timedelta, datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__)
CORS(app)

# ── BrightHR connection ───────────────────────────────────────────────────────
BHR_TOKEN_URL  = "https://login.brighthr.com/connect/token"
BHR_EMP_URL    = "https://api.bright.hr/employees/v1/query"
BHR_CLIENT_ID  = os.environ.get("BHR_CLIENT_ID",  "CapiApp_dccf2bcf-de20-41b1-8af4-acbd0b368682")
BHR_CLIENT_SEC = os.environ.get("BHR_CLIENT_SECRET", "mavhd4GSsMMn3RnBrSlyIqPWLleTe0tGn-OfpW7xZTM")

def brighthr_token() -> str:
    r = requests.post(BHR_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials",
              "client_id": BHR_CLIENT_ID,
              "client_secret": BHR_CLIENT_SEC},
        timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]

def brighthr_engineers() -> list:
    """Fetch all active (non-terminated) employees from BrightHR."""
    token = brighthr_token()
    result, continuation_token = [], None
    while True:
        body = {"continuationToken": continuation_token} if continuation_token else {}
        r = requests.post(BHR_EMP_URL,
            headers={"Authorization": f"Bearer {token}"},
            json=body, timeout=15)
        r.raise_for_status()
        data = r.json()
        for emp in data.get("items", []):
            if emp.get("_metadata", {}).get("isTerminated"):
                continue
            result.append(emp)
        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break
    return result

# ── Fleet Manager connection (same server, port 8080) ────────────────────────
FLEET_BASE       = os.environ.get("FLEET_BASE", "http://localhost:8080")
FLEET_JWT_SECRET = os.environ.get("FLEET_JWT_SECRET", "fleet-secret")

def fleet_token() -> str:
    """Generate an internal service JWT accepted by Fleet Manager."""
    payload = {
        "id":    "advance-dispatch-service",
        "email": "system@advance-dispatch",
        "role":  "admin",
        "name":  "Advance Dispatch",
    }
    return pyjwt.encode(payload, FLEET_JWT_SECRET, algorithm="HS256")

def fleet_get(path: str, params: dict = None):
    """GET from Fleet Manager API, returns parsed JSON data field."""
    headers = {"Authorization": f"Bearer {fleet_token()}"}
    r = requests.get(f"{FLEET_BASE}{path}", headers=headers, params=params, timeout=10)
    r.raise_for_status()
    body = r.json()
    return body.get("data", body)

# ── VISITOUR connection ───────────────────────────────────────────────────────
# Set VT_ENV=LIVE to use the production environment, otherwise TEST is used.
_VT_ENV = os.environ.get("VT_ENV", "TEST")

if _VT_ENV == "LIVE":
    VT_USER = os.environ.get("VT_USER", "INT.PROD")
    VT_PASS = os.environ.get("VT_PASS", "Programs-fitted-lengths")
    VT_BASE = "https://advgroup.vt-fls.com/VTS/WS"
else:
    VT_USER = os.environ.get("VT_USER", "INT.TEST")
    VT_PASS = os.environ.get("VT_PASS", "Taking-rach-robbers")
    VT_BASE = "https://advgroup-test.vt-fls.com/VTS/WS"

# WSDL: https://advgroup.vt-fls.com/wsdl  (live)
#       https://advgroup-test.vt-fls.com/wsdl  (test)

def vt_session():
    s = requests.Session()
    s.auth = HTTPBasicAuth(VT_USER, VT_PASS)
    return s

# ── Engineer master data (from our confirmed VISITOUR ID mapping) ─────────────
# Augmented with config we've pushed (capacity, radii).
ENGINEERS = [
    {"id": "487",  "firstName": "Tony",         "lastName": "Reid",             "fmExtId": "487"},
    {"id": "858",  "firstName": "Aristotelis",   "lastName": "Goudelis",         "fmExtId": "858"},
    {"id": "689",  "firstName": "Carl",          "lastName": "Mills",            "fmExtId": "689"},
    {"id": "802",  "firstName": "Charles",       "lastName": "Tidey",            "fmExtId": "802"},
    {"id": "240",  "firstName": "Chris",         "lastName": "Amor",             "fmExtId": "240"},
    {"id": "348",  "firstName": "Franc",         "lastName": "Genovese",         "fmExtId": "348"},
    {"id": "926",  "firstName": "Gareth",        "lastName": "Terrell",          "fmExtId": "926"},
    {"id": "501",  "firstName": "Gary",          "lastName": "Cant",             "fmExtId": "501"},
    {"id": "776",  "firstName": "Hossein",       "lastName": "Soltani-Tehrani",  "fmExtId": "776"},
    {"id": "773",  "firstName": "Ian",           "lastName": "Scott",            "fmExtId": "773"},
    {"id": "690",  "firstName": "Jack",          "lastName": "Eagle",            "fmExtId": "690"},
    {"id": "233",  "firstName": "Lee",           "lastName": "Reynolds",         "fmExtId": "233"},
    {"id": "800",  "firstName": "Louis",         "lastName": "Holman",           "fmExtId": "800"},
    {"id": "952",  "firstName": "Mark",          "lastName": "Wilson",           "fmExtId": "952"},
    {"id": "711",  "firstName": "Michael",       "lastName": "Mutirwara",        "fmExtId": "711"},
    {"id": "855",  "firstName": "Mustafa",       "lastName": "Raza",             "fmExtId": "855"},
    {"id": "820",  "firstName": "Nick",          "lastName": "Green",            "fmExtId": "820"},
    {"id": "405",  "firstName": "Nigel",         "lastName": "Lomax",            "fmExtId": "405"},
    {"id": "808",  "firstName": "Paul",          "lastName": "Holman",           "fmExtId": "808"},
    {"id": "982",  "firstName": "Rhys",          "lastName": "Standing",         "fmExtId": "982"},
    {"id": "239",  "firstName": "Ricky",         "lastName": "Parrett",          "fmExtId": "239"},
    {"id": "799",  "firstName": "Rob",           "lastName": "Carlisle",         "fmExtId": "799"},
    {"id": "378",  "firstName": "Mark",          "lastName": "Holmes",           "fmExtId": "378"},
    {"id": "723",  "firstName": "Roy",           "lastName": "Aris",             "fmExtId": "723"},
    {"id": "857",  "firstName": "Ryan",          "lastName": "Mongiovi",         "fmExtId": "857"},
    {"id": "681",  "firstName": "Scott",         "lastName": "Morgan",           "fmExtId": "681"},
    {"id": "308",  "firstName": "Sean",          "lastName": "Craig",            "fmExtId": "308"},
    {"id": "676",  "firstName": "Shane",         "lastName": "Sheppard",         "fmExtId": "676"},
    {"id": "844",  "firstName": "Stephen",       "lastName": "Martin",           "fmExtId": "844"},
    {"id": "884",  "firstName": "Terry",         "lastName": "Jones",            "fmExtId": "884"},
    {"id": "696",  "firstName": "Trymore",       "lastName": "Mavhangira",       "fmExtId": "696"},
    {"id": "731",  "firstName": "Umit",          "lastName": "Salah",            "fmExtId": "731"},
    {"id": "761",  "firstName": "Vincent",       "lastName": "Magombe",          "fmExtId": "761"},
    {"id": "694",  "firstName": "Wes",           "lastName": "Mwashaireni",      "fmExtId": "694"},
    {"id": "10009","firstName": "Derek",         "lastName": "Fisher",           "fmExtId": "10009"},
]

# FMExtID → engineer name lookup
FM_TO_NAME = {e["fmExtId"]: f"{e['firstName']} {e['lastName']}" for e in ENGINEERS}

# name (lowercase) → FMExtID reverse lookup
NAME_TO_FM = {f"{e['firstName']} {e['lastName']}".lower(): e["fmExtId"] for e in ENGINEERS}

# ── VISITOUR SOAP helpers ─────────────────────────────────────────────────────

def parse_xml_tag(xml: str, tag: str) -> str:
    """Extract text content of first matching XML tag."""
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
    return m.group(1).strip() if m else ""

def parse_xml_all(xml: str, tag: str):
    """Find all occurrences of a tag and return their inner XML."""
    return re.findall(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)

def call_get_schedule(date_from: str, date_to: str = None, state_from: int = 1, state_to: int = 6):
    """
    Call VISITOUR GetSchedule for a date range.
    VISITOUR's FromDate/ToDate filters by LastUpdate timestamp, not tour date.
    We use a 60-day lookback window to catch all active calls, then filter
    results by the <Date> field (actual tour date) to match the requested range.
    Returns list of ScheduledCall dicts.
    """
    if not date_to:
        date_to = date_from

    # Wide lookback so we catch calls updated anytime in the last 60 days
    lookback = (date.fromisoformat(date_from) - timedelta(days=60)).isoformat()

    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<GetSchedule>
  <FromDate>{lookback}T00:00:00</FromDate>
  <ToDate>{date_to}T23:59:59</ToDate>
  <StateFrom>{state_from}</StateFrom>
  <StateTo>{state_to}</StateTo>
  <SchedulingRelevantChanges>true</SchedulingRelevantChanges>
  <RelevanceType>1</RelevanceType>
</GetSchedule>"""

    session = vt_session()
    r = session.post(
        f"{VT_BASE}/GetSchedule",
        headers={"Content-Type": "text/xml; charset=utf-8"},
        data=xml_body.encode("utf-8"),
        timeout=30,
    )
    r.raise_for_status()

    # Parse ScheduledCall blocks (strip namespace declarations first)
    xml_text = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', '', r.text)
    calls = []
    blocks = parse_xml_all(xml_text, "ScheduledCall")
    for block in blocks:
        fm_ext_id  = parse_xml_tag(block, "FMExtID")
        lat_raw    = parse_xml_tag(block, "Y")   # WGS84 * 100000
        lon_raw    = parse_xml_tag(block, "X")   # WGS84 * 100000
        state_map  = {"1": "open", "2": "confirmed", "3": "fixed",
                      "4": "on_route", "5": "arrival", "6": "complete"}
        state_code = parse_xml_tag(block, "State")

        # <Date> is the actual tour date e.g. "2026-09-25T00:00:00+01:00"
        tour_date_raw = parse_xml_tag(block, "Date")
        tour_date     = tour_date_raw[:10] if tour_date_raw else ""

        # Filter to only calls whose tour date falls within the requested range
        if tour_date and not (date_from <= tour_date <= date_to):
            continue

        call = {
            "id":                parse_xml_tag(block, "ExtID") or parse_xml_tag(block, "VTID"),
            "vtid":              parse_xml_tag(block, "VTID"),
            "customerName":      parse_xml_tag(block, "Name"),
            "customerName2":     parse_xml_tag(block, "Name2"),
            "address":           ", ".join(filter(None, [
                                     parse_xml_tag(block, "Street"),
                                     parse_xml_tag(block, "City"),
                                     parse_xml_tag(block, "ZIP"),
                                 ])),
            "scheduledDate":     tour_date,
            "arrival":           parse_xml_tag(block, "Arrival"),
            "estimatedDuration": int(parse_xml_tag(block, "Duration") or 0),
            "drivingTime":       int(parse_xml_tag(block, "DrivingTime") or 0),
            "distanceM":         int(parse_xml_tag(block, "Distance") or 0),
            "status":            state_map.get(state_code, "open"),
            "statusCode":        state_code,
            "fmExtId":           fm_ext_id,
            "engineer":          FM_TO_NAME.get(fm_ext_id, fm_ext_id or "Unassigned"),
            "sequence":          int(parse_xml_tag(block, "Sequence") or 0),
            "fixed":             parse_xml_tag(block, "Fixed") == "true",
            "lat":               float(lat_raw) / 100000 if lat_raw else None,
            "lon":               float(lon_raw) / 100000 if lon_raw else None,
            "callInfo1":         parse_xml_tag(block, "CallInfo1"),
            "callInfo2":         parse_xml_tag(block, "CallInfo2"),
            "serviceType":       parse_xml_tag(block, "ServiceType"),
            "skills":            parse_xml_tag(block, "Skills"),
            "orderType":         parse_xml_tag(block, "OrderType"),
            "equipmentName":     parse_xml_tag(block, "EquipmentName"),
            "phone":             parse_xml_tag(block, "Phone1"),
            "contactPerson":     parse_xml_tag(block, "ContactPerson"),
        }
        calls.append(call)

    return calls


# ── Engineer config (persisted to JSON, editable via API) ────────────────────
import json, pathlib

ENG_CONFIG_PATH = pathlib.Path(os.environ.get("ENG_CONFIG_PATH", "/root/engineer_config.json"))

# Seed data — used only when no config file exists yet.
# Postcodes geocoded via postcodes.io; hours from Areas tab of Engineer Details & Skills.xlsx.
_ENG_CONFIG_SEED = {
  "Tony Reid":               {"fmExtId":"487","department":"Catering","qualification":"Gas","area":"West Midlands","postcode":"B76 1DY","lat":52.52910,"lon":-1.79682,"address":"67 Bonner Drive, Sutton Coldfield, West Midlands, B76 1DY","shiftStart":"07:00","shiftEnd":"15:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Aristotelis Goudelis":    {"fmExtId":"858","department":"Apprentice","qualification":"-","area":"West Midlands","postcode":"WS13 8LB","lat":52.68895,"lon":-1.79614,"address":"20 Bexmore Drive, Lichfield, WS13 8LB","shiftStart":"07:00","shiftEnd":"15:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Carl Mills":              {"fmExtId":"689","department":"Cooling","qualification":"FGAS","area":"East Midlands","postcode":"DN21 1UL","lat":53.39424,"lon":-0.75982,"address":"49 Aisby Walk, Gainsborough, Lincolnshire, DN21 1UL","shiftStart":"08:00","shiftEnd":"16:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":80,"vtMaxDrive":200},
  "Charles Tidey":           {"fmExtId":"802","department":"Catering","qualification":"Gas","area":"South East & London","postcode":"ME20 6BG","lat":51.29894,"lon":0.44306,"address":"720 London Road, Larkfield, Kent, ME20 6BG","shiftStart":"06:30","shiftEnd":"14:30","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Chris Amor":              {"fmExtId":"240","department":"Cooling","qualification":"FGAS","area":"South West","postcode":"SN4 0DU","lat":51.52991,"lon":-1.66848,"address":"6 Ridgeway Cottages, Foxhill, Wiltshire, SN4 0DU","shiftStart":"08:00","shiftEnd":"17:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":100,"vtMaxDrive":200},
  "Franc Genovese":          {"fmExtId":"348","department":"Catering","qualification":"Electric","area":"Midlands","postcode":"MK45 3AW","lat":52.09383,"lon":-0.41558,"address":"35A Wood Lane, Cotton End, Beds, MK45 3AW","shiftStart":"06:00","shiftEnd":"14:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Gareth Terrell":          {"fmExtId":"926","department":"Cooling","qualification":"FGAS","area":"South East & London","postcode":"SS2 6QX","lat":51.56303,"lon":0.70044,"address":"33 Derek Gardens, Southend, SS2 6QX","shiftStart":"06:00","shiftEnd":"14:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Gary Cant":               {"fmExtId":"501","department":"Catering","qualification":"Gas","area":"East Anglia","postcode":"PE34 3PZ","lat":52.62150,"lon":0.38909,"address":"24 West Way, Wimbotsham, Kings Lynn, PE34 3PZ","shiftStart":"08:00","shiftEnd":"16:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Hossein Soltani-Tehrani": {"fmExtId":"776","department":"Cooling","qualification":"FGAS","area":"London","postcode":"CR8 1DX","lat":51.33771,"lon":-0.10937,"address":"Flat 2 Loxwood House, Purley Hill, Purley, CR8 1DX","shiftStart":"08:00","shiftEnd":"16:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Ian Scott":               {"fmExtId":"773","department":"Catering","qualification":"Gas","area":"North","postcode":"NE13 6LE","lat":55.04416,"lon":-1.61945,"address":"12 Dunnock Place, Wideopen, Newcastle, NE13 6LE","shiftStart":"07:00","shiftEnd":"15:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":83,"vtMaxDrive":200},
  "Jack Eagle":              {"fmExtId":"690","department":"Cooling","qualification":"FGAS","area":"South East & London","postcode":"ME5 9HP","lat":51.33292,"lon":0.51954,"address":"63 Catkin Close, Chatham, Kent, ME5 9HP","shiftStart":"07:00","shiftEnd":"15:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Lee Reynolds":            {"fmExtId":"233","department":"Catering","qualification":"Gas","area":"Midlands","postcode":"NG10 3DD","lat":52.87968,"lon":-1.29004,"address":"32 Lock Lane, Sawley, Long Eaton, Notts, NG10 3DD","shiftStart":"05:30","shiftEnd":"13:30","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Louis Holman":            {"fmExtId":"800","department":"Catering","qualification":"Electric","area":"South","postcode":"DT10 2DX","lat":50.88458,"lon":-2.35578,"address":"12 The Green, Kingston, Sturminster Newton, Dorset, DT10 2DX","shiftStart":"07:30","shiftEnd":"15:30","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Mark Holmes":             {"fmExtId":"378","department":"Catering","qualification":"Gas","area":"North","postcode":"S26 6PQ","lat":53.34010,"lon":-1.25326,"address":"17 Osbourne Road, Kiveton Park, Sheffield, S26 6PQ","shiftStart":"06:00","shiftEnd":"14:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":72,"vtMaxDrive":200},
  "Mark Wilson":             {"fmExtId":"952","department":"Catering","qualification":"Gas","area":"South East & London","postcode":"DA15 9AQ","lat":51.43545,"lon":0.11063,"address":"125 Hurst Road, Sidcup, Kent, DA15 9AQ","shiftStart":"09:00","shiftEnd":"17:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Michael Mutirwara":       {"fmExtId":"711","department":"Cooling","qualification":"FGAS","area":"West Midlands","postcode":"B24 9AE","lat":52.52088,"lon":-1.84189,"address":"27 Springhill, Erdington, B24 9AE","shiftStart":"09:00","shiftEnd":"17:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Mustafa Raza":            {"fmExtId":"855","department":"Apprentice","qualification":"-","area":"North West","postcode":"OL12 9BD","lat":53.62469,"lon":-2.14373,"address":"29 Halifax Road, Rochdale, OL12 9BD","shiftStart":"07:00","shiftEnd":"15:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Nick Green":              {"fmExtId":"820","department":"Catering","qualification":"Gas","area":"South West","postcode":"BS35 2DE","lat":51.60540,"lon":-2.51673,"address":"88 Hamble Close, Thornbury, Bristol, BS35 2DE","shiftStart":"06:30","shiftEnd":"14:30","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Nigel Lomax":             {"fmExtId":"405","department":"Catering","qualification":"Gas","area":"North West","postcode":"M34 7TW","lat":53.44844,"lon":-2.10054,"address":"3 Silverdale Avenue, Denton, Manchester, M34 7TW","shiftStart":"07:00","shiftEnd":"15:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Paul Holman":             {"fmExtId":"808","department":"Catering","qualification":"Gas","area":"South","postcode":"DT11 8DZ","lat":50.91218,"lon":-2.24244,"address":"23 Greenway, Blandford Forum, Child Okeford, Dorset, DT11 8DZ","shiftStart":"06:00","shiftEnd":"14:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Rhys Standing":           {"fmExtId":"982","department":"Catering","qualification":"Gas","area":"South East & London","postcode":"BN8 4HD","lat":50.97203,"lon":-0.01701,"address":"Gokkul, Station Road, North Chailey, BN8 4HD","shiftStart":"06:30","shiftEnd":"14:30","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Ricky Parrett":           {"fmExtId":"239","department":"Catering","qualification":"Gas","area":"London","postcode":"SG1 6GY","lat":51.93259,"lon":-0.17852,"address":"Mendip Way, Stevenage, SG1 6GY","shiftStart":"05:00","shiftEnd":"13:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Rob Carlisle":            {"fmExtId":"799","department":"Cooling","qualification":"FGAS","area":"South","postcode":"PO12 4BY","lat":50.81225,"lon":-1.15348,"address":"59 Hastings Avenue, Gosport, Hampshire, PO12 4BY","shiftStart":"08:30","shiftEnd":"16:30","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Roy Aris":                {"fmExtId":"723","department":"Cooling","qualification":"FGAS","area":"Midlands","postcode":"OX5 1TF","lat":51.80586,"lon":-1.30700,"address":"28 The Paddocks, Yarnton, Oxford, OX5 1TF","shiftStart":"07:30","shiftEnd":"15:30","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":50,"vtMaxDrive":150},
  "Scott Morgan":            {"fmExtId":"681","department":"Catering","qualification":"Gas","area":"North","postcode":"","lat":None,"lon":None,"address":"","shiftStart":"08:00","shiftEnd":"16:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Sean Craig":              {"fmExtId":"308","department":"Catering","qualification":"Gas","area":"London","postcode":"LU3 3HE","lat":51.91982,"lon":-0.46754,"address":"88 Grampian Way, Sundon Park, Luton, LU3 3HE","shiftStart":"05:30","shiftEnd":"13:30","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Shane Sheppard":          {"fmExtId":"676","department":"Catering","qualification":"Electric","area":"South","postcode":"RH7 6BQ","lat":51.18281,"lon":-0.02482,"address":"7 Ray Close, Lingfield, Surrey, RH7 6BQ","shiftStart":"09:00","shiftEnd":"17:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Stephen Martin":          {"fmExtId":"844","department":"Catering","qualification":"Gas","area":"North West","postcode":"ST3 7RR","lat":52.96778,"lon":-2.08706,"address":"7 Monyash Close, Meir Park, Stoke, ST3 7RR","shiftStart":"07:00","shiftEnd":"15:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Terry Jones":             {"fmExtId":"884","department":"Catering","qualification":"Gas","area":"Midlands","postcode":"NN8 2JX","lat":52.29434,"lon":-0.70164,"address":"136 Priory Rd, Wellingborough, Northamptonshire, NN8 2JX","shiftStart":"05:00","shiftEnd":"13:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Trymore Mavhangira":      {"fmExtId":"696","department":"Cooling","qualification":"FGAS","area":"London","postcode":"AL2 2NA","lat":51.72261,"lon":-0.34046,"address":"14 Oliver Close, Park Street, St Albans, AL2 2NA","shiftStart":"09:00","shiftEnd":"17:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Umit Salah":              {"fmExtId":"731","department":"Catering","qualification":"Gas","area":"","postcode":"","lat":None,"lon":None,"address":"","shiftStart":"08:00","shiftEnd":"16:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Vincent Magombe":         {"fmExtId":"761","department":"Cooling","qualification":"FGAS","area":"North","postcode":"M40 2NG","lat":53.49381,"lon":-2.18185,"address":"Flat 27 Lancaster Court, Croydon Drive, Newton Heath, M40 2NG","shiftStart":"08:00","shiftEnd":"16:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Wes Mwashaireni":         {"fmExtId":"694","department":"Cooling","qualification":"FGAS","area":"Midlands","postcode":"LU5 4EJ","lat":51.87787,"lon":-0.50246,"address":"19 Brive Road, Dunstable, LU5 4EJ","shiftStart":"09:00","shiftEnd":"17:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Derek Fisher":            {"fmExtId":"10009","department":"Catering","qualification":"Electric","area":"South","postcode":"GU12 4PS","lat":51.24800,"lon":-0.76300,"address":"Haig Road, Aldershot, Hampshire, GU12 4PS","shiftStart":"09:00","shiftEnd":"17:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
  "Ryan Mongiovi":           {"fmExtId":"857","department":"Apprentice","qualification":"-","area":"Midlands","postcode":"MK42 7RQ","lat":52.11134,"lon":-0.48715,"address":"1 Spruce Walk, Kempston, Bedford, MK42 7RQ","shiftStart":"07:00","shiftEnd":"15:00","travelRadius":25,"mobile":"","vehicle":"","notes":"","vtCapacity":50,"vtCapacity2":0,"vtSpeedPct":100,"vtWorkPct":100,"vtOvertime":0,"vtMinRadius":0,"vtMaxRadius":62,"vtMaxDrive":150},
}

def _load_eng_config() -> dict:
    """Load engineer config from JSON file, falling back to seed data."""
    if ENG_CONFIG_PATH.exists():
        try:
            return json.loads(ENG_CONFIG_PATH.read_text())
        except Exception:
            pass
    return dict(_ENG_CONFIG_SEED)

def _save_eng_config(cfg: dict):
    ENG_CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# In-memory cache — reloaded on each GET so server restart always reads file
_eng_config: dict = _load_eng_config()

def _geocode_postcode(postcode: str):
    """Geocode a UK postcode via postcodes.io. Returns (lat, lon) or (None, None)."""
    if not postcode:
        return None, None
    pc = postcode.replace(" ", "").upper()
    try:
        r = requests.get(f"https://api.postcodes.io/postcodes/{pc}", timeout=8)
        if r.ok:
            result = r.json().get("result") or {}
            return result.get("latitude"), result.get("longitude")
    except Exception:
        pass
    return None, None

def _push_vt_field_manager(fm_ext_id: str, cfg: dict) -> bool:
    """Push FieldManager config for one engineer to VISITOUR."""
    def mi_to_km(mi): return round(float(mi) / 0.621371)
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FieldManager>
  <FMExtID>{fm_ext_id}</FMExtID>
  <Capacity>{cfg.get('vtCapacity',50)}</Capacity>
  <Capacity2>{cfg.get('vtCapacity2',0)}</Capacity2>
  <SpeedPercent>{cfg.get('vtSpeedPct',100)}</SpeedPercent>
  <WorkPercent>{cfg.get('vtWorkPct',100)}</WorkPercent>
  <Overtime>{cfg.get('vtOvertime',0)}</Overtime>
  <MinDeployableRadius>{mi_to_km(cfg.get('vtMinRadius',0))}</MinDeployableRadius>
  <MaxDeployableRadius>{mi_to_km(cfg.get('vtMaxRadius',62))}</MaxDeployableRadius>
  <MaxDrivingDistance>{mi_to_km(cfg.get('vtMaxDrive',150))}</MaxDrivingDistance>
</FieldManager>"""
    try:
        r = vt_session().post(
            f"{VT_BASE}/FieldManager",
            headers={"Content-Type": "text/xml; charset=utf-8"},
            data=xml.encode("utf-8"),
            timeout=20,
        )
        m = re.search(r"<FieldManagerResult>(\d+)</FieldManagerResult>", r.text)
        if not m:
            m = re.search(r"<return>(-?\d+)</return>", r.text)
        return m and int(m.group(1)) in (0, 10000)
    except Exception:
        return False


# ── Sync-notify state (set by Fleet Manager after each BrightHR sync) ─────────
_last_sync_ts: str | None = None


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "advance-dispatch"})


@app.get("/api/sync-notify")
def get_sync_notify():
    """Dispatch frontend polls this to know when Fleet Manager last synced BrightHR."""
    return jsonify({"lastSync": _last_sync_ts})


@app.post("/api/sync-notify")
def post_sync_notify():
    """Called by brighthr_sync_server.py on the server after each sync completes."""
    global _last_sync_ts
    from datetime import datetime, timezone
    _last_sync_ts = datetime.now(timezone.utc).isoformat()
    return jsonify({"ok": True, "lastSync": _last_sync_ts})


@app.get("/api/engineer-config")
def get_engineer_config():
    """Return full engineer config (merged from file + seed)."""
    global _eng_config
    _eng_config = _load_eng_config()
    return jsonify(_eng_config)


@app.patch("/api/engineer-config/<name>")
def patch_engineer_config(name: str):
    """
    Update one engineer's config. Automatically:
    - Re-geocodes if postcode changed
    - Pushes to VISITOUR FieldManager if any vt* field changed
    """
    global _eng_config
    _eng_config = _load_eng_config()

    if name not in _eng_config:
        return jsonify({"error": f"Engineer '{name}' not found"}), 404

    payload = request.get_json(force=True) or {}
    current = _eng_config[name]

    # Detect changes
    vt_fields = {"vtCapacity","vtCapacity2","vtSpeedPct","vtWorkPct","vtOvertime","vtMinRadius","vtMaxRadius","vtMaxDrive"}
    vt_changed = any(k in payload and payload[k] != current.get(k) for k in vt_fields)
    pc_changed  = "postcode" in payload and payload["postcode"].replace(" ","").upper() != (current.get("postcode","") or "").replace(" ","").upper()

    # Merge update
    current.update(payload)

    # Re-geocode if postcode changed
    if pc_changed and current.get("postcode"):
        lat, lon = _geocode_postcode(current["postcode"])
        if lat:
            current["lat"], current["lon"] = lat, lon

    _eng_config[name] = current
    _save_eng_config(_eng_config)

    # Push to VISITOUR if FieldManager fields changed and engineer has an FMExtID
    vt_result = None
    if vt_changed and current.get("fmExtId"):
        ok = _push_vt_field_manager(current["fmExtId"], current)
        vt_result = "pushed" if ok else "push_failed"

    return jsonify({"ok": True, "engineer": name, "data": current, "visitour": vt_result})


@app.get("/api/engineers")
def get_engineers():
    """
    Return engineers from Fleet Manager, enriched with VISITOUR FMExtID.
    Falls back to the hardcoded list if Fleet Manager is unreachable.
    """
    # Return all 32 VISITOUR engineers immediately — fast, no external calls
    return jsonify([
        {
            "id":        e["fmExtId"],
            "name":      f"{e['firstName']} {e['lastName']}",
            "firstName": e["firstName"],
            "lastName":  e["lastName"],
            "email":     "",
            "isActive":  True,
            "active":    True,
            "fmExtId":   e["fmExtId"],
        }
        for e in ENGINEERS
    ])


@app.get("/api/absences")
def get_absences():
    """
    GET /api/absences?date=YYYY-MM-DD[&months=3]
    Returns absences from Fleet Manager (BrightHR-synced) as a map of
    engineer name → [date strings] for use by the dispatch frontend.
    """
    date_str = request.args.get("date", date.today().isoformat())
    months   = int(request.args.get("months", 3))

    try:
        ref_date  = date.fromisoformat(date_str)
        # Collect absences across the requested months
        all_absences = {}

        for m in range(months):
            total_month = ref_date.month - 1 + m
            target = date(ref_date.year + total_month // 12, total_month % 12 + 1, 1)
            rows = fleet_get("/api/absences", {"year": target.year, "month": target.month})

            for row in rows:
                if row.get("status") == "cancelled":
                    continue
                eng    = row.get("engineer", {})
                name   = f"{eng.get('firstName','')} {eng.get('lastName','')}".strip()
                if not name:
                    continue

                start = date.fromisoformat(str(row["startDate"])[:10])
                end   = date.fromisoformat(str(row["endDate"])[:10])

                # Expand date range — preserve absence type per date
                eng_map = all_absences.setdefault(name, {})
                absence_type = row.get("absenceType", "AnnualLeave")
                d = start
                while d <= end:
                    ds = d.isoformat()
                    # Active absences take priority over cancelled
                    if ds not in eng_map:
                        eng_map[ds] = absence_type
                    d += timedelta(days=1)

        return jsonify(all_absences)

    except Exception as e:
        app.logger.warning(f"Could not fetch absences from Fleet Manager: {e}")
        return jsonify({})


@app.get("/api/schedule")
def get_schedule():
    """
    GET /api/schedule?date=YYYY-MM-DD[&to=YYYY-MM-DD][&state_from=1&state_to=6]
    Returns scheduled calls from VISITOUR for the given date (or range).
    """
    date_from  = request.args.get("date", date.today().isoformat())
    date_to    = request.args.get("to",   date_from)
    state_from = int(request.args.get("state_from", 1))
    state_to   = int(request.args.get("state_to",   6))

    try:
        calls = call_get_schedule(date_from, date_to, state_from, state_to)
        return jsonify({
            "date":       date_from,
            "dateTo":     date_to,
            "totalCalls": len(calls),
            "calls":      calls,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/schedule/week")
def get_schedule_week():
    """Return this week's schedule (Mon–Fri)."""
    today      = date.today()
    monday     = today - timedelta(days=today.weekday())
    friday     = monday + timedelta(days=4)
    try:
        calls = call_get_schedule(monday.isoformat(), friday.isoformat())
        return jsonify({
            "weekStart":  monday.isoformat(),
            "weekEnd":    friday.isoformat(),
            "totalCalls": len(calls),
            "calls":      calls,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/debug/engineers")
def debug_engineers():
    """Shows BrightHR employees that didn't match a VISITOUR ID, for name-matching diagnosis."""
    try:
        bhr_engs = brighthr_engineers()
        unmatched, matched = [], []
        for e in bhr_engs:
            first    = e.get("firstName", "")
            last     = e.get("lastName", "")
            name_key = f"{first} {last}".lower()
            fm_id    = NAME_TO_FM.get(name_key, "")
            entry    = {"brighthrName": f"{first} {last}", "nameKey": name_key}
            if fm_id:
                matched.append({**entry, "fmExtId": fm_id})
            else:
                unmatched.append(entry)
        # Also show VISITOUR names not in BrightHR
        bhr_keys = {f"{e.get('firstName','')} {e.get('lastName','')}".lower() for e in bhr_engs}
        not_in_bhr = [{"visitourName": n, "fmExtId": fid}
                      for n, fid in NAME_TO_FM.items() if n not in bhr_keys]
        return jsonify({"matched": len(matched), "unmatched": unmatched, "notInBrightHR": not_in_bhr})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def call_get_field_managers():
    """
    Call VISITOUR GetFieldManagers to retrieve all engineer (FieldManager) records.
    Returns list of dicts with fmExtId, name, capacity, radius, skills etc.
    """
    xml_body = """<?xml version="1.0" encoding="utf-8"?>
<GetFieldManagers>
  <SubcontractorOnly>false</SubcontractorOnly>
</GetFieldManagers>"""

    session = vt_session()
    r = session.post(
        f"{VT_BASE}/GetFieldManagers",
        headers={"Content-Type": "text/xml; charset=utf-8"},
        data=xml_body.encode("utf-8"),
        timeout=30,
    )
    r.raise_for_status()

    xml_text = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', '', r.text)
    managers = []

    # Try <FieldManager> blocks first, fall back to <Resource> blocks
    blocks = parse_xml_all(xml_text, "FieldManager") or parse_xml_all(xml_text, "Resource")
    for block in blocks:
        fm_ext_id = parse_xml_tag(block, "FMExtID") or parse_xml_tag(block, "ExtID")
        if not fm_ext_id:
            continue

        # Skills: may be comma-separated string or repeated <Skill> tags
        skills_str = parse_xml_tag(block, "Skills") or ""
        skills_list = parse_xml_all(block, "Skill")
        if skills_list:
            skills = [s.strip() for s in skills_list if s.strip()]
        else:
            skills = [s.strip() for s in skills_str.split(",") if s.strip()]

        def km_to_mi(km_str):
            try:
                return round(float(km_str) * 0.621371)
            except (ValueError, TypeError):
                return None

        managers.append({
            "fmExtId":       fm_ext_id,
            "firstName":     parse_xml_tag(block, "FirstName") or parse_xml_tag(block, "Name"),
            "lastName":      parse_xml_tag(block, "LastName") or "",
            "capacity":      int(parse_xml_tag(block, "Capacity") or 0),
            "capacity2":     int(parse_xml_tag(block, "Capacity2") or 0),
            "speedPct":      int(parse_xml_tag(block, "SpeedPercent") or 100),
            "workPct":       int(parse_xml_tag(block, "WorkPercent") or 100),
            "overtime":      int(parse_xml_tag(block, "Overtime") or 0),
            "minRadiusMi":   km_to_mi(parse_xml_tag(block, "MinDeployableRadius")),
            "maxRadiusMi":   km_to_mi(parse_xml_tag(block, "MaxDeployableRadius")),
            "maxDriveMi":    km_to_mi(parse_xml_tag(block, "MaxDrivingDistance")),
            "skills":        skills,
        })
    return managers


@app.post("/api/sync-visitour")
def sync_visitour():
    """
    Pull FieldManager data (capacity, radius, skills) from VISITOUR and merge
    into the local engineer config. Only updates fields that VISITOUR returns;
    shift times, postcodes etc are left untouched.
    """
    global _eng_config
    _eng_config = _load_eng_config()

    try:
        managers = call_get_field_managers()
    except Exception as e:
        return jsonify({"error": f"VISITOUR GetFieldManagers failed: {e}"}), 502

    # Build reverse lookup: fmExtId → engineer name
    fm_to_name = {v.get("fmExtId"): k for k, v in _eng_config.items() if v.get("fmExtId")}

    updated, skipped = [], []
    for mgr in managers:
        fm_id = mgr["fmExtId"]
        name  = fm_to_name.get(fm_id)
        if not name:
            skipped.append({"fmExtId": fm_id, "reason": "not in local config"})
            continue

        patch = {}
        if mgr["capacity"] is not None:
            patch["vtCapacity"] = mgr["capacity"]
        if mgr["capacity2"] is not None:
            patch["vtCapacity2"] = mgr["capacity2"]
        if mgr["speedPct"] is not None:
            patch["vtSpeedPct"] = mgr["speedPct"]
        if mgr["workPct"] is not None:
            patch["vtWorkPct"] = mgr["workPct"]
        if mgr["overtime"] is not None:
            patch["vtOvertime"] = mgr["overtime"]
        if mgr["minRadiusMi"] is not None:
            patch["vtMinRadius"] = mgr["minRadiusMi"]
        if mgr["maxRadiusMi"] is not None:
            patch["vtMaxRadius"] = mgr["maxRadiusMi"]
        if mgr["maxDriveMi"] is not None:
            patch["vtMaxDrive"] = mgr["maxDriveMi"]
        if mgr["skills"]:
            patch["vtSkills"] = mgr["skills"]

        if patch:
            _eng_config[name].update(patch)
            updated.append({"name": name, "fmExtId": fm_id, "fields": list(patch.keys())})

    if updated:
        _save_eng_config(_eng_config)

    return jsonify({
        "ok":      True,
        "updated": len(updated),
        "skipped": len(skipped),
        "details": updated,
        "skippedDetails": skipped,
    })


@app.get("/api/debug/schedule")
def debug_schedule():
    """Returns raw VISITOUR XML response for diagnosis."""
    date_from = request.args.get("date", date.today().isoformat())
    date_to   = request.args.get("to", date_from)
    state_from = int(request.args.get("state_from", 0))
    state_to   = int(request.args.get("state_to", 9))

    lookback = (date.fromisoformat(date_from) - timedelta(days=60)).isoformat()
    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<GetSchedule>
  <FromDate>{lookback}T00:00:00</FromDate>
  <ToDate>{date_to}T23:59:59</ToDate>
  <StateFrom>{state_from}</StateFrom>
  <StateTo>{state_to}</StateTo>
  <SchedulingRelevantChanges>true</SchedulingRelevantChanges>
  <RelevanceType>1</RelevanceType>
</GetSchedule>"""

    try:
        session = vt_session()
        r = session.post(
            f"{VT_BASE}/GetSchedule",
            headers={"Content-Type": "text/xml; charset=utf-8"},
            data=xml_body.encode("utf-8"),
            timeout=30,
        )
        return app.response_class(r.text, mimetype="text/xml", status=r.status_code)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Supabase connection ───────────────────────────────────────────────────────
import math

SB_URL  = os.environ.get("SUPABASE_URL",  "https://ehuhqzjnikvykldasygc.supabase.co")
SB_KEY  = os.environ.get("SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVodWhxempuaWt2eWtsZGFzeWdjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc5OTc3NzEsImV4cCI6MjEwMzU3Mzc3MX0.Kv7ko_u34u6ZTTU2QU50UULpG0bOX6jyOsA8-ry9ltU")
SB_HDR  = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
           "Content-Type": "application/json", "Prefer": "return=minimal"}

def sb_get(path: str, params: str = "") -> list:
    url = f"{SB_URL}/rest/v1/{path}{('?' + params) if params else ''}"
    r = requests.get(url, headers=SB_HDR, timeout=15)
    r.raise_for_status()
    return r.json()

def sb_patch(path: str, params: str, body: dict) -> bool:
    url = f"{SB_URL}/rest/v1/{path}?{params}"
    r = requests.patch(url, headers=SB_HDR, json=body, timeout=15)
    return r.ok


# ── Scheduling algorithm ──────────────────────────────────────────────────────

WORK_START     = 480   # 08:00 in minutes
WORK_END       = 1020  # 17:00 in minutes
JOB_DURATION   = 60    # minutes (default)
SPEED_KMH      = 48.28 # average road speed
SCOTLAND_LAT   = 55.0  # flag likely data-quality jobs above this latitude
MAX_KM         = 200   # skip engineer if further than this from job


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a  = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _travel_mins(km: float) -> int:
    return int((km / SPEED_KMH) * 60)


def _time_to_min(t: str) -> int:
    """'08:30' → 510"""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _run_scheduler(jobs: list, engineers: list, eng_skills: dict,
                   absences: dict, existing: list) -> dict:
    """
    Greedy scheduler.  Returns {"assignments": [...], "unschedulable": [...]}.
    Each assignment: {id, engineer_name, scheduled_time}.
    """
    # Build per-engineer-per-day busy slots from already-scheduled jobs.
    # busy[eng_name][date_str] = list of (start_min, end_min)
    busy: dict = {}
    for call in existing:
        eng_name = call.get("engineer_name") or ""
        st       = call.get("scheduled_time") or ""
        if not eng_name or not st:
            continue
        ds   = st[:10]
        hhmm = st[11:16]
        sm   = _time_to_min(hhmm) if ":" in hhmm else 0
        em   = sm + JOB_DURATION
        busy.setdefault(eng_name, {}).setdefault(ds, []).append((sm, em))

    # cursor[eng_name][date_str] = next available start minute
    cursor: dict = {}

    def _next_slot(eng_name: str, ds: str, after_min: int) -> int | None:
        """Return earliest free start >= after_min that doesn't overlap any busy slot."""
        slots = busy.get(eng_name, {}).get(ds, [])
        t = after_min
        while t + JOB_DURATION <= WORK_END:
            overlap = any(s < t + JOB_DURATION and e > t for s, e in slots)
            if not overlap:
                return t
            # Jump past the earliest conflicting slot
            t = max(e for s, e in slots if s < t + JOB_DURATION and e > t)
        return None

    def _book(eng_name: str, ds: str, start: int):
        busy.setdefault(eng_name, {}).setdefault(ds, []).append((start, start + JOB_DURATION))

    assignments   = []
    unschedulable = []

    # Sort jobs by date then by how many skills they require (hardest first)
    jobs_sorted = sorted(jobs, key=lambda j: (j.get("date", ""), -len(j.get("required_skills", []))))

    for job in jobs_sorted:
        jlat = job.get("latitude")
        jlon = job.get("longitude")
        jds  = job.get("date", "")
        if not jds:
            unschedulable.append({"id": job["id"], "reason": "no date"})
            continue
        if jlat and jlat > SCOTLAND_LAT:
            unschedulable.append({"id": job["id"], "reason": "scotland_flag"})
            continue

        req_skills = set(job.get("required_skills") or [])
        best_score = -1
        best_eng   = None
        best_start = None

        for eng in engineers:
            ename = eng["name"]
            elat  = eng.get("lat")
            elon  = eng.get("lon")

            # Skip if on leave
            if absences.get(ename, {}).get(jds):
                continue

            # Compute distance (skip if no home location or too far)
            if elat and elon and jlat and jlon:
                km = _haversine_km(elat, elon, jlat, jlon)
            else:
                km = 0
            if km > MAX_KM:
                continue

            # Shift window from engineer config
            shift_start = _time_to_min(eng.get("shiftStart", "08:00"))
            shift_end   = _time_to_min(eng.get("shiftEnd",   "17:00"))
            day_start   = max(WORK_START, shift_start)
            day_end     = min(WORK_END,   shift_end)

            # Earliest available slot
            cur = cursor.get(ename, {}).get(jds, day_start)
            slot = _next_slot(ename, jds, cur)
            if slot is None or slot + JOB_DURATION > day_end:
                continue  # fully booked

            # --- Score ---
            eskills = set(eng_skills.get(ename, []))
            if req_skills:
                match_ratio = len(req_skills & eskills) / len(req_skills)
            else:
                match_ratio = 1.0
            # Pass 1: require full match; pass 2 relaxed below
            smatch = match_ratio

            dist_score = max(0, 1 - km / MAX_KM)
            # load score — favour less-loaded engineers
            day_jobs  = len(busy.get(ename, {}).get(jds, []))
            load_score = max(0, 1 - day_jobs / 9)

            score = smatch * 40 + dist_score * 30 + load_score * 30

            if score > best_score and (not req_skills or smatch > 0):
                best_score = score
                best_eng   = ename
                best_start = slot

        if best_eng is None:
            # Pass 2: relax skill requirement — just closest available
            for eng in sorted(engineers, key=lambda e: _haversine_km(
                    e.get("lat") or 52.5, e.get("lon") or -1.9, jlat or 52.5, jlon or -1.9)):
                ename = eng["name"]
                if absences.get(ename, {}).get(jds):
                    continue
                shift_start = _time_to_min(eng.get("shiftStart", "08:00"))
                shift_end   = _time_to_min(eng.get("shiftEnd",   "17:00"))
                day_start   = max(WORK_START, shift_start)
                day_end     = min(WORK_END,   shift_end)
                cur  = cursor.get(ename, {}).get(jds, day_start)
                slot = _next_slot(ename, jds, cur)
                if slot is None or slot + JOB_DURATION > day_end:
                    continue
                elat = eng.get("lat"); elon = eng.get("lon")
                if elat and elon and jlat and jlon:
                    km = _haversine_km(elat, elon, jlat, jlon)
                    if km > MAX_KM:
                        continue
                best_eng   = ename
                best_start = slot
                break

        if best_eng is None:
            unschedulable.append({"id": job["id"], "reason": "no_capacity"})
            continue

        # Commit
        _book(best_eng, jds, best_start)
        cursor.setdefault(best_eng, {})[jds] = best_start + JOB_DURATION

        h, m   = divmod(best_start, 60)
        iso_dt = f"{jds}T{h:02d}:{m:02d}:00"
        assignments.append({
            "id":             job["id"],
            "engineer_name":  best_eng,
            "scheduled_time": iso_dt,
        })

    return {"assignments": assignments, "unschedulable": unschedulable}


# ── POST /api/schedule/generate ───────────────────────────────────────────────

@app.post("/api/schedule/generate")
def generate_schedule():
    """
    Generate a draft schedule for a Mon–Fri week.

    Body (JSON):
      { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD", "dry_run": false }

    Fetches unassigned jobs + engineer data from Supabase, runs the greedy
    scheduler, writes schedule_status='draft' assignments back, returns summary.
    """
    body      = request.get_json(force=True) or {}
    date_from = body.get("from", date.today().isoformat())
    date_to   = body.get("to",   date_from)
    dry_run   = bool(body.get("dry_run", False))

    try:
        # 1. Unscheduled jobs (no engineer assigned, not cancelled)
        jobs_raw = sb_get(
            "adv_calls",
            f"select=id,call_id,customer_name,latitude,longitude,required_skills,"
            f"call_type,scheduled_time,status,category"
            f"&cancelled=eq.0"
            f"&engineer_name=is.null"
            f"&scheduled_time=gte.{date_from}T00:00:00"
            f"&scheduled_time=lte.{date_to}T23:59:59"
            f"&limit=2000"
        )
        # Also grab jobs where engineer_name is 'Unassigned'
        jobs_raw2 = sb_get(
            "adv_calls",
            f"select=id,call_id,customer_name,latitude,longitude,required_skills,"
            f"call_type,scheduled_time,status,category"
            f"&cancelled=eq.0"
            f"&engineer_name=eq.Unassigned"
            f"&scheduled_time=gte.{date_from}T00:00:00"
            f"&scheduled_time=lte.{date_to}T23:59:59"
            f"&limit=2000"
        )
        jobs_combined = jobs_raw + jobs_raw2

        # Normalise: extract date from scheduled_time or generate weekday sequence
        jobs = []
        for row in jobs_combined:
            st = row.get("scheduled_time") or ""
            jobs.append({
                "id":             row["id"],
                "date":           st[:10] if st else "",
                "latitude":       row.get("latitude"),
                "longitude":      row.get("longitude"),
                "required_skills": row.get("required_skills") or
                                   ([row["category"]] if row.get("category") else []),
            })

        # 2. Already-scheduled jobs (to avoid conflicts)
        existing = sb_get(
            "adv_calls",
            f"select=id,engineer_name,scheduled_time"
            f"&cancelled=eq.0"
            f"&engineer_name=not.is.null"
            f"&engineer_name=neq.Unassigned"
            f"&scheduled_time=gte.{date_from}T00:00:00"
            f"&scheduled_time=lte.{date_to}T23:59:59"
            f"&limit=5000"
        )

        # 3. Engineers (home locations from Supabase, fall back to config)
        sb_engs = sb_get(
            "adv_engineers",
            "select=adv_name,home_lat,home_lon,postcode&active=eq.true&limit=100"
        )
        sb_eng_map = {r["adv_name"]: r for r in sb_engs if r.get("adv_name")}

        cfg = _load_eng_config()
        engineers = []
        for name, c in cfg.items():
            sb = sb_eng_map.get(name, {})
            lat = sb.get("home_lat") or c.get("lat")
            lon = sb.get("home_lon") or c.get("lon")
            engineers.append({
                "name":       name,
                "lat":        lat,
                "lon":        lon,
                "shiftStart": c.get("shiftStart", "08:00"),
                "shiftEnd":   c.get("shiftEnd",   "17:00"),
            })

        # 4. Engineer skills from Supabase
        skills_rows = sb_get(
            "adv_engineer_skills",
            "select=engineer_name,skill_name&has_skill=eq.true&limit=5000"
        )
        eng_skills: dict = {}
        for sr in skills_rows:
            eng_skills.setdefault(sr["engineer_name"], []).append(sr["skill_name"])

        # 5. Absences
        abs_rows = sb_get(
            "adv_engineer_absences",
            f"select=engineer_name,start_date,end_date"
            f"&start_date=lte.{date_to}"
            f"&end_date=gte.{date_from}"
            f"&limit=500"
        )
        absences: dict = {}
        for ar in abs_rows:
            d = date.fromisoformat(ar["start_date"])
            end = date.fromisoformat(ar["end_date"])
            while d <= end:
                absences.setdefault(ar["engineer_name"], {})[d.isoformat()] = True
                d += timedelta(days=1)

        # 6. Run scheduler
        result = _run_scheduler(jobs, engineers, eng_skills, absences, existing)

        # 7. Write assignments to Supabase (unless dry_run)
        written = 0
        errors  = []
        if not dry_run:
            for asgn in result["assignments"]:
                ok = sb_patch(
                    "adv_calls",
                    f"id=eq.{asgn['id']}",
                    {
                        "engineer_name":  asgn["engineer_name"],
                        "scheduled_time": asgn["scheduled_time"],
                        "schedule_status": "draft",
                    }
                )
                if ok:
                    written += 1
                else:
                    errors.append(asgn["id"])

        return jsonify({
            "ok":            True,
            "dry_run":       dry_run,
            "from":          date_from,
            "to":            date_to,
            "jobs_found":    len(jobs),
            "assigned":      len(result["assignments"]),
            "unschedulable": len(result["unschedulable"]),
            "written":       written,
            "errors":        errors,
            "assignments":   result["assignments"] if dry_run else [],
            "unschedulable_detail": result["unschedulable"],
        })

    except Exception as e:
        app.logger.exception("schedule/generate failed")
        return jsonify({"error": str(e)}), 500


# ── PATCH /api/schedule/move ──────────────────────────────────────────────────

@app.patch("/api/schedule/move")
def move_job():
    """
    Move a single job to a new engineer / time slot (drag-and-drop write-back).

    Body (JSON):
      { "id": <adv_calls.id>, "engineer_name": "...", "scheduled_time": "YYYY-MM-DDTHH:MM:SS" }
    """
    body = request.get_json(force=True) or {}
    job_id    = body.get("id")
    eng_name  = body.get("engineer_name")
    sched_time = body.get("scheduled_time")

    if not job_id or not eng_name or not sched_time:
        return jsonify({"error": "id, engineer_name and scheduled_time required"}), 400

    try:
        ok = sb_patch(
            "adv_calls",
            f"id=eq.{job_id}",
            {
                "engineer_name":   eng_name,
                "scheduled_time":  sched_time,
                "schedule_status": "draft",   # manual move keeps draft status
            }
        )
        return jsonify({"ok": ok, "id": job_id, "engineer_name": eng_name,
                        "scheduled_time": sched_time})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── POST /api/schedule/confirm ────────────────────────────────────────────────

@app.post("/api/schedule/confirm")
def confirm_schedule():
    """
    Promote all draft jobs in a date range to confirmed.

    Body (JSON):
      { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD" }
    """
    body      = request.get_json(force=True) or {}
    date_from = body.get("from")
    date_to   = body.get("to", date_from)

    if not date_from:
        return jsonify({"error": "'from' date required"}), 400

    try:
        # Fetch draft jobs to count them first
        drafts = sb_get(
            "adv_calls",
            f"select=id"
            f"&schedule_status=eq.draft"
            f"&scheduled_time=gte.{date_from}T00:00:00"
            f"&scheduled_time=lte.{date_to}T23:59:59"
            f"&limit=5000"
        )
        if not drafts:
            return jsonify({"ok": True, "confirmed": 0, "message": "No draft jobs in range"})

        # Bulk confirm
        url = (f"{SB_URL}/rest/v1/adv_calls"
               f"?schedule_status=eq.draft"
               f"&scheduled_time=gte.{date_from}T00:00:00"
               f"&scheduled_time=lte.{date_to}T23:59:59")
        r = requests.patch(url, headers=SB_HDR, json={"schedule_status": "confirmed"}, timeout=20)

        return jsonify({
            "ok":        r.ok,
            "confirmed": len(drafts),
            "from":      date_from,
            "to":        date_to,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3004))
    print(f"🚀  Advance Dispatch backend running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
