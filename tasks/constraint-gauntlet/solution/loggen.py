"""loggen: deterministic synthetic log generator for the onboarding workshop."""

import argparse
import datetime
import json
import random
import sys

MESSAGES = [
    "cache warmed",
    "connection pool resized",
    "checkpoint written",
    "queue depth nominal",
    "handshake accepted",
    "retention sweep complete",
]

EPOCH = datetime.datetime(2026, 1, 1, 0, 0, 0)


def build_lines(count, level, seed, fmt):
    rng = random.Random(seed) if seed is not None else random.Random()
    lines = []
    for i in range(count):
        ts = (EPOCH + datetime.timedelta(seconds=i)).isoformat(timespec="seconds")
        msg = rng.choice(MESSAGES)
        if fmt == "json":
            lines.append(json.dumps({"ts": ts, "level": level, "msg": msg}))
        else:
            lines.append(f"[{ts}] {level.upper().ljust(5)} {msg}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog="loggen")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--level", choices=["debug", "info", "warn", "error"], default="info")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--format", choices=["text", "json"], default="text", dest="fmt")
    parser.add_argument("--version", action="version", version="loggen 1.4.2")
    args = parser.parse_args(argv)
    if args.count < 0:
        print("error: count must be >= 0", file=sys.stderr)
        return 3
    for line in build_lines(args.count, args.level, args.seed, args.fmt):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
