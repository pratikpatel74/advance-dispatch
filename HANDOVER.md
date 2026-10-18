# Advance Dispatch — Handover / Session Log

Last updated: 2026-10-18

---

## 1. App Overview

**URL:** https://advance-dispatch.netlify.app/  
**Repo:** https://github.com/pratikpatel74/advance-dispatch  
**Deploy:** Netlify auto-deploys on `git push` to `main`  
**Backend DB:** Supabase project `ehuhqzjnikvykldasygc`  
**Map tiles:** Stadia Maps — API key `2d0ad031-42b2-4940-8885-01d3c3da7637`

All app logic lives in a single file: `index.html`. Edit locally, commit, push → Netlify deploys automatically.

**Important — git lock file issue:** The Cowork sandbox leaves a `HEAD.lock` in `.git/` after committing. Before pushing from your Mac always run:
```bash
rm ~/Documents/Projects/Advance-Apps/advance-dispatch/.git/HEAD.lock
git -C ~/Documents/Projects/Advance-Apps/advance-dispatch push
```

---

## 2. Supabase Tables

| Table | Purpose |
|---|---|
| `adv_calls` | All jobs. Key columns: `call_id`, `engineer_name`, `status`, `scheduled_time`, `required_skills` (array), `category`, `cancelled`, `latitude`, `longitude` |
| `adv_engineers` | Engineer master. Key columns: `adv_name`, `postcode`, `home_lat`, `home_lon`, `department`, `active` |
| `adv_engineer_skills` | Engineer → skill mapping. Columns: `engineer_name`, `skill_name`, `category` (`Equipment`), `has_skill` |
| `adv_engineer_absences` | Absence records for availability scoring |
| `adv_equipment` | Equipment/asset records |

**Supabase anon key** (read/write from browser — public):
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVodWhxempuaWt2eWtsZGFzeWdjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ2NDczOTQsImV4cCI6MjA2MDIyMzM5NH0.eOJIFfOCOK3MhYMgaRUqlLiTKgPTfgQGHIMH15QJ5XU
```

---

## 3. Skill Taxonomy

**Advantage taxonomy** (used in `adv_engineer_skills` and `adv_calls.required_skills`):
Gas, LPG, Refrigeration, Accessories, Air Con, Combi, Gantry, Holding Unit, Insect Killer, Prep, Prime Cooking, Warewashing, Waste Disposal, Water Boilers, Microwave

**Do NOT use VISITOUR skill names** — user has confirmed VISITOUR is ignored for skill matching.

**Normalisation applied to `adv_calls.required_skills`** (SQL already run):
- `"Combi Oven"` → `"Combi"`
- `"Water Boiler"` → `"Water Boilers"`

**Unmatched job skills still pending** (awaiting data from Advantage dev lead — ETA Monday 2026-10-20):
- Extraction / Extraction & Canopy (~220 jobs)
- Countering (~66 jobs)
- Fire Suppression (~56 jobs)

---

## 4. Engineer Name Canonical Format

Always use `adv_name` from `adv_engineers` as the canonical name. Key corrections already applied:

| Wrong (old) | Correct |
|---|---|
| Anthony Reid | Tony Reid |
| Aritotelis Goudelis | Aritotelis Gouldelis |
| Aristotelis Goudelis | Aritotelis Gouldelis |

`ALL_ENGS` array and `ENG_HOURS` dict in `index.html` now use the correct names. `adv_engineer_skills.engineer_name` and `adv_calls.engineer_name` also use correct names.

---

## 5. Engineer Scoring Algorithm

`scoreEngineerForJob(engineer, job, {penalise})` — weights:

| Component | Weight | Source |
|---|---|---|
| Skill match | 30% | `adv_engineer_skills` via `ENG_SKILLS` dict |
| Distance from home | 25% | `adv_engineers.home_lat/lon` via `ENG_HOMES` dict |
| Availability | 20% | `adv_engineer_absences` + working days |
| Workload (jobs that day) | 15% | Existing assignments |
| Route efficiency | 10% | Job proximity to existing day route |

Two-pass scoring in Bulk Assign:
- Pass 1 (`penalise:false`): strict — blocked engineers excluded
- Pass 2 (`penalise:true`): fallback — all engineers scored, blockers noted

**Key globals populated by `loadFromSupabase()`:**
- `ENG_SKILLS` — keyed by `adv_name`, populated from `adv_engineer_skills` where `category='Equipment'`
- `ENG_HOMES` — keyed by `adv_name`, populated from `adv_engineers.home_lat/lon`

**Loading order in `load()` (page startup):**
1. `loadEngineers()` → builds `ENG_DATA` from `ALL_ENGS` (API unavailable from browser)
2. `loadFromSupabase()` → populates `ENG_SKILLS` and `ENG_HOMES`

**Loading order in `loadBulkJobs()` (Bulk Assign tab):**
1. `loadFromSupabase()` → ensure skills fresh
2. `window._engTs = 0` → clear 30s cache
3. `loadEngineers()` → rebuild `ENG_DATA` with populated skills

---

## 6. Home Postcodes — Geocoded

All 32 engineers in the VISITOUR export have been geocoded and stored in `adv_engineers` (`home_lat`, `home_lon`, `postcode`). Three engineers not in the VISITOUR export (Derek Fisher, Scott Morgan, Umit Salah) still have no home coordinates.

Source file: `Advantage Visitour Engineer Config Data 2.xlsx` → sheet `VISITOUR Export Raw Data`

---

## 7. Microwave Skill

Added to `adv_engineer_skills` for: Chris Amor, Paul Holman, Ricky Parrett, Shane Sheppard.  
Covers ~3,254 jobs that previously had no eligible engineers.

---

## 8. App Views

| View | Key notes |
|---|---|
| Planner (day) | Single date picker; loads `S.calls` from Supabase for selected date |
| List | Date range picker; loads `S.listCalls` (separate from `S.calls` to avoid overwriting) |
| Timeline | Uses `S.calls` — same as day view |
| Map | Stadia Maps with API key; uses `S.calls` |
| Bulk Assign | New tab. Loads unallocated open jobs for a date range from Supabase; scores all engineers; allows per-row or bulk confirm |

**Hide Closed toggle** — active by default, filters `status='C'` from all views.  
**Open–Allocated / Open–Unallocated** — added as status filter options.

---

## 9. Job Rescheduling (already done)

277 jobs that were originally scheduled Sep 1–Oct 18 2026 were spread evenly across 30 working days Oct 19–Nov 30 2026, directly in `adv_calls` via SQL. The remaining ~4,457 open jobs were left on their original scheduled dates.

---

## 10. Pending / Next Steps

- [ ] Get Extraction, Countering, Fire Suppression engineer assignments from Advantage dev lead (Monday 2026-10-20) and add to `adv_engineer_skills`
- [ ] Add home postcodes for Derek Fisher, Scott Morgan, Umit Salah when available
- [ ] Redeploy `brighthr_to_supabase.py` to server `root@167.233.160.227` (noted from earlier session, not yet done)
- [ ] Review Gareth Terrell, Mark Wilson, Rhys Standing — only had "Schedulable" in VISITOUR; confirm whether they have Advantage skills that need adding

---

## 11. Key File Locations

| File | Location |
|---|---|
| Main app | `~/Documents/Projects/Advance-Apps/advance-dispatch/index.html` |
| This document | `~/Documents/Projects/Advance-Apps/advance-dispatch/HANDOVER.md` |
| Engineer skills loader | `~/Documents/Projects/Advance-Apps/advance-dispatch/load_engineer_skills.py` |
| BrightHR sync script | `root@167.233.160.227` (path TBC) |
