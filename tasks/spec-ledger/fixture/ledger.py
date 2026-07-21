"""Double-entry ledger toolkit. See README.md for the full specification."""


def parse_amount(s):
    """See README section 1."""
    raise NotImplementedError


def format_amount(d):
    """See README section 2."""
    raise NotImplementedError


def normalize_account(name):
    """See README section 3."""
    raise NotImplementedError


def validate_transaction(txn):
    """See README section 4."""
    raise NotImplementedError


def post(ledger, txn):
    """See README section 5."""
    raise NotImplementedError


def account_balance(ledger, account, as_of=None):
    """See README section 6."""
    raise NotImplementedError


def running_balance(ledger, account):
    """See README section 7."""
    raise NotImplementedError


def trial_balance(ledger):
    """See README section 8."""
    raise NotImplementedError


def filter_window(ledger, start, end):
    """See README section 9."""
    raise NotImplementedError


def render_statement(ledger, account):
    """See README section 10."""
    raise NotImplementedError


def to_csv(ledger):
    """See README section 11."""
    raise NotImplementedError


def sum_debits_credits(ledger):
    """See README section 12."""
    raise NotImplementedError
