"""Hidden verifier for feature-textdb. Usage: verify.py <workspace>

All database files used for recovery/corruption checks are authored here,
byte-for-byte from the README's record grammar — the fixture is never trusted.
"""

import importlib.util
import json
import shutil
import sys
import tempfile
import zlib
from pathlib import Path

ALL_CHECKS = [
    "api_surface", "basic_put_get", "overwrite_get", "missing_key_error",
    "bad_key_rejected", "bad_value_rejected", "record_format_exact",
    "empty_value_record", "pipe_value", "unicode_value_bytelen",
    "delete_record_format", "journal_empty_after_ops", "iteration_order_basic",
    "iteration_order_reinsert", "overwrite_keeps_position", "keys_returns_copy",
    "find_value_basic", "find_value_overwrite_delete", "find_value_no_validation",
    "stats_shape", "stats_values", "reopen_state", "compact_bytes_exact",
    "compact_stats_and_files", "compact_then_ops", "compact_reopen_order",
    "compact_reopen_next_seq", "compact_empty_db", "recovery_committed_applied",
    "recovery_next_seq", "recovery_uncommitted_discarded", "recovery_torn_record",
    "recovery_torn_commit", "recovery_second_torn", "recovery_prefix_rule",
    "recovery_bad_commit_crc", "recovery_seq_mismatch", "recovery_idempotent",
    "recovery_delete_entry", "corrupt_data_bad_crc", "corrupt_data_torn_line",
    "corrupt_data_bad_framing", "closed_semantics", "bad_value_order",
    "recovery_commit_first", "recovery_mismatch_then_valid",
    "unicode_reopen_parse", "journal_unicode_entry", "find_value_after_recovery",
]


def _crc(data: bytes) -> bytes:
    return format(zlib.crc32(data) & 0xFFFFFFFF, "08x").encode("ascii")


def rec(op: str, seq: int, key: str, value: str) -> bytes:
    kb, vb = key.encode("utf-8"), value.encode("utf-8")
    head = (
        op.encode() + b"|" + str(seq).zfill(10).encode()
        + b"|" + str(len(kb)).zfill(2).encode() + b"|" + kb
        + b"|" + str(len(vb)).zfill(5).encode() + b"|" + vb + b"|"
    )
    return head + _crc(head) + b"\n"


def commit(seq: int) -> bytes:
    head = b"C|" + str(seq).zfill(10).encode() + b"|"
    return head + _crc(head) + b"\n"


def tamper(line: bytes) -> bytes:
    """Flip one crc character (position -9 counted with trailing newline)."""
    i = len(line) - 9
    ch = b"0" if line[i:i + 1] != b"0" else b"1"
    return line[:i] + ch + line[i + 1:]


def main():
    checks = {name: False for name in ALL_CHECKS}
    root = Path(tempfile.mkdtemp(prefix="textdb-verify-"))
    try:
        run_checks(checks, root)
    except Exception:
        pass
    finally:
        shutil.rmtree(root, ignore_errors=True)
    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


