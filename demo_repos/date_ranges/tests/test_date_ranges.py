from datetime import date

from date_ranges import dates_between


def test_weekdays() -> None:
    assert dates_between(date(2024, 5, 6), date(2024, 5, 8)) == [
        date(2024, 5, 6),
        date(2024, 5, 7),
        date(2024, 5, 8),
    ]


def test_single_day() -> None:
    day = date(2024, 8, 1)
    assert dates_between(day, day) == [day]


def test_reversed_bounds() -> None:
    assert dates_between(date(2024, 5, 8), date(2024, 5, 6)) == []


def test_end_of_month() -> None:
    assert dates_between(date(2024, 2, 28), date(2024, 3, 1)) == [
        date(2024, 2, 28),
        date(2024, 2, 29),
        date(2024, 3, 1),
    ]


def test_holiday_period() -> None:
    assert dates_between(date(2024, 12, 31), date(2025, 1, 2)) == [
        date(2024, 12, 31),
        date(2025, 1, 1),
        date(2025, 1, 2),
    ]
