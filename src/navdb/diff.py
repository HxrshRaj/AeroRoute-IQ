"""Compare two built databases: what was added, removed or changed between cycles."""
from __future__ import annotations

import sqlite3

KEYS = {"airports": ("ident",), "runways": ("airport_ident", "le_ident", "he_ident"), "navaids": ("source_id",)}


def _load(path, table):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()
    return {tuple(r[k] for k in KEYS[table]): r for r in rows}


def diff_databases(old_path, new_path) -> dict:
    report = {}
    for table in KEYS:
        old, new = _load(old_path, table), _load(new_path, table)
        changed = []
        for key in sorted(old.keys() & new.keys(), key=str):
            fields = {c: (old[key][c], new[key][c]) for c in old[key] if old[key][c] != new[key][c]}
            if fields:
                changed.append({"key": "/".join(map(str, key)), "fields": fields})
        report[table] = {"added": sorted("/".join(map(str, k)) for k in new.keys() - old.keys()),
                         "removed": sorted("/".join(map(str, k)) for k in old.keys() - new.keys()),
                         "changed": changed}
    return report


def to_markdown(report: dict, old_name: str, new_name: str) -> str:
    lines = [f"# Change report: {old_name} to {new_name}", ""]
    for table, r in report.items():
        lines += [f"## {table}", f"- Added: {len(r['added'])}", f"- Removed: {len(r['removed'])}",
                  f"- Changed: {len(r['changed'])}", ""]
        for label in ("added", "removed"):
            for key in r[label][:20]:
                lines.append(f"  - {label}: `{key}`")
        for c in r["changed"][:20]:
            detail = ", ".join(f"{f}: {a} to {b}" for f, (a, b) in c["fields"].items())
            lines.append(f"  - changed `{c['key']}`: {detail}")
        lines.append("")
    return "\n".join(lines)
