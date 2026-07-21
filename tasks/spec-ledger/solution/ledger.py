"""Double-entry ledger toolkit. See README.md for the full specification."""

import re
from datetime import date
from decimal import Decimal

CENT = Decimal("0.01")

_AMOUNT_RE = re.compile(r"^-?\d+(\.\d{1,2})?$")
_SEGMENT_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_amount(s):
    """See README section 1."""
    if not isinstance(s, str):
        raise ValueError(f"not a string: {s!r}")
    text = s.strip()
    if not _AMOUNT_RE.match(text):
        raise ValueError(f"bad amount: {s!r}")
    return Decimal(text).quantize(CENT)


def format_amount(d):
    """See README section 2."""
    q = d.quantize(CENT)
    if q == 0:
        q = abs(q)
    return f"{q:.2f}"


def normalize_account(name):
    """See README section 3."""
    if not isinstance(name, str):
        raise ValueError(f"not a string: {name!r}")
    segments = [seg.strip().lower() for seg in name.split(":")]
    if not all(_SEGMENT_RE.match(seg) for seg in segments):
        raise ValueError(f"bad account name: {name!r}")
    return ":".join(segments)


def _valid_date(s):
    if not isinstance(s, str) or not _DATE_RE.match(s):
        return False
    year, month, day = (int(part) for part in s.split("-"))
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def validate_transaction(txn):
    """See README section 4."""
    try:
        if not isinstance(txn, dict):
            return False
        if not _valid_date(txn.get("date")):
            return False
        memo = txn.get("memo")
        if not isinstance(memo, str) or not memo:
            return False
        entries = txn.get("entries")
        if not isinstance(entries, list) or len(entries) < 2:
            return False
        total = Decimal("0")
        for entry in entries:
            if not isinstance(entry, dict):
                return False
            account = entry.get("account")
            amount = entry.get("amount")
            if not isinstance(account, str) or not account:
                return False
            if not isinstance(amount, Decimal) or amount == 0:
                return False
            total += amount
        return total == 0
    except Exception:
        return False


def post(ledger, txn):
    """See README section 5."""
    if not validate_transaction(txn):
        raise ValueError("invalid transaction")
    return [*ledger, txn]


def account_balance(ledger, account, as_of=None):
    """See README section 6."""
    total = Decimal("0")
    for txn in ledger:
        if as_of is not None and txn["date"] > as_of:
            continue
        for entry in txn["entries"]:
            if entry["account"] == account:
                total += entry["amount"]
    return total.quantize(CENT)


def _by_date(ledger):
    return sorted(ledger, key=lambda txn: txn["date"])


def running_balance(ledger, account):
    """See README section 7."""
    rows = []
    total = Decimal("0")
    for txn in _by_date(ledger):
        matched = [e["amount"] for e in txn["entries"] if e["account"] == account]
        if not matched:
            continue
        total += sum(matched, Decimal("0"))
        rows.append((txn["date"], total.quantize(CENT)))
    return rows


def trial_balance(ledger):
    """See README section 8."""
    totals = {}
    for txn in ledger:
        for entry in txn["entries"]:
            totals[entry["account"]] = totals.get(entry["account"], Decimal("0")) + entry["amount"]
    return [(account, totals[account].quantize(CENT)) for account in sorted(totals)]


def filter_window(ledger, start, end):
    """See README section 9."""
    if not _valid_date(start) or not _valid_date(end):
        raise ValueError("invalid window bounds")
    return [txn for txn in ledger if start <= txn["date"] <= end]


def render_statement(ledger, account):
    """See README section 10."""
    lines = [
        f"Statement: {account}",
        "Date".ljust(10) + "  " + "Memo".ljust(22)
        + "Amount".rjust(10) + "  " + "Balance".rjust(10),
    ]
    total = Decimal("0")
    for txn in _by_date(ledger):
        matched = [e["amount"] for e in txn["entries"] if e["account"] == account]
        if not matched:
            continue
        net = sum(matched, Decimal("0")).quantize(CENT)
        total += net
        lines.append(
            txn["date"].ljust(10) + "  " + txn["memo"][:22].ljust(22)
            + format_amount(net).rjust(10) + "  " + format_amount(total).rjust(10)
        )
    lines.append(f"Ending balance: {format_amount(total)}")
    return "\n".join(lines)


def _csv_field(value):
    if any(ch in value for ch in ',"\n'):
        return '"' + value.replace('"', '""') + '"'
    return value


def to_csv(ledger):
    """See README section 11."""
    lines = ["date,memo,account,amount"]
    for txn in ledger:
        for entry in txn["entries"]:
            lines.append(",".join([
                _csv_field(txn["date"]),
                _csv_field(txn["memo"]),
                _csv_field(entry["account"]),
                _csv_field(format_amount(entry["amount"])),
            ]))
    return "\n".join(lines)


def sum_debits_credits(ledger):
    """See README section 12."""
    debits = Decimal("0")
    credits = Decimal("0")
    for txn in ledger:
        for entry in txn["entries"]:
            if entry["amount"] > 0:
                debits += entry["amount"]
            else:
                credits += -entry["amount"]
    return (debits.quantize(CENT), credits.quantize(CENT))
