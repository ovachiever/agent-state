"""Tiny formatting helpers shared by the report renderers."""


def align_columns(pairs, gap=2):
    """Left-align `(label, value)` pairs into two tidy columns."""
    if not pairs:
        return ""
    width = max(len(str(label)) for label, _ in pairs) + gap
    return "\n".join(f"{str(label).ljust(width)}{value}" for label, value in pairs)
