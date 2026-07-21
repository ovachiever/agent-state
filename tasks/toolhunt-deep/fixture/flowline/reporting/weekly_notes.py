"""Free-form notes appended to the weekly digest email."""


def render_notes(notes):
    """Bulleted plain-text block from a list of note strings."""
    return "\n".join(f"  * {note.strip()}" for note in notes if note.strip())
