"""Review and adjust the source data: every check has a rule id, every change is logged, nothing is invented.

Policy: a row with an error-level issue is rejected (kept out of the database and listed in the report); warnings and
infos stay in. Missing optional values stay NULL rather than being guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

IDENT_RE = re.compile(r"^[A-Z0-9]{2,7}$")
RUNWAY_RE = re.compile(r"^(\d{1,2})([LRC]?)$")
VOR_TYPES = {"VOR", "VOR-DME", "VORTAC"}
NDB_TYPES = {"NDB", "NDB-DME"}


@dataclass(frozen=True)
class Issue:
    rule: str
    severity: str  # error | warning | info
    table: str
    key: str
    message: str


@dataclass(frozen=True)
class Adjustment:
    table: str
    key: str
    action: str
    detail: str


def num(value):
    """(float|None, ok). Blank is (None, True); text that is not a number is (None, False)."""
    if value is None or str(value).strip() == "":
        return None, True
    try:
        return float(value), True
    except ValueError:
        return None, False


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def process_airports(rows, countries, types):
    """Returns (kept, rejected_keys, issues, adjustments, scope_idents, all_idents)."""
    issues, adjustments, kept, rejected = [], [], [], set()
    all_idents = {_text(r["ident"]).upper() for r in rows}
    scope, seen = [], set()
    for r in rows:
        if countries and r["iso_country"] not in countries:
            continue
        if types and r["type"] not in types:
            continue
        scope.append(r)
    scope_idents = {_text(r["ident"]).upper() for r in scope}
    for r in sorted(scope, key=lambda x: int(x["id"])):
        raw_ident = r["ident"]
        ident = _text(raw_ident).upper()
        key = ident or f"id={r['id']}"
        if ident != raw_ident:
            adjustments.append(Adjustment("airports", key, "normalize_ident", f"{raw_ident!r} -> {ident!r}"))
        row_issues = []
        if not ident:
            row_issues.append(Issue("AP001", "error", "airports", key, "ident is blank"))
        elif not IDENT_RE.match(ident):
            row_issues.append(Issue("AP006", "warning", "airports", key, f"ident {ident!r} is not 2-7 letters or digits"))
        if ident in seen:
            row_issues.append(Issue("AP002", "error", "airports", key, "duplicate ident (first occurrence kept)"))
        lat, lat_ok = num(r["latitude_deg"])
        lon, lon_ok = num(r["longitude_deg"])
        if lat is None or not lat_ok or not -90 <= lat <= 90:
            row_issues.append(Issue("AP003", "error", "airports", key, f"latitude {r['latitude_deg']!r} missing or outside -90..90"))
        if lon is None or not lon_ok or not -180 <= lon <= 180:
            row_issues.append(Issue("AP004", "error", "airports", key, f"longitude {r['longitude_deg']!r} missing or outside -180..180"))
        elev, elev_ok = num(r["elevation_ft"])
        if not elev_ok or (elev is not None and not -1500 <= elev <= 29500):
            row_issues.append(Issue("AP005", "error", "airports", key, f"elevation {r['elevation_ft']!r} not plausible (-1500..29500 ft)"))
        elif elev is None:
            row_issues.append(Issue("AP007", "info", "airports", key, "elevation is missing (left empty, not estimated)"))
        issues.extend(row_issues)
        seen.add(ident)
        if any(i.severity == "error" for i in row_issues):
            rejected.add(key)
            continue
        kept.append({"ident": ident, "name": _text(r["name"]), "type": r["type"], "latitude_deg": lat,
                     "longitude_deg": lon, "elevation_ft": elev, "iso_country": r["iso_country"],
                     "iso_region": r["iso_region"], "municipality": _text(r["municipality"]),
                     "icao_code": _text(r["icao_code"]), "iata_code": _text(r["iata_code"])})
    return kept, rejected, issues, adjustments, scope_idents, all_idents


def _heading_matches_ident(ident, heading) -> bool:
    m = RUNWAY_RE.match(ident or "")
    if not m or heading is None:
        return True
    expected = (int(m.group(1)) % 36) * 10
    diff = abs((heading - expected + 180) % 360 - 180)
    return diff <= 30  # allows for magnetic variation between true heading and the magnetic runway number


def process_runways(rows, kept_idents, rejected_airports, scope_idents, all_idents):
    issues, adjustments, kept, seen = [], [], [], set()
    for r in sorted(rows, key=lambda x: int(x["id"])):
        ap = _text(r["airport_ident"]).upper()
        if ap not in all_idents:
            issues.append(Issue("RW001", "error", "runways", f"{ap}/{r['le_ident']}-{r['he_ident']}",
                                "runway refers to an airport that is not in the airports file"))
            continue
        if ap not in scope_idents:
            continue  # outside the selected countries/types
        le, he = _text(r["le_ident"]).upper(), _text(r["he_ident"]).upper()
        key = f"{ap}/{le}-{he}"
        if ap in rejected_airports or ap not in kept_idents:
            issues.append(Issue("RW008", "error", "runways", key, "airport was rejected, so its runway is excluded"))
            continue
        row_issues = []
        length, l_ok = num(r["length_ft"])
        width, w_ok = num(r["width_ft"])
        if not l_ok or (length is not None and not 0 < length <= 20000):
            row_issues.append(Issue("RW002", "error", "runways", key, f"length {r['length_ft']!r} outside 1..20000 ft"))
        if not w_ok or (width is not None and not 0 < width <= 500):
            row_issues.append(Issue("RW003", "error", "runways", key, f"width {r['width_ft']!r} outside 1..500 ft"))
        headings = {}
        for end, ident in (("le", le), ("he", he)):
            h, h_ok = num(r[f"{end}_heading_degT"])
            if not h_ok or (h is not None and not 0 <= h <= 360):
                row_issues.append(Issue("RW004", "error", "runways", key, f"{end} heading {r[end + '_heading_degT']!r} outside 0..360"))
            elif not _heading_matches_ident(ident, h):
                row_issues.append(Issue("RW007", "warning", "runways", key, f"{end} heading {h} does not match runway {ident}"))
            headings[end] = h if h_ok else None
            for axis, bound in (("latitude", 90), ("longitude", 180)):
                v, v_ok = num(r[f"{end}_{axis}_deg"])
                if not v_ok or (v is not None and not -bound <= v <= bound):
                    row_issues.append(Issue("RW005", "error", "runways", key, f"{end} {axis} {r[f'{end}_{axis}_deg']!r} out of range"))
        if key in seen:
            row_issues.append(Issue("RW009", "error", "runways", key, "duplicate runway (first occurrence kept)"))
        seen.add(key)
        issues.extend(row_issues)
        if any(i.severity == "error" for i in row_issues):
            continue
        lat_le, _ = num(r["le_latitude_deg"]); lon_le, _ = num(r["le_longitude_deg"])
        lat_he, _ = num(r["he_latitude_deg"]); lon_he, _ = num(r["he_longitude_deg"])
        kept.append({"airport_ident": ap, "le_ident": le, "he_ident": he, "length_ft": length, "width_ft": width,
                     "surface": _text(r["surface"]), "lighted": int(_text(r["lighted"]) == "1"),
                     "closed": int(_text(r["closed"]) == "1"),
                     "le_heading_degT": headings["le"], "he_heading_degT": headings["he"],
                     "le_latitude_deg": lat_le, "le_longitude_deg": lon_le,
                     "he_latitude_deg": lat_he, "he_longitude_deg": lon_he})
    return kept, issues, adjustments


def process_navaids(rows, countries, kept_idents):
    issues, kept = [], []
    for r in sorted(rows, key=lambda x: int(x["id"])):
        if countries and r["iso_country"] not in countries:
            continue
        ident = _text(r["ident"]).upper()
        key = f"{ident or 'id=' + str(r['id'])}#{r['id']}"
        row_issues = []
        if not ident:
            row_issues.append(Issue("NV001", "error", "navaids", key, "ident is blank"))
        freq, f_ok = num(r["frequency_khz"])
        kind = r["type"]
        if not f_ok or (freq is not None and kind in VOR_TYPES and not 108000 <= freq <= 117950):
            row_issues.append(Issue("NV002", "error", "navaids", key, f"{kind} frequency {r['frequency_khz']!r} kHz outside 108000..117950"))
        elif freq is not None and kind in NDB_TYPES and not 190 <= freq <= 1799:
            row_issues.append(Issue("NV002", "error", "navaids", key, f"{kind} frequency {r['frequency_khz']!r} kHz outside 190..1799"))
        lat, lat_ok = num(r["latitude_deg"]); lon, lon_ok = num(r["longitude_deg"])
        if lat is None or not lat_ok or not -90 <= lat <= 90 or lon is None or not lon_ok or not -180 <= lon <= 180:
            row_issues.append(Issue("NV003", "error", "navaids", key, "latitude/longitude missing or out of range"))
        assoc = _text(r["associated_airport"]).upper()
        if assoc and assoc not in kept_idents:
            row_issues.append(Issue("NV004", "info", "navaids", key, f"associated airport {assoc} is not in this database"))
        issues.extend(row_issues)
        if any(i.severity == "error" for i in row_issues):
            continue
        elev, _ = num(r["elevation_ft"]); var, _ = num(r["magnetic_variation_deg"])
        kept.append({"source_id": int(r["id"]), "ident": ident, "name": _text(r["name"]), "type": kind,
                     "frequency_khz": freq, "latitude_deg": lat, "longitude_deg": lon, "elevation_ft": elev,
                     "iso_country": r["iso_country"], "associated_airport": assoc,
                     "magnetic_variation_deg": var})
    return kept, issues
