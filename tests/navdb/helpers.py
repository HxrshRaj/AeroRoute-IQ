import csv

AIRPORT_COLS = ["id", "ident", "type", "name", "latitude_deg", "longitude_deg", "elevation_ft", "continent", "iso_country",
                "iso_region", "municipality", "scheduled_service", "icao_code", "iata_code", "gps_code", "local_code",
                "home_link", "wikipedia_link", "keywords"]
RUNWAY_COLS = ["id", "airport_ref", "airport_ident", "length_ft", "width_ft", "surface", "lighted", "closed", "le_ident",
               "le_latitude_deg", "le_longitude_deg", "le_elevation_ft", "le_heading_degT", "le_displaced_threshold_ft",
               "he_ident", "he_latitude_deg", "he_longitude_deg", "he_elevation_ft", "he_heading_degT",
               "he_displaced_threshold_ft"]
NAVAID_COLS = ["id", "filename", "ident", "name", "type", "frequency_khz", "latitude_deg", "longitude_deg", "elevation_ft",
               "iso_country", "dme_frequency_khz", "dme_channel", "dme_latitude_deg", "dme_longitude_deg",
               "dme_elevation_ft", "slaved_variation_deg", "magnetic_variation_deg", "usageType", "power",
               "associated_airport"]


def airport(id, ident, lat=12.0, lon=77.0, elev=3000, type="medium_airport", country="IN", **kw):
    row = {c: "" for c in AIRPORT_COLS}
    row.update(id=id, ident=ident, type=type, name=f"{ident} Airport", latitude_deg=lat, longitude_deg=lon,
               elevation_ft=elev, iso_country=country, iso_region=f"{country}-KA", municipality="Town")
    row.update(kw)
    return row


def runway(id, airport_ident, le="09", he="27", length=9000, width=150, le_h=90, he_h=270, **kw):
    row = {c: "" for c in RUNWAY_COLS}
    row.update(id=id, airport_ident=airport_ident, length_ft=length, width_ft=width, surface="ASP", lighted=1, closed=0,
               le_ident=le, he_ident=he, le_heading_degT=le_h, he_heading_degT=he_h)
    row.update(kw)
    return row


def navaid(id, ident, type="VOR", freq=112500, lat=12.1, lon=77.1, country="IN", assoc="", **kw):
    row = {c: "" for c in NAVAID_COLS}
    row.update(id=id, ident=ident, name=f"{ident} nav", type=type, frequency_khz=freq, latitude_deg=lat,
               longitude_deg=lon, iso_country=country, associated_airport=assoc)
    row.update(kw)
    return row


def write_sources(dest, airports, runways=(), navaids=()):
    dest.mkdir(parents=True, exist_ok=True)
    for name, cols, rows in (("airports", AIRPORT_COLS, airports), ("runways", RUNWAY_COLS, runways),
                             ("navaids", NAVAID_COLS, navaids)):
        with open(dest / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    return dest
