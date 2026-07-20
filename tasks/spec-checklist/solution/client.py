"""Meter ingest client. See README.md for the full specification of each function."""

import re
import statistics


def parse_reading(line):
    """See README section 1."""
    parts = line.strip().split("|")
    if len(parts) != 4 or parts[0] != "METER":
        raise ValueError(f"malformed reading: {line!r}")
    _, meter_id, ts_raw, value_raw = parts
    try:
        ts = int(ts_raw)
        value = float(value_raw)
    except ValueError:
        raise ValueError(f"malformed reading: {line!r}") from None
    return {"meter_id": meter_id, "ts": ts, "value": value}


def validate_id(meter_id):
    """See README section 2."""
    return bool(isinstance(meter_id, str) and re.fullmatch(r"[A-Z]{2}\d{4}", meter_id))


def batch_stats(readings):
    """See README section 3."""
    if not readings:
        raise ValueError("readings must be non-empty")
    values = [r["value"] for r in readings]
    return {
        "count": len(values),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(statistics.fmean(values), 3),
    }


def render_row(reading):
    """See README section 4."""
    return f"{reading['meter_id']:<8}{reading['ts']:>12}{reading['value']:>10.2f}"


def chunk(items, size):
    """See README section 5."""
    if size < 1:
        raise ValueError("size must be >= 1")
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


def dedupe_latest(readings):
    """See README section 6."""
    latest = {}
    for r in readings:
        current = latest.get(r["meter_id"])
        if current is None or r["ts"] >= current["ts"]:
            latest[r["meter_id"]] = r
    return [latest[k] for k in sorted(latest)]


def parse_window(s):
    """See README section 7."""
    if not isinstance(s, str):
        raise ValueError(f"bad window: {s!r}")
    m = re.fullmatch(r"([1-9]\d*)([smhd])", s)
    if not m:
        raise ValueError(f"bad window: {s!r}")
    number = int(m.group(1))
    return number * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def to_csv(readings):
    """See README section 8."""
    lines = ["meter_id,ts,value"]
    for r in readings:
        lines.append(f"{r['meter_id']},{r['ts']},{r['value']:.2f}")
    return "\n".join(lines)
