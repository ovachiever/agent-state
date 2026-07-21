"""Exception hierarchy for the engine."""


class FlowlineError(Exception):
    """Base class for engine failures."""


class ReaderError(FlowlineError):
    """Raised when an input source cannot be parsed."""


class SinkError(FlowlineError):
    """Raised when an output target rejects rows."""


class RegistryError(FlowlineError):
    """Raised when a step key cannot be resolved to a callable."""
