"""python -m navdb fetch | build | diff"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .build import build
from .diff import diff_databases, to_markdown
from .sources import fetch


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="navdb", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download the public source files")
    f.add_argument("--dest", required=True)
    b = sub.add_parser("build", help="validate the sources and build a database for the AIRAC cycle of --date")
    b.add_argument("--source", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--countries", default="IN", help="comma separated ISO country codes")
    b.add_argument("--date", default=None, help="YYYY-MM-DD, default today")
    b.add_argument("--built-at", default=None, help="timestamp to record (default now); set it for reproducible manifests")
    b.add_argument("--max-reject-pct", type=float, default=5.0)
    d = sub.add_parser("diff", help="change report between two built databases")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--markdown", default=None)
    a = ap.parse_args(argv)

    if a.cmd == "fetch":
        for p in fetch(a.dest):
            print("downloaded", p)
        return 0
    if a.cmd == "build":
        m = build(a.source, a.out, countries=tuple(c.strip().upper() for c in a.countries.split(",")),
                  on_date=date.fromisoformat(a.date) if a.date else None, built_at=a.built_at,
                  max_reject_pct=a.max_reject_pct)
        print(json.dumps(m, indent=2))
        return 0 if m["status"] == "PASS" else 1
    report = diff_databases(a.old, a.new)
    md = to_markdown(report, Path(a.old).name, Path(a.new).name)
    if a.markdown:
        Path(a.markdown).write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
