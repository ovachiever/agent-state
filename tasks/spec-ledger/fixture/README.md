# Ledger toolkit

Pure functions over a double-entry ledger. No I/O, no globals mutated, no
mutation of any argument, standard library only.

**Money is `decimal.Decimal`, always.** Every amount that enters or leaves
these functions is a `Decimal` quantized to exactly 2 decimal places
(cent-exact). Float arithmetic on money is forbidden anywhere in the module —
binary floats cannot represent cents and this spec treats any float money as
a defect, even when the rounded result happens to look right.

## Data model

A **transaction** is a dict:

```python
{"date": "2026-03-04", "memo": "Office chairs", "entries": [entry, ...]}
```

An **entry** is a dict: `{"account": "assets:cash", "amount": Decimal("-180.25")}`.
Positive amounts are debits, negative amounts are credits. A **ledger** is a
list of transactions in posting order.

The sample ledger used by every example below:

```python
SAMPLE = [
    {"date": "2026-03-01", "memo": "Opening balance", "entries": [
        {"account": "assets:cash", "amount": Decimal("500.00")},
        {"account": "equity:opening", "amount": Decimal("-500.00")},
    ]},
    {"date": "2026-03-04", "memo": "Office chairs", "entries": [
        {"account": "expenses:furniture", "amount": Decimal("180.25")},
        {"account": "assets:cash", "amount": Decimal("-180.25")},
    ]},
    {"date": "2026-03-09", "memo": "Client payment, invoice 44", "entries": [
        {"account": "assets:cash", "amount": Decimal("320.00")},
        {"account": "income:consulting", "amount": Decimal("-320.00")},
    ]},
]
```

## Required functions (all twelve)

### 1. `parse_amount(s)`
Parse a money string into a `Decimal` quantized to 2 decimal places. Strip
surrounding whitespace first. The stripped text must be an optional leading
`-`, one or more digits, then optionally a `.` followed by one or two digits:
`"42"` → `Decimal("42.00")`, `"42.5"` → `Decimal("42.50")`, `"-7.25"` →
`Decimal("-7.25")`, `" 3.10 "` → `Decimal("3.10")`. Everything else raises
`ValueError`: empty string, `"1.234"` (too many decimals), `"1,000"`, `"$5"`,
`"+5"`, `"5."`, `".5"`.

### 2. `format_amount(d)`
`Decimal` → string with exactly 2 decimal places, no thousands separators,
leading `-` for negatives: `Decimal("3")` → `"3.00"`, `Decimal("-7.25")` →
`"-7.25"`, `Decimal("1234.5")` → `"1234.50"`. Negative zero normalizes:
`Decimal("-0.00")` → `"0.00"`.

### 3. `normalize_account(name)`
Account names are colon-separated segments. Strip whitespace around each
segment and lowercase it; join back with `:`. After lowercasing, every segment
must match `[a-z0-9][a-z0-9-]*` (starts alphanumeric, then alphanumerics and
hyphens only). `" Assets : Cash "` → `"assets:cash"`,
`"Expenses:Office-Supplies"` → `"expenses:office-supplies"`. Anything else
raises `ValueError`: empty string, empty segment (`"assets:"`, `":cash"`,
`"a::b"`), inner spaces (`"assets:petty cash"`), illegal characters
(`"assets:_x"`), segment starting with a hyphen (`"-cash"`).

### 4. `validate_transaction(txn)`
Return a bool; never raise, no matter how malformed the input (wrong type,
missing keys, garbage values — all just `False`). Returns `True` iff ALL of:

- `txn` is a dict whose `"date"` is a string in `YYYY-MM-DD` form naming a
  real calendar date (`"2026-02-30"` and `"2026-3-01"` are both invalid);
- `"memo"` is a non-empty string;
- `"entries"` is a list of at least 2 entries;
- every entry is a dict with a non-empty string `"account"` and an
  `"amount"` that is a `Decimal` (an int or float amount fails) and is not
  zero;
- the amounts sum to exactly zero (the double-entry invariant).

### 5. `post(ledger, txn)`
Validate `txn` with the rules of section 4; if invalid raise `ValueError`.
Otherwise return a **new** list: the original transactions in order, then
`txn` appended. Never mutate the `ledger` argument (the returned list is a
different object).

