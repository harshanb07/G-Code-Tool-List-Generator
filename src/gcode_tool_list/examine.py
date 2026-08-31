"""Legacy-compatible line filtering for Examine mode."""


def filter_lines(
    source_text: str,
    search_text: str,
    case_sensitive: bool = False,
) -> str:
    """Return source lines containing the literal search text."""
    if not search_text:
        return ""

    needle = search_text if case_sensitive else search_text.casefold()
    matching_lines: list[str] = []

    for line in source_text.splitlines(keepends=True):
        haystack = line if case_sensitive else line.casefold()
        if needle in haystack:
            matching_lines.append(line)

    return "".join(matching_lines)
