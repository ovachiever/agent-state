"""Run context threaded through pipeline stages."""


class RunContext:
    """Carries run id, dry-run flag, and accumulated warnings."""

    def __init__(self, run_id, dry_run=False):
        self.run_id = run_id
        self.dry_run = dry_run
        self.warnings = []

    def warn(self, message):
        self.warnings.append(str(message))
        return message
