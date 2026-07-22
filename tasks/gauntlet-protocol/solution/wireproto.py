"""wireproto — text wire-protocol encoder/decoder. Reference implementation."""

import sys

VERSION = "wireproto 1.4.2"
USAGE = "error: usage: wireproto.py {encode,decode,--version}"

_ESCAPES = {"\\": "\\\\", ",": "\\c", ";": "\\s", "\n": "\\n"}
_UNESCAPES = {"\\": "\\", "c": ",", "s": ";", "n": "\n"}
_DIGITS = set("0123456789")
MAX_LEN = 99999


def _escape_field(field):
    return "".join(_ESCAPES.get(ch, ch) for ch in field)


def encode(fields):
    if not isinstance(fields, list):
        raise ValueError("encode: fields must be a list")
    if not fields:
        raise ValueError("encode: need at least one field")
    for i, f in enumerate(fields):
        if not isinstance(f, str):
            raise ValueError(f"encode: field {i} is not a str")
    body = ",".join(_escape_field(f) for f in fields)
    if len(body) > MAX_LEN:
        raise ValueError("encode: body too long")
    return f"#{len(body)}#{body};"


def _check_length_field(run):
    if not run or any(c not in _DIGITS for c in run):
        raise ValueError("decode: bad length")
    if len(run) > 1 and run[0] == "0":
        raise ValueError("decode: bad length")
    value = int(run)
    if value > MAX_LEN:
        raise ValueError("decode: length too large")
    return value


def _parse_body(body):
    fields = []
    cur = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == "\\":
            if i + 1 >= n:
                raise ValueError("decode: dangling escape")
            nxt = body[i + 1]
            if nxt not in _UNESCAPES:
                raise ValueError("decode: bad escape")
            cur.append(_UNESCAPES[nxt])
            i += 2
        elif ch == ";" or ch == "\n":
            raise ValueError("decode: unescaped delimiter")
        elif ch == ",":
            fields.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(ch)
            i += 1
    fields.append("".join(cur))
    return fields


def decode(text):
    if not text or text[0] != "#":
        raise ValueError("decode: missing frame start")
    end = text.find("#", 1)
    if end == -1:
        raise ValueError("decode: truncated frame")
    length = _check_length_field(text[1:end])
    term = end + 1 + length
    if len(text) < term + 1:
        raise ValueError("decode: truncated frame")
    if text[term] != ";":
        raise ValueError("decode: missing terminator")
    if len(text) > term + 1:
        raise ValueError("decode: trailing data")
    return _parse_body(text[end + 1:term])


class Decoder:
    """Incremental stream decoder: open -> (closed | poisoned)."""

    def __init__(self):
        self._buf = ""
        self._state = "open"

    def feed(self, chunk):
        if self._state == "poisoned":
            raise ValueError("feed: decoder is poisoned")
        if self._state == "closed":
            raise ValueError("feed: decoder is closed")
        self._buf += chunk
        frames = []
        try:
            while True:
                fields = self._try_extract()
                if fields is None:
                    break
                frames.append(fields)
        except ValueError:
            self._state = "poisoned"
            raise
        return frames

    def _try_extract(self):
        buf = self._buf
        if not buf:
            return None
        if buf[0] != "#":
            raise ValueError("decode: missing frame start")
        end = buf.find("#", 1)
        if end == -1:
            return None
        length = _check_length_field(buf[1:end])
        term = end + 1 + length
        if len(buf) < term + 1:
            return None
        if buf[term] != ";":
            raise ValueError("decode: missing terminator")
        fields = _parse_body(buf[end + 1:term])
        self._buf = buf[term + 1:]
        return fields

    def pending(self):
        return len(self._buf)

    def close(self):
        if self._state == "poisoned":
            raise ValueError("close: decoder is poisoned")
        if self._state == "closed":
            return None
        if self._buf:
            raise ValueError("close: incomplete frame")
        self._state = "closed"
        return None


def main(argv):
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "--version":
        if len(argv) != 1:
            print(USAGE, file=sys.stderr)
            return 2
        print(VERSION)
        return 0
    if cmd == "encode":
        fields = argv[1:]
        if not fields:
            print("error: need at least one field", file=sys.stderr)
            return 2
        try:
            print(encode(list(fields)))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 3
        return 0
    if cmd == "decode":
        if len(argv) != 1:
            print(USAGE, file=sys.stderr)
            return 2
        data = sys.stdin.read()
        dec = Decoder()
        try:
            frames = dec.feed(data)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 3
        try:
            dec.close()
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 4
        for fields in frames:
            print(",".join(_escape_field(f) for f in fields))
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
