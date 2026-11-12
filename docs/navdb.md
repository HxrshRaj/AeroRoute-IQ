# Navigation database build tool (`src/navdb`)

A small, scripted version of a monthly aeronautical-database build: take source data, review and adjust it by documented
rules, build a versioned database, check the output, and record what happened. It uses the free, public-domain
[OurAirports](https://github.com/davidmegginson/ourairports-data) files (airports, runways, navaids). It was written to practise the
process and its automation, not to produce flight-grade data.

## Monthly process

| Step | What to do | Command or place |
|---|---|---|
| 1. Retrieve source data | Download the three source files. | `python -m navdb fetch --dest data/navdb/source` |
| 2. Review and adjust | Run the build. Every rule that fires is listed; rows with an error are left out; every automatic change is logged. | `python -m navdb build --source data/navdb/source --out data/navdb/out --countries IN` |
| 3. Check the outputs | Read the manifest (status, counts, rejected rows) and `*.issues.json`. A build fails if more than `--max-reject-pct` of airports are rejected. | `data/navdb/out/navdb_<cycle>.manifest.json` |
| 4. Compare with last cycle | Produce a change report of added, removed and changed records. | `python -m navdb diff old.sqlite new.sqlite --markdown change.md` |
| 5. Deliver | Hand over the `.sqlite` file with its manifest and the change report. | the monthly workflow uploads all of these |
| 6. Document | Record anything unusual in the issue log (template below). | this file or your tracker |

The database is named for its AIRAC cycle (28-day cycles, for example `navdb_2611.sqlite`), and the manifest records the
effective date. `src/navdb/airac.py` computes the cycle from a date and is tested against published cycle dates.

## What is checked

| Rule | Severity | Meaning |
|---|---|---|
| AP001 | error | airport identifier is blank |
| AP002 | error | duplicate identifier (the first row is kept) |
| AP003 / AP004 | error | latitude / longitude missing, not a number, or out of range |
| AP005 | error | elevation not plausible (-1500 to 29500 ft) |
| AP006 | warning | identifier is not 2 to 7 letters or digits (for example local codes with a hyphen) |
| AP007 | info | elevation missing; it is left empty and never estimated |
| RW001 | error | runway refers to an airport that is not in the airports file |
| RW002 / RW003 | error | runway length / width out of range |
| RW004 / RW005 | error | runway heading / threshold coordinate out of range |
| RW007 | warning | heading differs from the runway number by more than 30 degrees |
| RW008 | error | runway excluded because its airport was rejected |
| RW009 | error | duplicate runway (the first row is kept) |
| NV001 | error | navaid identifier blank |
| NV002 | error | frequency outside the band for its type (VOR 108.0 to 117.95 MHz, NDB 190 to 1799 kHz) |
| NV003 | error | navaid coordinates missing or out of range |
| NV004 | info | navaid refers to an airport that is not in this database |

## Data quality notes

Standards such as DO-200B (processing of aeronautical data) describe data quality attributes that a process has to control:
accuracy, resolution, traceability, timeliness, completeness and format. This tool touches each of them in a small way:

* **Traceability:** the manifest stores the SHA-256 and row count of every input file, and the database stores every issue and adjustment.
* **Integrity:** `content_sha256` is a hash of the table contents in key order. The same input gives the same hash (tested), and any change to a value changes it.
* **Completeness / format:** range, format and referential-integrity rules, with missing values left empty and reported.
* **Timeliness:** the build is tied to an AIRAC cycle and the monthly workflow runs on a schedule.

## Honest limits

* This is **not** Jeppesen data, ARINC 424 or any certified product, and it is **not** DO-200B, DO-178C or DO-330 compliant. Nothing here
  is tool-qualified or approved for any flight use. The list above is awareness of the concepts, not a compliance claim.
* The source is community-maintained open data with no assurance level. A rule firing means "review this row", not "this row is wrong in the real world".
* Resolution and accuracy are only checked as plausible ranges, not against an authoritative source.
* The monthly workflow builds the Indian subset by default. It does not keep history between runs; compare cycles by downloading the previous artifact.

## Issue log template

| Date | Cycle | Rule / step | Record | What happened | Action taken | Owner |
|---|---|---|---|---|---|---|
