"""Hidden verifier for gauntlet-protocol. Usage: verify.py <workspace>"""

import ast
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

ALL_CHECKS = [
    "file_exists", "stdlib_only", "import_no_side_effects", "encode_basic_exact",
    "encode_escapes_exact", "encode_empty_field", "encode_unicode_length",
    "encode_errors", "encode_body_too_long", "decode_basic", "decode_escapes",
    "decode_missing_start", "decode_truncated_no_hash", "decode_bad_length_basic",
    "decode_bad_length_leading_zero", "decode_bad_length_unicode",
    "decode_length_too_large", "decode_truncated_body", "decode_missing_terminator",
    "decode_trailing_data", "decode_bad_escape", "decode_dangling_escape",
    "decode_unescaped_delimiter", "roundtrip_adversarial", "decoder_partial_feed",
    "decoder_multi_frame", "decoder_char_by_char", "decoder_escape_boundary",
    "decoder_poisoned", "decoder_lazy_validation", "decoder_close_lifecycle",
    "decoder_close_incomplete_recovery",
    "cli_version", "cli_encode", "cli_decode_success", "cli_decode_malformed",
    "cli_decode_incomplete", "cli_usage_errors",
]

PAYLOADS = [
    [""],
    ["", ""],
    ["", "", ""],
    ["a", "", "b"],
    [","],
    [";"],
    ["\\"],
    ["\\c"],
    ["\\\\"],
    ["\\;"],
    ["end\\"],
    ["\\n"],
    ["\n"],
    ["line1\nline2"],
    ["a,b", "c;d"],
    ["#"],
    ["#5#ab;"],
    [",,,"],
    ["ünïcødé"],
    ["🎉🎊", "emoji"],
    ["café €"],
    [" padded  "],
    ["x" * 500],
    ["mix\\,;\n#", "", ";,\\"],
]


def main():
    checks = {name: False for name in ALL_CHECKS}
    try:
        run_checks(checks)
    except Exception:
        pass
    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