### 6. `account_balance(ledger, account, as_of=None)`
Sum of all entry amounts whose account equals `account` exactly, returned as
a `Decimal` quantized to 2 places. When `as_of` (a `YYYY-MM-DD` string) is
given, include only transactions with `date <= as_of` (inclusive). An account
with no entries yields `Decimal("0.00")`.
`account_balance(SAMPLE, "assets:cash")` → `Decimal("639.75")`;
with `as_of="2026-03-04"` → `Decimal("319.75")`.

### 7. `running_balance(ledger, account)`
Walk the transactions sorted by date ascending — the sort must be stable, so
transactions sharing a date keep their ledger order. For each transaction with
at least one entry for `account`, net that transaction's entries for the
account into one amount and append the tuple `(date, cumulative_balance)`
with the balance quantized to 2 places. Transactions not touching the account
produce no tuple. No matches at all → `[]`.
`running_balance(SAMPLE, "assets:cash")` →
`[("2026-03-01", Decimal("500.00")), ("2026-03-04", Decimal("319.75")), ("2026-03-09", Decimal("639.75"))]`.

### 8. `trial_balance(ledger)`
List of `(account, balance)` tuples covering **every** account that appears
anywhere in the ledger — including accounts whose balance nets to zero —
sorted by account name ascending, each balance a `Decimal` quantized to
2 places. Empty ledger → `[]`.

### 9. `filter_window(ledger, start, end)`
Transactions with `start <= date <= end`, both bounds inclusive, as a new
list preserving ledger order. `start` and `end` must each be a valid
`YYYY-MM-DD` calendar date or `ValueError` is raised. If `start > end`,
return `[]` (not an error).

### 10. `render_statement(ledger, account)`
A fixed-width plain-text statement, lines joined with `\n`, **no trailing
newline**. Line 1 is `Statement: ` plus the account. Line 2 is the column
header. Then one row per transaction touching the account, in the same order
and with the same per-transaction netting as `running_balance`. Last line is
`Ending balance: ` plus the ending balance via `format_amount` (an account
with no rows still gets line 1, the header, and `Ending balance: 0.00`).

Column layout for header and rows: date left-justified to width 10, two
spaces, memo truncated to its first 22 characters then left-justified to
width 22, amount right-justified to width 10, two spaces, balance
right-justified to width 10. Amount is the transaction's net for the account
and balance the cumulative balance, both via `format_amount`.

`render_statement(SAMPLE, "assets:cash")` returns character-for-character:

```
Statement: assets:cash
Date        Memo                      Amount     Balance
2026-03-01  Opening balance           500.00      500.00
2026-03-04  Office chairs            -180.25      319.75
2026-03-09  Client payment, invoic    320.00      639.75
Ending balance: 639.75
```

### 11. `to_csv(ledger)`
Header line `date,memo,account,amount`, then one row per **entry** —
transactions in ledger order, entries in their order within each transaction
— with the amount rendered via `format_amount`. A field containing a comma,
double quote, or newline is wrapped in double quotes with inner double quotes
doubled; all other fields are unquoted. Lines joined with `\n`, no trailing
newline. Empty ledger → just the header. `to_csv(SAMPLE)` returns exactly:

```
date,memo,account,amount
2026-03-01,Opening balance,assets:cash,500.00
2026-03-01,Opening balance,equity:opening,-500.00
2026-03-04,Office chairs,expenses:furniture,180.25
2026-03-04,Office chairs,assets:cash,-180.25
2026-03-09,"Client payment, invoice 44",assets:cash,320.00
2026-03-09,"Client payment, invoice 44",income:consulting,-320.00
```

### 12. `sum_debits_credits(ledger)`
Tuple `(debits, credits)`: `debits` is the sum of all positive entry amounts,
`credits` the sum of the absolute values of all negative entry amounts, both
`Decimal` quantized to 2 places. Empty ledger →
`(Decimal("0.00"), Decimal("0.00"))`. For a ledger of balanced transactions
the two are equal: `sum_debits_credits(SAMPLE)` →
`(Decimal("1000.25"), Decimal("1000.25"))`.
