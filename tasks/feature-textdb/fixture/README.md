# TextDB Specification

Implement the class `TextDB` in `textdb.py`. Standard library only. Everything
in this document is contractual: exact byte layouts, exact exception types and
messages, exact `stats()` keys, exact recovery rules. Nothing here is
decorative.

## Overview

TextDB is a tiny append-only key-value store persisted as text. A database
lives in a directory containing exactly two files:

- `data.tdb` — the append-only data file, one record per line.
- `journal.tdb` — the write-ahead journal used for crash safety. In a healthy
  idle database it is always 0 bytes.

`TextDB(directory)` (accepting `str` or `Path`) opens a database: it creates
the directory if missing (including parents), creates either file as empty if
missing, and then runs **recovery** (see below) before returning. All state
needed to serve reads is rebuilt in memory at open; reads never re-scan the
files afterward.

## Keys and values

- A **key** is a `str` of 1 to 64 characters, each drawn from
  `A–Z a–z 0–9 . _ -` (ASCII letters, digits, dot, underscore, hyphen).
  Anything else — wrong type, empty, too long, a forbidden character — is
  invalid.
- A **value** is a `str` whose UTF-8 encoding is at most 99999 bytes and which
  contains no newline character (U+000A). The empty string is a valid value.
  Values may contain `|`, `#`, spaces, and arbitrary non-ASCII characters.

`put`, `get`, and `delete` all validate the key first, before anything else;
`put` validates the value second, before any I/O. A call that raises for
validation performs no file writes and changes no state.

## Record format

Both files hold **record lines**. A record line is a byte sequence (the files
are read and written as bytes; all lengths below are byte lengths of the UTF-8
encoding):

```
op | '|' | seq | '|' | klen | '|' | key | '|' | vlen | '|' | value | '|' | crc | '\n'
```

- `op` — one byte: `P` (put) or `D` (delete).
- `seq` — the record's sequence number, exactly 10 decimal digits,
  zero-padded. Sequence numbers start at 1.
- `klen` — byte length of the key, exactly 2 decimal digits, zero-padded.
- `key` — exactly `klen` bytes.
- `vlen` — byte length of the value, exactly 5 decimal digits, zero-padded.
  For a `D` record, `vlen` is `00000` and the value field is empty (a `D`
  record with nonzero `vlen` is corrupt).
- `value` — exactly `vlen` bytes. Because `vlen` is explicit, a value
  containing `|` is unambiguous: parse by field widths, never by splitting
  on `|`.
- `crc` — CRC-32 (`zlib.crc32`, masked to 32 bits) of every byte of the line
  from the start through and including the `|` immediately before the crc
  field, formatted as exactly 8 lowercase hex digits, zero-padded.
- The line ends with a single `\n`.

A record line's total length is therefore `33 + klen + vlen` bytes. Keys and
values can never contain a newline, so every record occupies exactly one
`\n`-terminated line.

Worked examples (real CRCs — use them to check your implementation):

```
P|0000000001|05|alpha|00003|one|6bb1be0e
P|0000000002|03|caf|00009|café €|fcf9ccc7
D|0000000007|05|alpha|00000||2291841a
```

(In the second example the value is `café €`, whose UTF-8 encoding is 9
bytes — `vlen` counts bytes, not characters.)

The journal additionally holds **commit lines**:

```
C | '|' | seq | '|' | crc | '\n'
```

where `seq` is 10 zero-padded decimal digits and `crc` is the CRC-32 of the
first 13 bytes (`C|` + seq + `|`), formatted the same way. A commit line is
exactly 22 bytes. Worked example: `C|0000000002|a8ad4337`.

## The write path

Every successful `put` or `delete` performs, in order:

1. Assign the next sequence number (see **Sequence numbers**).
2. Append the record line **and** its commit line to `journal.tdb`.
3. Append the record line (alone) to `data.tdb`.
4. Truncate `journal.tdb` to 0 bytes.

So after any successful mutation the journal exists and is exactly 0 bytes.

## Iteration order

`keys()` returns the **live** keys (those with a current value) in iteration
order: the order in which each key most recently went from absent to present.
Overwriting an existing live key keeps its position. Deleting a key removes
it; putting it again later places it at the end. (These are exactly Python
`dict` insertion semantics.) `keys()` returns a fresh list each call — the
caller mutating it must not affect the database.

## The secondary index

`find_value(value)` returns the list of live keys whose current value equals
`value`, in iteration order, as a fresh list. It performs **no validation of
any kind**: any argument that equals no stored value — including non-strings
and strings no valid value could be — simply yields `[]`. The index must be
consistent after every operation: puts, overwrites, deletes, compaction,
recovery.

## Methods

- `put(key, value) -> None` — insert or overwrite.
- `get(key) -> str` — the current value.
- `delete(key) -> None` — remove a live key (writes a `D` record).
- `keys() -> list[str]` — live keys in iteration order.
- `find_value(value) -> list[str]` — see above.
- `compact() -> None` — see **Compaction**.
- `stats() -> dict` — see **stats()**.
- `close() -> None` — see **Closing**.

