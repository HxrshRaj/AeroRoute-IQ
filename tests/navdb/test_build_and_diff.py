import json
import sqlite3
from datetime import date

import pytest

from navdb.__main__ import main
from navdb.build import build
from navdb.diff import diff_databases, to_markdown
from navdb.sources import sha256_file

from .helpers import airport, navaid, runway, write_sources

FIXED = {"on_date": date(2026, 11, 12), "built_at": "2026-11-12T00:00:00Z"}


def sources(tmp_path, name="src", elev_vobl=3000, extra_airports=()):
    airports = [airport(1, "VOBL", elev=elev_vobl), airport(2, "VIDP", lat=28.5, lon=77.1, elev=777), airport(3, "BAD1", lat=999),
                *extra_airports]
    return write_sources(tmp_path / name, airports,
                         [runway(1, "VOBL"), runway(2, "VIDP", le="10", he="28", le_h=100, he_h=280), runway(3, "BAD1")],
                         [navaid(1, "BLR", assoc="VOBL"), navaid(2, "BAD", freq=90000)])


def test_build_writes_the_database_and_manifest(tmp_path):
    m = build(sources(tmp_path), tmp_path / "out", **FIXED, max_reject_pct=100)
    assert m["cycle"] == "2611" and m["effective_date"] == "2026-10-29"
    assert m["counts"] == {"airports": 2, "runways": 2, "navaids": 1}
    assert m["rejected_airports"] == 1
    conn = sqlite3.connect(tmp_path / "out" / m["database"])
    assert conn.execute("SELECT COUNT(*) FROM airports").fetchone()[0] == 2
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("SELECT value FROM metadata WHERE key='cycle'").fetchone()[0] == "2611"
    assert conn.execute("SELECT COUNT(*) FROM validation_issues WHERE severity='error'").fetchone()[0] >= 3
    assert (tmp_path / "out" / "navdb_2611.manifest.json").exists()


def test_manifest_records_the_hash_and_row_count_of_every_source_file(tmp_path):
    src = sources(tmp_path)
    m = build(src, tmp_path / "out", **FIXED, max_reject_pct=100)
    by_file = {s["file"]: s for s in m["sources"]}
    for name in ("airports", "runways", "navaids"):
        assert by_file[f"{name}.csv"]["sha256"] == sha256_file(src / f"{name}.csv")
    assert by_file["airports.csv"]["rows"] == 3 and by_file["navaids.csv"]["rows"] == 2


def test_the_same_input_gives_the_same_content_hash_and_manifest(tmp_path):
    src = sources(tmp_path)
    a = build(src, tmp_path / "a", **FIXED, max_reject_pct=100)
    b = build(src, tmp_path / "b", **FIXED, max_reject_pct=100)
    assert a["content_sha256"] == b["content_sha256"]
    assert (tmp_path / "a" / "navdb_2611.manifest.json").read_text() == (tmp_path / "b" / "navdb_2611.manifest.json").read_text()


def test_changing_one_source_value_changes_the_content_hash(tmp_path):
    a = build(sources(tmp_path, "s1", elev_vobl=3000), tmp_path / "a", **FIXED, max_reject_pct=100)
    b = build(sources(tmp_path, "s2", elev_vobl=3001), tmp_path / "b", **FIXED, max_reject_pct=100)
    assert a["content_sha256"] != b["content_sha256"]
    assert a["sources"][0]["sha256"] != b["sources"][0]["sha256"]


def test_build_fails_when_too_many_airports_are_rejected(tmp_path):
    m = build(sources(tmp_path), tmp_path / "out", **FIXED, max_reject_pct=10)  # 1 of 3 rejected = 33%
    assert m["status"] == "FAIL" and m["reject_pct_airports"] == pytest.approx(33.333, abs=0.01)


def test_cycle_follows_the_build_date(tmp_path):
    m = build(sources(tmp_path), tmp_path / "out", on_date=date(2026, 11, 26), built_at="x", max_reject_pct=100)
    assert m["cycle"] == "2612" and m["database"] == "navdb_2612.sqlite"


def test_diff_reports_added_removed_and_changed_records(tmp_path):
    old = build(sources(tmp_path, "s1"), tmp_path / "o", **FIXED, max_reject_pct=100)
    new = build(sources(tmp_path, "s2", elev_vobl=3100, extra_airports=[airport(9, "VABB", lat=19.1, lon=72.9, elev=39)]),
                tmp_path / "n", on_date=date(2026, 11, 26), built_at="y", max_reject_pct=100)
    report = diff_databases(tmp_path / "o" / old["database"], tmp_path / "n" / new["database"])
    assert report["airports"]["added"] == ["VABB"] and report["airports"]["removed"] == []
    assert report["airports"]["changed"] == [{"key": "VOBL", "fields": {"elevation_ft": (3000.0, 3100.0)}}]
    assert report["runways"] == {"added": [], "removed": [], "changed": []}
    md = to_markdown(report, "old", "new")
    assert "Added: 1" in md and "VOBL" in md and "elevation_ft: 3000.0 to 3100.0" in md


def test_cli_build_returns_nonzero_on_fail_and_diff_writes_markdown(tmp_path, capsys):
    src = sources(tmp_path)
    assert main(["build", "--source", str(src), "--out", str(tmp_path / "o"), "--date", "2026-11-12",
                 "--max-reject-pct", "100"]) == 0
    assert main(["build", "--source", str(src), "--out", str(tmp_path / "f"), "--date", "2026-11-12",
                 "--max-reject-pct", "1"]) == 1
    db = tmp_path / "o" / "navdb_2611.sqlite"
    md = tmp_path / "change.md"
    assert main(["diff", str(db), str(db), "--markdown", str(md)]) == 0
    assert "Changed: 0" in md.read_text()
    json.loads((tmp_path / "o" / "navdb_2611.manifest.json").read_text())
