from navdb.rules import process_airports, process_navaids, process_runways

from .helpers import airport, navaid, runway


def run_airports(rows, countries=("IN",), types=("large_airport", "medium_airport", "small_airport")):
    return process_airports(rows, set(countries), set(types))


def rules_of(issues):
    return sorted(i.rule for i in issues)


def test_clean_airport_is_kept_without_issues():
    kept, rejected, issues, adj, *_ = run_airports([airport(1, "VOBL")])
    assert [a["ident"] for a in kept] == ["VOBL"] and not rejected and not issues and not adj


def test_ident_is_trimmed_and_uppercased_and_the_change_is_logged():
    kept, _, _, adj, *_ = run_airports([airport(1, " vobl ")])
    assert kept[0]["ident"] == "VOBL"
    assert adj[0].action == "normalize_ident" and "' vobl '" in adj[0].detail


def test_latitude_and_longitude_out_of_range_are_rejected():
    kept, rejected, issues, *_ = run_airports([airport(1, "AAAA", lat=95), airport(2, "BBBB", lon=-181), airport(3, "CCCC")])
    assert [a["ident"] for a in kept] == ["CCCC"]
    assert rejected == {"AAAA", "BBBB"}
    assert {"AP003", "AP004"} <= set(rules_of(issues))


def test_non_numeric_coordinate_is_rejected():
    kept, rejected, issues, *_ = run_airports([airport(1, "AAAA", lat="north")])
    assert not kept and "AP003" in rules_of(issues)


def test_duplicate_ident_keeps_the_first_row_only():
    kept, rejected, issues, *_ = run_airports([airport(1, "VOBL", name="first"), airport(2, "VOBL", name="second")])
    assert len(kept) == 1 and kept[0]["name"] == "first"
    assert "AP002" in rules_of(issues)


def test_blank_ident_is_rejected():
    kept, _, issues, *_ = run_airports([airport(1, "  ")])
    assert not kept and "AP001" in rules_of(issues)


def test_implausible_elevation_is_rejected_but_missing_elevation_is_left_empty():
    kept, rejected, issues, *_ = run_airports([airport(1, "AAAA", elev=99999), airport(2, "BBBB", elev="")])
    assert [a["ident"] for a in kept] == ["BBBB"]
    assert kept[0]["elevation_ft"] is None             # not estimated
    assert {"AP005", "AP007"} <= set(rules_of(issues))


def test_oddly_formatted_ident_is_a_warning_not_a_rejection():
    kept, _, issues, *_ = run_airports([airport(1, "IN-0363")])
    assert kept and [i.severity for i in issues] == ["warning"] and issues[0].rule == "AP006"


def test_country_and_type_filters_define_the_scope():
    rows = [airport(1, "VOBL"), airport(2, "KJFK", country="US"), airport(3, "HELI", type="heliport"),
            airport(4, "CLSD", type="closed")]
    kept, *_ = run_airports(rows)
    assert [a["ident"] for a in kept] == ["VOBL"]


def test_runway_for_an_airport_missing_from_the_source_is_an_error():
    kept, *_rest = run_airports([airport(1, "VOBL")])
    scope = {"VOBL"}
    rw, issues, _ = process_runways([runway(1, "NOPE")], {"VOBL"}, set(), scope, {"VOBL"})
    assert not rw and rules_of(issues) == ["RW001"]


def test_runway_dimension_and_heading_checks():
    rows = [runway(1, "VOBL", length=0), runway(2, "VOBL", le="10", he="28", width=900, le_h=100, he_h=280),
            runway(3, "VOBL", le="11", he="29", le_h=400, he_h=290)]
    rw, issues, _ = process_runways(rows, {"VOBL"}, set(), {"VOBL"}, {"VOBL"})
    assert not rw
    assert {"RW002", "RW003", "RW004"} <= set(rules_of(issues))


def test_heading_that_disagrees_with_the_runway_number_is_a_warning_and_the_row_is_kept():
    rw, issues, _ = process_runways([runway(1, "VOBL", le="18", he="36", le_h=4, he_h=184)],
                                    {"VOBL"}, set(), {"VOBL"}, {"VOBL"})
    assert len(rw) == 1 and rules_of(issues) == ["RW007", "RW007"]


def test_heading_within_magnetic_variation_tolerance_is_accepted():
    rw, issues, _ = process_runways([runway(1, "VOBL", le="09", he="27", le_h=101, he_h=281)],
                                    {"VOBL"}, set(), {"VOBL"}, {"VOBL"})
    assert len(rw) == 1 and not issues


def test_runway_of_a_rejected_airport_is_excluded():
    rw, issues, _ = process_runways([runway(1, "BAD1")], set(), {"BAD1"}, {"BAD1"}, {"BAD1"})
    assert not rw and rules_of(issues) == ["RW008"]


def test_duplicate_runway_keeps_the_first():
    rw, issues, _ = process_runways([runway(1, "VOBL"), runway(2, "VOBL")], {"VOBL"}, set(), {"VOBL"}, {"VOBL"})
    assert len(rw) == 1 and "RW009" in rules_of(issues)


def test_runway_outside_the_selected_scope_is_ignored_silently():
    rw, issues, _ = process_runways([runway(1, "KJFK")], {"VOBL"}, set(), {"VOBL"}, {"VOBL", "KJFK"})
    assert not rw and not issues


def test_navaid_frequency_is_checked_against_the_band_for_its_type():
    rows = [navaid(1, "OK1", freq=112500), navaid(2, "BAD1", freq=90000), navaid(3, "NDB1", type="NDB", freq=350),
            navaid(4, "NDB2", type="NDB", freq=105)]
    kept, issues = process_navaids(rows, {"IN"}, set())
    assert [n["ident"] for n in kept] == ["OK1", "NDB1"]
    assert rules_of(issues) == ["NV002", "NV002"]


def test_navaid_blank_ident_and_bad_coordinates_are_rejected():
    kept, issues = process_navaids([navaid(1, ""), navaid(2, "XYZ", lat=120)], {"IN"}, set())
    assert not kept and {"NV001", "NV003"} <= set(rules_of(issues))


def test_navaid_pointing_at_an_unknown_airport_is_only_informational():
    kept, issues = process_navaids([navaid(1, "VOR1", assoc="ZZZZ")], {"IN"}, {"VOBL"})
    assert len(kept) == 1 and [i.severity for i in issues] == ["info"]
