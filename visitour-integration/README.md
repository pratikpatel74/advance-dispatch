# VISITOUR Integration — Advance Dispatch

This package documents how Advance Dispatch pushes engineer (FieldManager) data
to the VISITOUR scheduling system, and includes the utility scripts for bulk updates.

---

## Architecture

```
Advance Dispatch frontend (index.html)
        │
        │  PATCH /api/engineer-config/<name>
        ▼
backend.py  (Flask, port 3004)
        │
        │  POST https://advgroup-test.vt-fls.com/VTS/WS/FieldManager
        ▼
VISITOUR API  (HTTP Basic Auth, XML body)
```

When any VISITOUR field is changed (capacity, radius, speed %, etc.), `backend.py`
automatically calls the VISITOUR REST endpoint to keep VISITOUR in sync.

---

## VISITOUR Connection

| Setting        | Value                                         |
|----------------|-----------------------------------------------|
| Base URL       | `https://advgroup-test.vt-fls.com/VTS/WS`    |
| Auth           | HTTP Basic Auth (username + password)         |
| Content-Type   | `text/xml; charset=utf-8`                     |
| Protocol       | REST with XML body (not SOAP envelope)        |

Credentials are read from environment variables:
```
VT_USER=INT.TEST
VT_PASS=<password>
```

---

## Fields Pushed to VISITOUR

All radius/distance values are stored in **miles** in `engineer_config.json` and
converted to **kilometres** before sending to VISITOUR.

| Config Field   | VISITOUR XML Tag          | Notes                        |
|----------------|---------------------------|------------------------------|
| `vtCapacity`   | `<Capacity>`              | Work time units (default 50) |
| `vtCapacity2`  | `<Capacity2>`             | Second TU (default 0)        |
| `vtSpeedPct`   | `<SpeedPercent>`          | Travel speed factor (100=normal) |
| `vtWorkPct`    | `<WorkPercent>`           | Work time factor (100=normal)|
| `vtOvertime`   | `<Overtime>`              | Max overtime (minutes/day)   |
| `vtMinRadius`  | `<MinDeployableRadius>`   | Min radius — stored mi, sent km |
| `vtMaxRadius`  | `<MaxDeployableRadius>`   | Max radius — stored mi, sent km |
| `vtMaxDrive`   | `<MaxDrivingDistance>`    | Max drive — stored mi, sent km  |

Conversion: `km = round(miles / 0.621371)`

---

## XML Request Format (POST /FieldManager)

```xml
<?xml version="1.0" encoding="utf-8"?>
<FieldManager>
  <FMExtID>487</FMExtID>
  <Capacity>50</Capacity>
  <Capacity2>0</Capacity2>
  <SpeedPercent>100</SpeedPercent>
  <WorkPercent>100</WorkPercent>
  <Overtime>0</Overtime>
  <MinDeployableRadius>0</MinDeployableRadius>
  <MaxDeployableRadius>80</MaxDeployableRadius>
  <MaxDrivingDistance>161</MaxDrivingDistance>
</FieldManager>
```

## XML Response — Success Codes

| Code    | Meaning       |
|---------|---------------|
| `0`     | Success       |
| `10000` | Also success  |
| Other   | Error         |

Response example:
```xml
<FieldManagerResult>0</FieldManagerResult>
```
or
```xml
<return>0</return>
```

---

## Reading Back from VISITOUR (GetFieldManagers)

POST to `/GetFieldManagers` with:
```xml
<?xml version="1.0" encoding="utf-8"?>
<GetFieldManagers>
  <SubcontractorOnly>false</SubcontractorOnly>
</GetFieldManagers>
```

Returns `<FieldManager>` or `<Resource>` blocks per engineer. 
Key tags: `<FMExtID>`, `<Capacity>`, `<SpeedPercent>`, `<WorkPercent>`,
`<MinDeployableRadius>`, `<MaxDeployableRadius>`, `<MaxDrivingDistance>`, `<Skills>`.

---

## Engineer ID Mapping (fmExtId)

Each engineer has a `fmExtId` — their VISITOUR FieldManager External ID.
See `engineer_id_map.py` for the full list.
Engineers without an fmExtId cannot be pushed to VISITOUR.

---

## Utility Scripts

| Script                    | Purpose                                              |
|---------------------------|------------------------------------------------------|
| `set_radius_all.py`       | Bulk-set Max Radius + Max Drive for all engineers    |
| `apply_settings_from_spreadsheet.py` | Apply values from the operational lead's xlsx |
| `engineer_id_map.py`      | fmExtId ↔ name reference                            |

Run any script with: `python3 <script>.py`
The API must be reachable at `http://167.233.160.227:3004`.

