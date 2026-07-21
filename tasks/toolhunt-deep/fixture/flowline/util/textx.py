"""Text helpers for identifiers and labels."""


def slugify(label):
    """Lower-case *label* and collapse runs of non-alphanumerics to `-`."""
    out = []
    previous_dash = False
    for char in str(label).lower():
        if char.isalnum():
            out.append(char)
            previous_dash = False
        elif not previous_dash:
            out.append("-")
            previous_dash = True
    return "".join(out).strip("-")


def truncate(text, limit=80, ellipsis="..."):
    """Clip *text* to *limit* characters, appending *ellipsis* when clipped."""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(ellipsis))] + ellipsis
