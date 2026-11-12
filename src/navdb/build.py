"""Build one versioned database from the source files: review, adjust, write SQLite, write a manifest with checksums."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from . import __version__
from .airac import cycle_id, effective_date
from .rules import process_airports, process_navaids, process_runways
from .sources import sha256_file, read_csv

SCHEMA = {
    "airports": ("ident TEXT PRIMARY KEY, name TEXT, type TEXT, latitude_deg REAL NOT NULL, longitude_deg REAL NOT NULL, "
                 "elevation_ft REAL, iso_country TEXT, iso_region TEXT, municipality TEXT, icao_code TEXT, iata_code TEXT"),
    "runways": ("airport_ident TEXT NOT NULL REFERENCES airports(ident), le_ident TEXT, he_ident TEXT, length_ft REAL, "
                "width_ft REAL, surface TEXT, lighted INTEGER, closed INTEGER, le_heading_degT REAL, he_heading_degT REAL, "
                "le_latitude_deg REAL, le_longitude_deg REAL, he_latitude_deg REAL, he_longitude_deg REAL, "
                "PRIMARY KEY (airport_ident, le_ident, he_ident)"),
    "navaids": ("source_id INTEGER PRIMARY KEY, ident TEXT NOT NULL, name TEXT, type TEXT, frequency_khz REAL, "
                "latitude_deg REAL NOT NULL, longitude_deg REAL NOT NULL, elevation_ft REAL, iso_country TEXT, "
                "associated_airport TEXT, magnetic_variation_deg REAL"),
}
ORDER_BY = {"airports": "ident", "runways": "airport_ident, le_ident, he_ident", "navaids": "source_id"}


def content_sha256(conn: sqlite3.Connection) -> str:
    """Hash of the table contents in key order. Independent of file layout, so identical data gives an identical hash."""
    h = hashlib.sha256()
    for table in SCHEMA:
        h.update(table.encode())
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY {ORDER_BY[table]}"):
            h.update(repr(row).encode())
    return h.hexdigest()


def _insert(conn, table, rows):
    if not rows:
        return
    cols = list(rows[0])
    conn.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                     [tuple(r[c] for c in cols) for r in rows])


def build(source_dir, out_dir, countries=("IN",), types=("large_airport", "medium_airport", "small_airport"),
          on_date: date | None = None, built_at: str | None = None, max_reject_pct: float = 5.0) -> dict:
    source_dir, out_dir = Path(source_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    on_date = on_date or date.today()
    cycle = cycle_id(on_date)
    raw = {name: read_csv(source_dir / f"{name}.csv") for name in ("airports", "runways", "navaids")}

    airports, rejected, issues, adjustments, scope, all_idents = process_airports(raw["airports"], set(countries), set(types))
    kept_idents = {a["ident"] for a in airports}
    runways, rw_issues, rw_adj = process_runways(raw["runways"], kept_idents, rejected, scope, all_idents)
    navaids, nv_issues = process_navaids(raw["navaids"], set(countries), kept_idents)
    issues += rw_issues + nv_issues
    adjustments += rw_adj

    db_path = out_dir / f"navdb_{cycle}.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        for table, ddl in SCHEMA.items():
            conn.execute(f"CREATE TABLE {table} ({ddl})")
        conn.execute("CREATE TABLE validation_issues (rule TEXT, severity TEXT, tbl TEXT, key TEXT, message TEXT)")
        conn.execute("CREATE TABLE adjustments (tbl TEXT, key TEXT, action TEXT, detail TEXT)")
        _insert(conn, "airports", airports)
        _insert(conn, "runways", runways)
        _insert(conn, "navaids", navaids)
        conn.executemany("INSERT INTO validation_issues VALUES (?,?,?,?,?)",
                         [(i.rule, i.severity, i.table, i.key, i.message) for i in issues])
        conn.executemany("INSERT INTO adjustments VALUES (?,?,?,?)",
                         [(a.table, a.key, a.action, a.detail) for a in adjustments])
        digest = content_sha256(conn)
        conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany("INSERT INTO metadata VALUES (?,?)",
                         [("cycle", cycle), ("content_sha256", digest), ("tool_version", __version__)])
        conn.commit()
    finally:
        conn.close()

    in_scope_rows = {"airports": len(airports) + len(rejected), "runways": len(runways), "navaids": len(navaids)}
    errors = [i for i in issues if i.severity == "error"]
    rejected_airports = len(rejected)
    reject_pct = 100.0 * rejected_airports / max(1, in_scope_rows["airports"])
    manifest = {
        "tool_version": __version__,
        "cycle": cycle,
        "effective_date": effective_date(on_date).isoformat(),
        "built_at": built_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": {"countries": sorted(countries), "airport_types": sorted(types)},
        "sources": [{"file": f"{n}.csv", "sha256": sha256_file(source_dir / f"{n}.csv"), "rows": len(raw[n])} for n in raw],
        "counts": {"airports": len(airports), "runways": len(runways), "navaids": len(navaids)},
        "rejected_airports": rejected_airports,
        "reject_pct_airports": round(reject_pct, 3),
        "issues_by_severity": dict(Counter(i.severity for i in issues)),
        "issues_by_rule": dict(sorted(Counter(i.rule for i in issues).items())),
        "adjustments": len(adjustments),
        "content_sha256": digest,
        "database": db_path.name,
        "status": "FAIL" if reject_pct > max_reject_pct else "PASS",
        "max_reject_pct": max_reject_pct,
    }
    (out_dir / f"navdb_{cycle}.manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (out_dir / f"navdb_{cycle}.issues.json").write_text(json.dumps(
        [i.__dict__ for i in issues if i.severity != "info"], indent=2))
    return manifest
