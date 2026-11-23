from datetime import date, timedelta


def dates_between(start: date, end: date) -> list[date]:
    if start > end:
        return []

    days = end.timetuple().tm_yday - start.timetuple().tm_yday
    return [start + timedelta(days=offset) for offset in range(days + 1)]
