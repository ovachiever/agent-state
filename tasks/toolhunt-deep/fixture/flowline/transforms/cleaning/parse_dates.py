"""Cleaning transform: ISO `YYYY-MM-DD` strings split into year/month/day ints."""


def parse_dates(rows):
    """Return a new row list with ISO `YYYY-MM-DD` strings split into year/month/day ints."""
    parsed = []
    for row in rows:
        updated = dict(row)
        value = row.get("date")
        if isinstance(value, str) and len(value) == 10 and value[4] == value[7] == "-":
            updated["year"], updated["month"], updated["day"] = (
                int(value[:4]), int(value[5:7]), int(value[8:10])
            )
        parsed.append(updated)
    return parsed
