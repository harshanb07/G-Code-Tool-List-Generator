"""Detection of CNC tool changes in G-code text."""

import re

from gcode_tool_list.models import ToolOccurrence


_COMMENT_PATTERN = re.compile(r"\(([^)]*)\)")
_TOOL_PATTERN = re.compile(r"(?<![A-Z])T(\d+)", re.IGNORECASE)
_TOOL_CHANGE_PATTERN = re.compile(r"(?<![A-Z])M0?6(?!\d)", re.IGNORECASE)


def find_tool_changes(source_text: str) -> list[ToolOccurrence]:
    """Return each line containing a tool number and an M6/M06 command."""
    occurrences: list[ToolOccurrence] = []

    for line_number, raw_line in enumerate(source_text.splitlines(), start=1):
        comments = list(_COMMENT_PATTERN.finditer(raw_line))
        code = _COMMENT_PATTERN.sub(
            lambda match: " " * len(match.group(0)),
            raw_line,
        )

        tool_match = _TOOL_PATTERN.search(code)
        if tool_match is None or _TOOL_CHANGE_PATTERN.search(code) is None:
            continue

        inline_comment = comments[0].group(1).strip() if comments else None
        occurrences.append(
            ToolOccurrence(
                tool_number=int(tool_match.group(1)),
                line_number=line_number,
                raw_line=raw_line,
                inline_comment=inline_comment,
            )
        )

    return occurrences
