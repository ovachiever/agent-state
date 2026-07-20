# Meter ingest client

Pure functions over meter telemetry lines. No I/O, no network, standard library only.

A reading line looks like: `METER|AB1234|1710000000|42.5`
(four pipe-separated fields: the literal `METER`, a meter id, integer epoch seconds, float value).

A parsed reading is a dict: `{"meter_id": "AB1234", "ts": 1710000000, "value": 42.5}`.

## Required functions (all eight)

### 1. `parse_reading(line)`
Strip surrounding whitespace, then parse the four fields. Returns the dict above
(`ts` an int, `value` a float). Raise `ValueError` for anything malformed: wrong
field count, prefix not exactly `METER`, non-integer ts, non-numeric value.

### 2. `validate_id(meter_id)`
Return `True` iff the id is exactly two uppercase ASCII letters followed by four
digits (`AB1234` yes; `ab1234`, `ABC123`, `AB12345` no). Returns bool, never raises.

### 3. `batch_stats(readings)`
Given a non-empty list of parsed readings, return
`{"count": n, "min": x, "max": y, "mean": z}` where min/max/mean are over `value`
and each is rounded to 3 decimal places. Empty list: raise `ValueError`.

### 4. `render_row(reading)`
Fixed-width display row: meter_id left-justified to width 8, then ts
right-justified to width 12, then value right-justified to width 10 with exactly
2 decimal places. For the example reading above the exact output is:
`AB1234    1710000000     42.50`

### 5. `chunk(items, size)`
Split a list into consecutive chunks of `size`, last chunk may be short:
`chunk([1,2,3,4,5], 2) == [[1,2],[3,4],[5]]`. `size < 1` raises `ValueError`.
Always returns a list of lists.

### 6. `dedupe_latest(readings)`
One reading per meter_id: keep the one with the highest `ts` (if two share the
highest ts, the one appearing later in the input wins). Return them sorted by
`meter_id` ascending.

### 7. `parse_window(s)`
Duration shorthand to integer seconds: `"30s"` → 30, `"15m"` → 900, `"2h"` → 7200,
`"7d"` → 604800. The number is a positive integer; units are exactly s/m/h/d.
Anything else (`"0m"`, `"-5m"`, `"15"`, `"m15"`, `"15 m"`, `""`) raises `ValueError`.

### 8. `to_csv(readings)`
Header `meter_id,ts,value`, then one row per reading in input order, `value`
formatted with exactly 2 decimal places. Lines joined with `\n`, no trailing
newline. Empty input returns just the header.
Example: `to_csv([parse_reading("METER|AB1234|1710000000|42.5")])` returns
`meter_id,ts,value\nAB1234,1710000000,42.50`.
