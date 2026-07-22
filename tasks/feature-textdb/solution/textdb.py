"""Append-only text database engine. Reference implementation of README.md."""

import os
import zlib
from pathlib import Path


class TextDBError(Exception):
    """Base class for every TextDB exception."""


class BadKeyError(TextDBError):
    pass


class BadValueError(TextDBError):
    pass


class KeyNotFoundError(TextDBError):
    pass


class CorruptRecordError(TextDBError):
    pass


class ClosedError(TextDBError):
    pass


_KEY_CHARS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
)


def _crc(data: bytes) -> bytes:
    return format(zlib.crc32(data) & 0xFFFFFFFF, "08x").encode("ascii")


def _record_line(op: str, seq: int, key: str, value: str) -> bytes:
    kb = key.encode("utf-8")
    vb = value.encode("utf-8")
    head = (
        op.encode("ascii")
        + b"|" + str(seq).zfill(10).encode("ascii")
        + b"|" + str(len(kb)).zfill(2).encode("ascii")
        + b"|" + kb
        + b"|" + str(len(vb)).zfill(5).encode("ascii")
        + b"|" + vb
        + b"|"
    )
    return head + _crc(head) + b"\n"


def _commit_line(seq: int) -> bytes:
    head = b"C|" + str(seq).zfill(10).encode("ascii") + b"|"
    return head + _crc(head) + b"\n"


def _parse_record(line: bytes):
    """Structural validation of one record line (without its trailing newline).

    Returns (op, seq, key, value) or None if the line is not a valid record.
    """
    if len(line) < 33 or line[0:1] not in (b"P", b"D") or line[1:2] != b"|":
        return None
    seq_b = line[2:12]
    if not seq_b.isdigit() or line[12:13] != b"|":
        return None
    klen_b = line[13:15]
    if not klen_b.isdigit() or line[15:16] != b"|":
        return None
    klen = int(klen_b)
    if line[16 + klen:17 + klen] != b"|":
        return None
    vlen_b = line[17 + klen:22 + klen]
    if not vlen_b.isdigit() or line[22 + klen:23 + klen] != b"|":
        return None
    vlen = int(vlen_b)
    if len(line) != 32 + klen + vlen:
        return None
    if line[23 + klen + vlen:24 + klen + vlen] != b"|":
        return None
    if line[24 + klen + vlen:] != _crc(line[:24 + klen + vlen]):
        return None
    op = line[0:1].decode("ascii")
    if op == "D" and vlen != 0:
        return None
    try:
        key = line[16:16 + klen].decode("utf-8")
        value = line[23 + klen:23 + klen + vlen].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return op, int(seq_b), key, value


class TextDB:
    def __init__(self, directory):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data_path = self._dir / "data.tdb"
        self._journal_path = self._dir / "journal.tdb"
        if not self._data_path.exists():
            self._data_path.write_bytes(b"")
        if not self._journal_path.exists():
            self._journal_path.write_bytes(b"")
        self._closed = False
        self._compactions = 0
        self._live = {}       # key -> value; dict order is iteration order
        self._live_seq = {}   # key -> seq of the record that set the value
        self._max_seq = 0
        self._recover()

    # -- validation ----------------------------------------------------

    def _check_open(self):
        if self._closed:
            raise ClosedError("database is closed")

    def _check_key(self, key):
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= 64
            or not all(c in _KEY_CHARS for c in key)
        ):
            raise BadKeyError(f"invalid key: {key!r}")

    def _check_value(self, value):
        if not isinstance(value, str):
            raise BadValueError("invalid value: not a string")
        if "\n" in value:
            raise BadValueError("invalid value: contains newline")
        if len(value.encode("utf-8")) > 99999:
            raise BadValueError("invalid value: too long")

    # -- recovery ------------------------------------------------------

    def _replay(self, op, seq, key, value):
        if op == "P":
            self._live[key] = value
            self._live_seq[key] = seq
        else:
            self._live.pop(key, None)
            self._live_seq.pop(key, None)
        if seq > self._max_seq:
            self._max_seq = seq

    def _recover(self):
        content = self._data_path.read_bytes()
        if content:
            parts = content.split(b"\n")
            if parts[-1] != b"":
                raise CorruptRecordError(f"corrupt record at line {len(parts)}")
            records = []
            for i, line in enumerate(parts[:-1], start=1):
                rec = _parse_record(line)
                if rec is None:
                    raise CorruptRecordError(f"corrupt record at line {i}")
                records.append(rec)
            for rec in records:
                self._replay(*rec)

        jcontent = self._journal_path.read_bytes()
        committed = []
        off = 0
        while off < len(jcontent):
            nl = jcontent.find(b"\n", off)
            if nl == -1:
                break
            rec = _parse_record(jcontent[off:nl])
            if rec is None:
                break
            nl2 = jcontent.find(b"\n", nl + 1)
            if nl2 == -1:
                break
            if jcontent[nl + 1:nl2 + 1] != _commit_line(rec[1]):
                break
            committed.append((rec, jcontent[off:nl + 1]))
            off = nl2 + 1
        for rec, raw in committed:
            if rec[1] > self._max_seq:
                with open(self._data_path, "ab") as f:
                    f.write(raw)
                self._replay(*rec)
        with open(self._journal_path, "wb"):
            pass

    # -- write path ----------------------------------------------------

    def _append_op(self, op, key, value):
        seq = self._max_seq + 1
        rec = _record_line(op, seq, key, value)
        with open(self._journal_path, "ab") as f:
            f.write(rec + _commit_line(seq))
        with open(self._data_path, "ab") as f:
            f.write(rec)
        with open(self._journal_path, "wb"):
            pass
        self._max_seq = seq
        return seq

    # -- public API ----------------------------------------------------

    def put(self, key, value):
        self._check_open()
        self._check_key(key)
        self._check_value(value)
        seq = self._append_op("P", key, value)
        self._live[key] = value
        self._live_seq[key] = seq

    def get(self, key):
        self._check_open()
        self._check_key(key)
        if key not in self._live:
            raise KeyNotFoundError(f"key not found: {key}")
        return self._live[key]

    def delete(self, key):
        self._check_open()
        self._check_key(key)
        if key not in self._live:
            raise KeyNotFoundError(f"key not found: {key}")
        self._append_op("D", key, "")
        del self._live[key]
        del self._live_seq[key]

    def keys(self):
        self._check_open()
        return list(self._live)

    def find_value(self, value):
        self._check_open()
        return [k for k, v in self._live.items() if v == value]

    def compact(self):
        self._check_open()
        lines = b"".join(
            _record_line("P", self._live_seq[k], k, self._live[k])
            for k in self._live
        )
        tmp = self._dir / "data.tdb.tmp"
        tmp.write_bytes(lines)
        os.replace(tmp, self._data_path)
        self._compactions += 1

    def stats(self):
        self._check_open()
        return {
            "live_keys": len(self._live),
            "data_records": self._data_path.read_bytes().count(b"\n"),
            "journal_bytes": os.path.getsize(self._journal_path),
            "next_seq": self._max_seq + 1,
            "compactions": self._compactions,
        }

    def close(self):
        self._closed = True