`get` or `delete` of a key that is valid but not live raises
`KeyNotFoundError`.

## Sequence numbers

`next_seq` — the number the next mutation will use — is derived from the data
file at open: 1 plus the largest `seq` appearing in `data.tdb` after recovery
(1 if the file is empty). Within a session it then increments by one per
successful `put` or `delete`. `compact()` does **not** change it in-session.
Because compaction can drop the record carrying the largest seq (when the
newest record is a `D`), reopening a compacted database can legitimately
yield a *smaller* `next_seq` than the compacting session had. That is by
design: sequence numbers only need to be unique within the current data file.

## Compaction

`compact()` rewrites `data.tdb` to contain exactly one `P` record per live
key, in iteration order. Each record is **byte-identical to the record that
set that key's current value** — same seq, same value, same crc. (Since
overwrites get fresh sequence numbers but iteration order is arrival order,
a compacted file's sequence numbers need not be monotonic. That is fine.)
Details:

- Delete records and superseded put records never survive compaction.
- A database with no live keys compacts to a 0-byte `data.tdb` (still counts
  as a compaction).
- The journal is left empty; after `compact()` the directory contains exactly
  `data.tdb` and `journal.tdb` — no temporary files left behind.
- In-session `next_seq` is unchanged, and iteration order is unchanged.
- Reopening a compacted database preserves iteration order, because recovery
  derives iteration order from *file order* (see below), not from sequence
  numbers.

## Recovery (runs at every open)

**Step 1 — read the data file strictly.** Split `data.tdb` on `\n`; every
line must be a structurally valid record: correct op byte, separators at the
exact offsets, all-digit seq/klen/vlen fields, total length `32 + klen +
vlen` (excluding the newline), matching lowercase crc, and `vlen == 0` for
`D` records. Structural validation does not re-check key/value *content*
rules (charset, length limits). Any violation — including an empty line, a
final line not terminated by `\n`, or a crc mismatch — raises
`CorruptRecordError` with message `corrupt record at line N` where N is the
1-based line number. If the data file is corrupt the constructor raises and
the journal is left untouched.

**Step 2 — replay.** Apply the data records in file order: `P` sets the key
(absent keys append to iteration order, present keys keep position), `D`
removes it (a `D` for an absent key is a no-op). This file-order replay is
what defines iteration order after a reopen.

**Step 3 — scan the journal leniently.** Starting at byte 0, repeatedly try
to read one structurally valid record line followed immediately by its valid
commit line with the **same seq**. Each such pair is a *committed entry*.
The first defect of any kind — a torn (incomplete) line, an invalid record,
a missing/torn commit line, a commit crc mismatch, a commit seq that doesn't
match the record — stops the scan, and everything from that point on is
discarded, even if later bytes happen to look valid. Journal damage is never
an error: it is a crash artifact, and recovery's job is to discard it.

**Step 4 — apply committed entries.** For each committed entry in order: if
its seq is strictly greater than the largest seq currently in the data file,
append its record line to `data.tdb` and replay it into memory; otherwise
skip it entirely — it is already durable (this happens when a crash landed
after the data append but before the journal truncate, and it must not
produce a duplicate record). Appending updates "largest seq in the data
file" as you go.

**Step 5 — truncate.** Truncate the journal to 0 bytes. Set `next_seq` from
the final data file.

## stats()

Returns a dict with **exactly** these five keys, all ints:

- `"live_keys"` — number of live keys.
- `"data_records"` — number of record lines currently in `data.tdb`
  (including `D` records and superseded `P` records).
- `"journal_bytes"` — current size of `journal.tdb` in bytes (0 in a healthy
  idle database).
- `"next_seq"` — as defined above.
- `"compactions"` — number of successful `compact()` calls **on this
  instance** (not persisted; a fresh open reports 0).

## Closing

`close()` marks the database closed. It is idempotent — closing twice is a
no-op, never an error. Every other method called after `close()` raises
`ClosedError`.

## Error taxonomy

Define these six exception classes in `textdb.py`. All five concrete errors
subclass the base `TextDBError(Exception)`. Messages are exact; the verifier
compares `str(e)` character-for-character.

| Exception | Raised by | Message |
|---|---|---|
| `TextDBError` | (base class only) | — |
| `BadKeyError` | `put`/`get`/`delete` given an invalid key | `invalid key: ` + Python `repr()` of the offending key |
| `BadValueError` | `put` given an invalid value | `invalid value: not a string` / `invalid value: contains newline` / `invalid value: too long` (checked in that order) |
| `KeyNotFoundError` | `get`/`delete` of a valid but absent key | `key not found: ` + the key |
| `CorruptRecordError` | the constructor, on a corrupt data file | `corrupt record at line N` |
| `ClosedError` | any method except `close` after `close()` | `database is closed` |

Note the asymmetry, and honor it: an invalid key raises `BadKeyError`
everywhere — `get("no spaces!")` is a `BadKeyError`, never a
`KeyNotFoundError`. Key validation precedes value validation, so
`put(42, 99)` raises `BadKeyError`, not `BadValueError`.
