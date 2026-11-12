from datetime import date

import pytest

from navdb.airac import cycle_id, effective_date


@pytest.mark.parametrize("day,expected", [
    (date(2020, 1, 2), "2001"),     # first cycle of 2020
    (date(2021, 1, 28), "2101"),
    (date(2024, 12, 26), "2413"),   # thirteenth cycle of 2024
    (date(2025, 1, 22), "2413"),    # day before 2501 takes effect
    (date(2025, 1, 23), "2501"),
    (date(2025, 12, 24), "2512"),
    (date(2025, 12, 25), "2513"),   # AIRAC 2513 took effect on 25 December 2025
    (date(2026, 1, 21), "2513"),
    (date(2026, 1, 22), "2601"),    # AIRAC 2601 took effect on 22 January 2026
    (date(2026, 11, 12), "2611"),
    (date(2027, 1, 20), "2613"),
    (date(2027, 1, 21), "2701"),
])
def test_cycle_id_matches_published_cycles(day, expected):
    assert cycle_id(day) == expected


def test_effective_date_is_the_start_of_the_cycle():
    assert effective_date(date(2026, 11, 12)) == date(2026, 10, 29)
    assert effective_date(date(2026, 10, 29)) == date(2026, 10, 29)
    assert effective_date(date(2026, 11, 25)) == date(2026, 10, 29)
    assert effective_date(date(2026, 11, 26)) == date(2026, 11, 26)