def run_checks(checks, root):
    ws = Path(sys.argv[1]).resolve()
    spec = importlib.util.spec_from_file_location("textdb", ws / "textdb.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    TextDB = mod.TextDB

    def cls(name):
        return getattr(mod, name, None)

    def raises(fn, cname, msg=None):
        c = cls(cname)
        if c is None:
            return False
        try:
            fn()
        except Exception as e:
            return isinstance(e, c) and (msg is None or str(e) == msg)
        return False

    def check(name, fn):
        try:
            checks[name] = bool(fn())
        except Exception:
            checks[name] = False

    def newdir(name, data=None, journal=None):
        d = root / name
        d.mkdir()
        if data is not None:
            (d / "data.tdb").write_bytes(data)
        if journal is not None:
            (d / "journal.tdb").write_bytes(journal)
        return d

    def data_bytes(d):
        return (d / "data.tdb").read_bytes()

    def journal_size(d):
        p = d / "journal.tdb"
        return p.stat().st_size if p.exists() else -1

    # -- surface --------------------------------------------------------

    def api_surface():
        base = cls("TextDBError")
        if base is None or not (isinstance(base, type) and issubclass(base, Exception)):
            return False
        for n in ("BadKeyError", "BadValueError", "KeyNotFoundError",
                  "CorruptRecordError", "ClosedError"):
            c = cls(n)
            if c is None or not (isinstance(c, type) and issubclass(c, base)):
                return False
        return all(
            callable(getattr(TextDB, m, None))
            for m in ("put", "get", "delete", "keys", "find_value",
                      "compact", "stats", "close")
        )

    check("api_surface", api_surface)

    # -- basics ---------------------------------------------------------

    def basic_put_get():
        db = TextDB(newdir("basic"))
        db.put("hello", "world")
        return db.get("hello") == "world"

    check("basic_put_get", basic_put_get)

    def overwrite_get():
        db = TextDB(newdir("overwrite"))
        db.put("k", "v1")
        db.put("k", "v2")
        return db.get("k") == "v2"

    check("overwrite_get", overwrite_get)

    def missing_key_error():
        db = TextDB(newdir("missing"))
        return (
            raises(lambda: db.get("ghost"), "KeyNotFoundError", "key not found: ghost")
            and raises(lambda: db.delete("ghost"), "KeyNotFoundError", "key not found: ghost")
        )

    check("missing_key_error", missing_key_error)

    def bad_key_rejected():
        db = TextDB(newdir("badkey"))
        long = "x" * 65
        return (
            raises(lambda: db.put(42, "v"), "BadKeyError", "invalid key: 42")
            and raises(lambda: db.put("", "v"), "BadKeyError", "invalid key: ''")
            and raises(lambda: db.put(long, "v"), "BadKeyError", f"invalid key: {long!r}")
            and raises(lambda: db.put("a b", "v"), "BadKeyError", "invalid key: 'a b'")
            and raises(lambda: db.get("a b"), "BadKeyError", "invalid key: 'a b'")
            and raises(lambda: db.delete(""), "BadKeyError", "invalid key: ''")
        )

    check("bad_key_rejected", bad_key_rejected)

    def bad_value_rejected():
        d = newdir("badvalue")
        db = TextDB(d)
        ok = (
            raises(lambda: db.put("k", 7), "BadValueError", "invalid value: not a string")
            and raises(lambda: db.put("k", "a\nb"), "BadValueError", "invalid value: contains newline")
            and raises(lambda: db.put("k", "x" * 100000), "BadValueError", "invalid value: too long")
            and raises(lambda: db.put(42, 7), "BadKeyError", "invalid key: 42")
        )
        s = db.stats()
        return ok and s["data_records"] == 0 and s["next_seq"] == 1

    check("bad_value_rejected", bad_value_rejected)

    # -- record format ---------------------------------------------------

    def record_format_exact():
        d = newdir("format")
        db = TextDB(d)
        db.put("alpha", "one")
        db.put("beta", "two")
        return data_bytes(d) == rec("P", 1, "alpha", "one") + rec("P", 2, "beta", "two")

    check("record_format_exact", record_format_exact)

    def empty_value_record():
        d = newdir("emptyval")
        db = TextDB(d)
        db.put("e", "")
        return db.get("e") == "" and data_bytes(d) == rec("P", 1, "e", "")

    check("empty_value_record", empty_value_record)

    def pipe_value():
        d = newdir("pipe")
        db = TextDB(d)
        db.put("p", "a|b|c")
        db.close()
        if data_bytes(d) != rec("P", 1, "p", "a|b|c"):
            return False
        return TextDB(d).get("p") == "a|b|c"

    check("pipe_value", pipe_value)

    def unicode_value_bytelen():
        d = newdir("unicode")
        db = TextDB(d)
        val = "héllo\U0001f389"  # héllo🎉 — 10 UTF-8 bytes, 6 code points
        db.put("u", val)
        db.close()
        if data_bytes(d) != rec("P", 1, "u", val):
            return False
        db2 = TextDB(d)
        return db2.get("u") == val and db2.stats()["data_records"] == 1

    check("unicode_value_bytelen", unicode_value_bytelen)

    def delete_record_format():
        d = newdir("delrec")
        db = TextDB(d)
        db.put("k", "v")
        db.delete("k")
        return (
            data_bytes(d) == rec("P", 1, "k", "v") + rec("D", 2, "k", "")
            and raises(lambda: db.get("k"), "KeyNotFoundError", "key not found: k")
        )

    check("delete_record_format", delete_record_format)

    def journal_empty_after_ops():
        d = newdir("journal")
        db = TextDB(d)
        db.put("k", "v")
        if journal_size(d) != 0:
            return False
        db.delete("k")
        return journal_size(d) == 0

    check("journal_empty_after_ops", journal_empty_after_ops)

    # -- iteration order and index --------------------------------------

    def iteration_order_basic():
        db = TextDB(newdir("order1"))
        for k in ("c", "a", "b"):
            db.put(k, "v")
        return db.keys() == ["c", "a", "b"]

    check("iteration_order_basic", iteration_order_basic)

    def iteration_order_reinsert():
        db = TextDB(newdir("order2"))
        for k in ("a", "b", "c"):
            db.put(k, "v")
        db.delete("a")
        db.put("a", "v2")
        return db.keys() == ["b", "c", "a"]

    check("iteration_order_reinsert", iteration_order_reinsert)

    def overwrite_keeps_position():
        db = TextDB(newdir("order3"))
        db.put("a", "1")
        db.put("b", "2")
        db.put("a", "3")
        return db.keys() == ["a", "b"] and db.get("a") == "3"

    check("overwrite_keeps_position", overwrite_keeps_position)

    def keys_returns_copy():
        db = TextDB(newdir("copy"))
        db.put("a", "1")
        got = db.keys()
        got.append("zz")
        return db.keys() == ["a"]

    check("keys_returns_copy", keys_returns_copy)

    idx_dir = newdir("index")

    def find_value_basic():
        db = TextDB(idx_dir)
        db.put("a", "1")
        db.put("b", "2")
        db.put("c", "1")
        return db.find_value("1") == ["a", "c"]

    check("find_value_basic", find_value_basic)

    def find_value_overwrite_delete():
        db = TextDB(idx_dir)
        db.put("b", "1")
        if db.find_value("1") != ["a", "b", "c"] or db.find_value("2") != []:
            return False
        db.delete("a")
        return db.find_value("1") == ["b", "c"]

    check("find_value_overwrite_delete", find_value_overwrite_delete)

    def find_value_no_validation():
        db = TextDB(idx_dir)
        return db.find_value("x\ny") == [] and db.find_value(123) == []

    check("find_value_no_validation", find_value_no_validation)

    # -- stats and reopen ------------------------------------------------

    def stats_shape():
        db = TextDB(newdir("shape"))
        s = db.stats()
        want = {"live_keys", "data_records", "journal_bytes", "next_seq", "compactions"}
        return (
            isinstance(s, dict)
            and set(s) == want
            and all(isinstance(v, int) for v in s.values())
        )

    check("stats_shape", stats_shape)

    def stats_values():
        db = TextDB(newdir("statsval"))
        if db.stats() != {"live_keys": 0, "data_records": 0, "journal_bytes": 0,
                          "next_seq": 1, "compactions": 0}:
            return False
        db.put("a", "1")
        db.put("b", "2")
        db.delete("a")
        return db.stats() == {"live_keys": 1, "data_records": 3, "journal_bytes": 0,
                              "next_seq": 4, "compactions": 0}

    check("stats_values", stats_values)

    def reopen_state():
        d = newdir("reopen")
        db = TextDB(d)
        db.put("a", "1")
        db.put("b", "2")
        db.put("a", "3")
        db.close()
        db2 = TextDB(d)
        if db2.keys() != ["a", "b"] or db2.get("a") != "3":
            return False
        if db2.stats()["next_seq"] != 4 or db2.stats()["compactions"] != 0:
            return False
        db2.put("c", "4")
        return data_bytes(d).endswith(rec("P", 4, "c", "4"))

    check("reopen_state", reopen_state)

    # -- compaction ------------------------------------------------------

    comp_dir = newdir("compact")
    comp_db = [None]

    def compact_bytes_exact():
        db = TextDB(comp_dir)
        comp_db[0] = db
        db.put("a", "va")   # seq 1
        db.put("b", "vb")   # seq 2
        db.put("c", "vc")   # seq 3
        db.put("b", "vb2")  # seq 4
        db.delete("a")      # seq 5
        db.compact()
        return (
            data_bytes(comp_dir) == rec("P", 4, "b", "vb2") + rec("P", 3, "c", "vc")
            and db.keys() == ["b", "c"]
        )

    check("compact_bytes_exact", compact_bytes_exact)

    def compact_stats_and_files():
        db = comp_db[0]
        s = db.stats()
        names = sorted(p.name for p in comp_dir.iterdir())
        return (
            s == {"live_keys": 2, "data_records": 2, "journal_bytes": 0,
                  "next_seq": 6, "compactions": 1}
            and names == ["data.tdb", "journal.tdb"]
        )

    check("compact_stats_and_files", compact_stats_and_files)

    def compact_then_ops():
        db = comp_db[0]
        db.put("d", "vd")  # in-session next_seq: 6
        return (
            data_bytes(comp_dir)
            == rec("P", 4, "b", "vb2") + rec("P", 3, "c", "vc") + rec("P", 6, "d", "vd")
            and db.keys() == ["b", "c", "d"]
        )

    check("compact_then_ops", compact_then_ops)

    def compact_reopen_order():
        comp_db[0].close()
        db = TextDB(comp_dir)
        return (
            db.keys() == ["b", "c", "d"]
            and db.get("b") == "vb2"
            and db.stats()["next_seq"] == 7
            and db.stats()["compactions"] == 0
        )

    check("compact_reopen_order", compact_reopen_order)

    def compact_reopen_next_seq():
        d = newdir("compact2")
        db = TextDB(d)
        db.put("a", "1")  # seq 1
        db.put("b", "2")  # seq 2
        db.put("c", "3")  # seq 3
        db.delete("c")    # seq 4 — the largest seq, and compaction drops it
        db.compact()
        if db.stats()["next_seq"] != 5:  # unchanged in-session
            return False
        db.close()
        db2 = TextDB(d)
        if db2.stats()["next_seq"] != 3:  # recomputed from surviving records
            return False
        db2.put("d", "4")
        return data_bytes(d).endswith(rec("P", 3, "d", "4")) and db2.keys() == ["a", "b", "d"]

    check("compact_reopen_next_seq", compact_reopen_next_seq)

    def compact_empty_db():
        d = newdir("compact3")
        db = TextDB(d)
        db.put("a", "1")
        db.delete("a")
        db.compact()
        s = db.stats()
        if data_bytes(d) != b"" or s["live_keys"] != 0 or s["data_records"] != 0:
            return False
        if s["next_seq"] != 3 or s["compactions"] != 1:
            return False
        db.close()
        return TextDB(d).stats()["next_seq"] == 1

    check("compact_empty_db", compact_empty_db)

    # -- torn-write recovery --------------------------------------------

    base_data = rec("P", 1, "a", "1")

    rec_dir = newdir("rec1", data=base_data, journal=rec("P", 2, "b", "2") + commit(2))
    rec_db = [None]

    def recovery_committed_applied():
        db = TextDB(rec_dir)
        rec_db[0] = db
        return (
            db.get("b") == "2"
            and db.keys() == ["a", "b"]
            and data_bytes(rec_dir) == base_data + rec("P", 2, "b", "2")
            and journal_size(rec_dir) == 0
            and db.stats()["next_seq"] == 3
        )

    check("recovery_committed_applied", recovery_committed_applied)

    def recovery_next_seq():
        db = rec_db[0]
        db.put("c", "3")
        return data_bytes(rec_dir).endswith(rec("P", 3, "c", "3"))

    check("recovery_next_seq", recovery_next_seq)

    def recovery_uncommitted_discarded():
        d = newdir("rec2", data=base_data, journal=rec("P", 2, "b", "2"))
        db = TextDB(d)
        return (
            raises(lambda: db.get("b"), "KeyNotFoundError", "key not found: b")
            and data_bytes(d) == base_data
            and journal_size(d) == 0
            and db.stats()["next_seq"] == 2
        )

    check("recovery_uncommitted_discarded", recovery_uncommitted_discarded)

    def recovery_torn_record():
        torn = rec("P", 2, "b", "hello")[:-7]
        d = newdir("rec3", data=base_data, journal=torn)
        db = TextDB(d)
        return (
            db.keys() == ["a"]
            and data_bytes(d) == base_data
            and journal_size(d) == 0
        )

    check("recovery_torn_record", recovery_torn_record)

    def recovery_torn_commit():
        d = newdir("rec4", data=base_data, journal=rec("P", 2, "b", "2") + commit(2)[:10])
        db = TextDB(d)
        return db.keys() == ["a"] and data_bytes(d) == base_data and journal_size(d) == 0

    check("recovery_torn_commit", recovery_torn_commit)

    def recovery_second_torn():
        j = rec("P", 2, "b", "2") + commit(2) + rec("P", 3, "c", "3")[:20]
        d = newdir("rec5", data=base_data, journal=j)
        db = TextDB(d)
        return (
            db.keys() == ["a", "b"]
            and data_bytes(d) == base_data + rec("P", 2, "b", "2")
            and db.stats()["next_seq"] == 3
        )

    check("recovery_second_torn", recovery_second_torn)

    def recovery_prefix_rule():
        j = (rec("P", 2, "b", "2") + commit(2)
             + b"GARBAGE\n"
             + rec("P", 3, "c", "3") + commit(3))
        d = newdir("rec6", data=base_data, journal=j)
        db = TextDB(d)
        return (
            db.keys() == ["a", "b"]
            and data_bytes(d) == base_data + rec("P", 2, "b", "2")
            and journal_size(d) == 0
        )

    check("recovery_prefix_rule", recovery_prefix_rule)

    def recovery_bad_commit_crc():
        d = newdir("rec7", data=base_data, journal=rec("P", 2, "b", "2") + tamper(commit(2)))
        db = TextDB(d)
        return db.keys() == ["a"] and data_bytes(d) == base_data and journal_size(d) == 0

    check("recovery_bad_commit_crc", recovery_bad_commit_crc)

    def recovery_seq_mismatch():
        d = newdir("rec8", data=base_data, journal=rec("P", 2, "b", "2") + commit(3))
        db = TextDB(d)
        return db.keys() == ["a"] and data_bytes(d) == base_data and journal_size(d) == 0

    check("recovery_seq_mismatch", recovery_seq_mismatch)

    def recovery_idempotent():
        data = base_data + rec("P", 2, "b", "2")
        d = newdir("rec9", data=data, journal=rec("P", 2, "b", "2") + commit(2))
        db = TextDB(d)
        return (
            data_bytes(d) == data  # not re-appended
            and db.get("b") == "2"
            and journal_size(d) == 0
            and db.stats()["next_seq"] == 3
        )

    check("recovery_idempotent", recovery_idempotent)

    def recovery_delete_entry():
        d = newdir("rec10", data=base_data, journal=rec("D", 2, "a", "") + commit(2))
        db = TextDB(d)
        return (
            db.keys() == []
            and data_bytes(d) == base_data + rec("D", 2, "a", "")
            and db.stats() == {"live_keys": 0, "data_records": 2, "journal_bytes": 0,
                               "next_seq": 3, "compactions": 0}
        )

    check("recovery_delete_entry", recovery_delete_entry)

    # -- data-file corruption -------------------------------------------

    def corrupt_data_bad_crc():
        data = rec("P", 1, "a", "1") + tamper(rec("P", 2, "b", "2")) + rec("P", 3, "c", "3")
        d = newdir("cor1", data=data)
        return raises(lambda: TextDB(d), "CorruptRecordError", "corrupt record at line 2")

    check("corrupt_data_bad_crc", corrupt_data_bad_crc)

    def corrupt_data_torn_line():
        data = rec("P", 1, "a", "1") + rec("P", 2, "b", "2")[:-5]
        d = newdir("cor2", data=data)
        return raises(lambda: TextDB(d), "CorruptRecordError", "corrupt record at line 2")

    check("corrupt_data_torn_line", corrupt_data_torn_line)

    def corrupt_data_bad_framing():
        bad = bytearray(rec("P", 2, "kk", "vv"))
        bad[13:15] = b"03"  # klen lies about the key width
        d = newdir("cor3", data=rec("P", 1, "a", "1") + bytes(bad))
        if not raises(lambda: TextDB(d), "CorruptRecordError", "corrupt record at line 2"):
            return False
        d2 = newdir("cor4", data=rec("P", 1, "a", "1") + b"\n" + rec("P", 3, "c", "3"))
        return raises(lambda: TextDB(d2), "CorruptRecordError", "corrupt record at line 2")

    check("corrupt_data_bad_framing", corrupt_data_bad_framing)

    # -- close -----------------------------------------------------------

    def closed_semantics():
        d = newdir("closed")
        db = TextDB(d)
        db.put("a", "1")
        db.close()
        db.close()  # idempotent
        ops = [
            lambda: db.put("b", "2"), lambda: db.get("a"), lambda: db.delete("a"),
            lambda: db.keys(), lambda: db.find_value("1"), lambda: db.compact(),
            lambda: db.stats(),
        ]
        if not all(raises(op, "ClosedError", "database is closed") for op in ops):
            return False
        return TextDB(d).get("a") == "1"  # a fresh open still works

    check("closed_semantics", closed_semantics)

    # -- hardening: subtle-but-stated clauses ---------------------------

    def bad_value_order():
        db = TextDB(newdir("valorder"))
        # both newline-tainted AND too long: the newline complaint wins
        return raises(
            lambda: db.put("k", "\n" + "x" * 100005),
            "BadValueError", "invalid value: contains newline",
        )

    check("bad_value_order", bad_value_order)

    def recovery_commit_first():
        # a commit line where a record should be is a defect: scan stops dead
        j = commit(1) + rec("P", 2, "b", "2") + commit(2)
        d = newdir("rec11", data=base_data, journal=j)
        db = TextDB(d)
        return db.keys() == ["a"] and data_bytes(d) == base_data and journal_size(d) == 0

    check("recovery_commit_first", recovery_commit_first)

    def recovery_mismatch_then_valid():
        # first pair defective (commit seq mismatch): later valid pairs discarded
        j = rec("P", 2, "b", "2") + commit(9) + rec("P", 3, "c", "3") + commit(3)
        d = newdir("rec12", data=base_data, journal=j)
        db = TextDB(d)
        return db.keys() == ["a"] and data_bytes(d) == base_data and journal_size(d) == 0

    check("recovery_mismatch_then_valid", recovery_mismatch_then_valid)

    def unicode_reopen_parse():
        val = "héllo\U0001f389"
        d = newdir("uniread", data=rec("P", 1, "u", val))
        db = TextDB(d)
        return db.get("u") == val and db.keys() == ["u"] and db.stats()["data_records"] == 1

    check("unicode_reopen_parse", unicode_reopen_parse)

    def journal_unicode_entry():
        val = "héllo\U0001f389"
        j = rec("P", 2, "u", val) + commit(2)
        d = newdir("unijournal", data=base_data, journal=j)
        db = TextDB(d)
        return (
            db.get("u") == val
            and data_bytes(d) == base_data + rec("P", 2, "u", val)
            and db.stats()["next_seq"] == 3
        )

    check("journal_unicode_entry", journal_unicode_entry)

    def find_value_after_recovery():
        data = rec("P", 1, "a", "x") + rec("P", 2, "b", "y")
        j = rec("P", 3, "c", "x") + commit(3)
        d = newdir("idxrec", data=data, journal=j)
        db = TextDB(d)
        return db.find_value("x") == ["a", "c"] and db.find_value("y") == ["b"]

    check("find_value_after_recovery", find_value_after_recovery)


if __name__ == "__main__":
    main()
