"""Detection of CNC tool changes in G-code text."""

import re

from gcode_tool_list.models import ToolOccurrence


_COMMENT_PATTERN = re.compile(r"\(([^)]*)\)")
_TOOL_PATTERN = re.compile(r"(?<![A-Z])T(\d+)", re.IGNORECASE)
_TOOL_CHANGE_PATTERN = re.compile(r"(?<![A-Z])M0?6(?!\d)", re.IGNORECASE)


def _hide_comments(raw_line: str) -> str:
    """Replace complete parenthesized comments with equal-length spaces."""
    return _COMMENT_PATTERN.sub(
        lambda match: " " * len(match.group(0)),
        raw_line,
    )


def find_tool_changes(source_text: str) -> list[ToolOccurrence]:
    """Return each line containing a tool number and an M6/M06 command."""
    occurrences: list[ToolOccurrence] = []
    lines = source_text.splitlines()

    for line_index, raw_line in enumerate(lines):
        comments = list(_COMMENT_PATTERN.finditer(raw_line))
        code = _hide_comments(raw_line)

        tool_match = _TOOL_PATTERN.search(code)
        tool_change_match = _TOOL_CHANGE_PATTERN.search(code)
        if tool_match is None or tool_change_match is None:
            continue

        tool_call_end = max(tool_match.end(), tool_change_match.end())
        associated_comments = [
            comment_text
            for match in comments
            if match.start() >= tool_call_end
            if (comment_text := match.group(1).strip())
        ]

        for following_line in lines[line_index + 1 : line_index + 6]:
            following_comments = list(_COMMENT_PATTERN.finditer(following_line))
            if _hide_comments(following_line).strip():
                break

            associated_comments.extend(
                comment_text
                for match in following_comments
                if (comment_text := match.group(1).strip())
            )

        occurrences.append(
            ToolOccurrence(
                tool_number=int(tool_match.group(1)),
                line_number=line_index + 1,
                raw_line=raw_line,
                comments=tuple(associated_comments),
            )
        )

    return occurrences
