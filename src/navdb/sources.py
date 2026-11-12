"""Source files: download, hash and read. Every build records the SHA-256 and row count of each input (traceability)."""
from __future__ import annotations

import csv
import hashlib
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/"
FILES = ("airports.csv", "runways.csv", "navaids.csv")


def fetch(dest, base_url: str = BASE_URL, timeout: int = 120) -> list[Path]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for name in FILES:
        target = dest / name
        with urllib.request.urlopen(base_url + name, timeout=timeout) as resp:
            target.write_bytes(resp.read())
        out.append(target)
    return out


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