def run_checks(checks):
    ws = Path(sys.argv[1]).resolve()
    script = ws / "wireproto.py"
    checks["file_exists"] = script.exists()
    if not script.exists():
        return

    try:
        tree = ast.parse(script.read_text(errors="replace"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        checks["stdlib_only"] = imported <= set(sys.stdlib_module_names)
    except SyntaxError:
        checks["stdlib_only"] = False

    def cli(*args, stdin="", timeout=20):
        return subprocess.run(
            [sys.executable, str(script), *args],
            input=stdin, capture_output=True, text=True, timeout=timeout,
        )

    # -- import ---------------------------------------------------------

    spec = importlib.util.spec_from_file_location("wireproto", script)
    mod = importlib.util.module_from_spec(spec)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            spec.loader.exec_module(mod)
    except Exception:
        return
    checks["import_no_side_effects"] = (
        buf.getvalue() == ""
        and callable(getattr(mod, "encode", None))
        and callable(getattr(mod, "decode", None))
        and isinstance(getattr(mod, "Decoder", None), type)
    )
    encode, decode, Decoder = mod.encode, mod.decode, mod.Decoder

    def check(name, fn):
        try:
            checks[name] = bool(fn())
        except Exception:
            checks[name] = False

    def err(fn, msg):
        try:
            fn()
        except ValueError as e:
            return str(e) == msg
        except Exception:
            return False
        return False

    # -- encode ---------------------------------------------------------

    check("encode_basic_exact", lambda: (
        encode(["x", "y"]) == "#3#x,y;"
        and encode(["hello"]) == "#5#hello;"
    ))

    check("encode_escapes_exact", lambda: (
        encode(["a,b"]) == "#4#a\\cb;"
        and encode([";"]) == "#2#\\s;"
        and encode(["\\"]) == "#2#\\\\;"
        and encode(["\n"]) == "#2#\\n;"
        and encode(["#"]) == "#1##;"
        and encode(["a b"]) == "#3#a b;"
    ))

    check("encode_empty_field", lambda: (
        encode([""]) == "#0#;" and encode(["", ""]) == "#1#,;"
    ))

    check("encode_unicode_length", lambda: (
        encode(["🎉"]) == "#1#🎉;" and encode(["café €"]) == "#6#café €;"
    ))

    check("encode_errors", lambda: (
        err(lambda: encode("ab"), "encode: fields must be a list")
        and err(lambda: encode(("a",)), "encode: fields must be a list")
        and err(lambda: encode([]), "encode: need at least one field")
        and err(lambda: encode(["a", 5, 6]), "encode: field 1 is not a str")
        and err(lambda: encode([None]), "encode: field 0 is not a str")
    ))

    check("encode_body_too_long", lambda: (
        err(lambda: encode(["x" * 100000]), "encode: body too long")
        and encode(["x" * 99999]) == "#99999#" + "x" * 99999 + ";"
    ))

    # -- decode ---------------------------------------------------------

    check("decode_basic", lambda: (
        decode("#3#x,y;") == ["x", "y"]
        and decode("#0#;") == [""]
        and decode("#1#,;") == ["", ""]
        and decode("#5#hello;") == ["hello"]
    ))

    check("decode_escapes", lambda: (
        decode("#4#a\\cb;") == ["a,b"]
        and decode("#2#\\s;") == [";"]
        and decode("#2#\\n;") == ["\n"]
        and decode("#2#\\\\;") == ["\\"]
        and decode("#1##;") == ["#"]
    ))

    check("decode_missing_start", lambda: (
        err(lambda: decode(""), "decode: missing frame start")
        and err(lambda: decode("x#0#;"), "decode: missing frame start")
    ))

    check("decode_truncated_no_hash", lambda: (
        err(lambda: decode("#123"), "decode: truncated frame")
        and err(lambda: decode("#"), "decode: truncated frame")
    ))

    check("decode_bad_length_basic", lambda: (
        err(lambda: decode("##a;"), "decode: bad length")
        and err(lambda: decode("#1a#ab;"), "decode: bad length")
        and err(lambda: decode("#-1#;"), "decode: bad length")
    ))

    check("decode_bad_length_leading_zero", lambda: (
        err(lambda: decode("#07#abcdefg;"), "decode: bad length")
        and err(lambda: decode("#00#;"), "decode: bad length")
    ))

    check("decode_bad_length_unicode", lambda: (
        err(lambda: decode("#١#a;"), "decode: bad length")
        and err(lambda: decode("#²#a;"), "decode: bad length")
    ))

    check("decode_length_too_large", lambda: (
        err(lambda: decode("#100000#"), "decode: length too large")
        and err(lambda: decode("#999999#x;"), "decode: length too large")
    ))

    check("decode_truncated_body", lambda: (
        err(lambda: decode("#5#ab"), "decode: truncated frame")
        and err(lambda: decode("#2#ab"), "decode: truncated frame")
    ))

    check("decode_missing_terminator", lambda: (
        err(lambda: decode("#2#abX"), "decode: missing terminator")
        and err(lambda: decode("#0#x"), "decode: missing terminator")
    ))

    check("decode_trailing_data", lambda: (
        err(lambda: decode("#1#a;;"), "decode: trailing data")
        and err(lambda: decode("#2#;;;;"), "decode: trailing data")
        and err(lambda: decode("#0#;#0#;"), "decode: trailing data")
    ))

    check("decode_bad_escape", lambda: (
        err(lambda: decode("#2#\\x;"), "decode: bad escape")
        and err(lambda: decode("#3#a\\;;"), "decode: bad escape")
        and err(lambda: decode("#2#\\C;"), "decode: bad escape")
    ))

    check("decode_dangling_escape", lambda: (
        err(lambda: decode("#2#a\\;"), "decode: dangling escape")
        and err(lambda: decode("#1#\\;"), "decode: dangling escape")
    ))

    check("decode_unescaped_delimiter", lambda: (
        err(lambda: decode("#1#\n;"), "decode: unescaped delimiter")
        and err(lambda: decode("#1#;;"), "decode: unescaped delimiter")
        and err(lambda: decode("#3#a;b;"), "decode: unescaped delimiter")
    ))

    check("roundtrip_adversarial", lambda: all(
        decode(encode(list(p))) == list(p) for p in PAYLOADS
    ))

    # -- Decoder state machine ------------------------------------------

    def decoder_partial_feed():
        d = Decoder()
        if d.feed("#5#ab") != [] or d.pending() != 5:
            return False
        if d.feed("c,d") != [] or d.pending() != 8:
            return False
        return d.feed(";") == [["abc", "d"]] and d.pending() == 0

    check("decoder_partial_feed", decoder_partial_feed)

    def decoder_multi_frame():
        d = Decoder()
        out = d.feed("#1#a;#1#b;#2#")
        return out == [["a"], ["b"]] and d.pending() == 3

    check("decoder_multi_frame", decoder_multi_frame)

    def decoder_char_by_char():
        stream = encode(["a,b", ""]) + encode(["🎉;"]) + encode(["\\", "x\ny"])
        d = Decoder()
        got = []
        for ch in stream:
            got.extend(d.feed(ch))
        return got == [["a,b", ""], ["🎉;"], ["\\", "x\ny"]] and d.pending() == 0

    check("decoder_char_by_char", decoder_char_by_char)

    def decoder_escape_boundary():
        d = Decoder()
        if d.feed("#4#a\\") != [] or d.pending() != 5:
            return False
        return d.feed("cb;") == [["a,b"]] and d.pending() == 0

    check("decoder_escape_boundary", decoder_escape_boundary)

    def decoder_poisoned():
        d = Decoder()
        if not err(lambda: d.feed("#1#a;x"), "decode: missing frame start"):
            return False
        if not err(lambda: d.feed("#1#a;"), "feed: decoder is poisoned"):
            return False
        return err(lambda: d.close(), "close: decoder is poisoned")

    check("decoder_poisoned", decoder_poisoned)

    def decoder_lazy_validation():
        d1 = Decoder()
        if d1.feed("#00") != [] or d1.pending() != 3:
            return False
        if not err(lambda: d1.feed("#"), "decode: bad length"):
            return False
        d2 = Decoder()
        if d2.feed("#2#ab") != [] or d2.pending() != 5:
            return False
        return err(lambda: d2.feed("X"), "decode: missing terminator")

    check("decoder_lazy_validation", decoder_lazy_validation)

    def decoder_close_lifecycle():
        d = Decoder()
        if d.feed("#1#a;") != [["a"]]:
            return False
        if d.close() is not None or d.close() is not None:
            return False
        return err(lambda: d.feed("x"), "feed: decoder is closed")

    check("decoder_close_lifecycle", decoder_close_lifecycle)

    def decoder_close_incomplete_recovery():
        d = Decoder()
        d.feed("#3#")
        if not err(lambda: d.close(), "close: incomplete frame"):
            return False
        # a failed close leaves the decoder open
        if d.feed("abc;") != [["abc"]]:
            return False
        return d.close() is None

    check("decoder_close_incomplete_recovery", decoder_close_incomplete_recovery)

    # -- CLI ------------------------------------------------------------

    def cli_version():
        r = cli("--version")
        return r.returncode == 0 and r.stdout == "wireproto 1.4.2\n" and r.stderr == ""

    check("cli_version", cli_version)

    def cli_encode():
        r = cli("encode", "a,b", "c")
        if not (r.returncode == 0 and r.stdout == "#6#a\\cb,c;\n" and r.stderr == ""):
            return False
        r2 = cli("encode")
        return (
            r2.returncode == 2
            and r2.stdout == ""
            and r2.stderr.strip() == "error: need at least one field"
        )

    check("cli_encode", cli_encode)

    def cli_decode_success():
        r = cli("decode", stdin="#1#a;#3#b,c;")
        if not (r.returncode == 0 and r.stdout == "a\nb,c\n" and r.stderr == ""):
            return False
        r2 = cli("decode", stdin="#4#a\\cb;")
        if not (r2.returncode == 0 and r2.stdout == "a\\cb\n" and r2.stderr == ""):
            return False
        r3 = cli("decode", stdin="")
        return r3.returncode == 0 and r3.stdout == "" and r3.stderr == ""

    check("cli_decode_success", cli_decode_success)

    def cli_decode_malformed():
        r = cli("decode", stdin="#1#a;garbage")
        return (
            r.returncode == 3
            and r.stdout == ""
            and r.stderr.strip() == "error: decode: missing frame start"
        )

    check("cli_decode_malformed", cli_decode_malformed)

    def cli_decode_incomplete():
        r = cli("decode", stdin="#5#ab")
        return (
            r.returncode == 4
            and r.stdout == ""
            and r.stderr.strip() == "error: close: incomplete frame"
        )

    check("cli_decode_incomplete", cli_decode_incomplete)

    def cli_usage_errors():
        usage = "error: usage: wireproto.py {encode,decode,--version}"
        for args in ([], ["frobnicate"], ["decode", "extra"], ["--version", "extra"]):
            r = cli(*args, stdin="")
            if not (r.returncode == 2 and r.stdout == "" and r.stderr.strip() == usage):
                return False
        return True

    check("cli_usage_errors", cli_usage_errors)


if __name__ == "__main__":
    main()
