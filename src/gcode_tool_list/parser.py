"""Detection of CNC tool changes in G-code text."""

import re

from gcode_tool_list.models import ToolOccurrence


_COMMENT_PATTERN = re.compile(r"\(([^)]*)\)")
_TOOL_PATTERN = re.compile(r"(?<![A-Z])T(\d+)", re.IGNORECASE)
_TOOL_CHANGE_PATTERN = re.compile(r"(?<![A-Z])M0?6(?!\d)", re.IGNORECASE)


def _replace_comment_with_spaces(match: re.Match[str]) -> str:
    return " " * len(match.group(0))


def _hide_comments(raw_line: str) -> str:
    """Replace complete parenthesized comments with equal-length spaces."""
    return _COMMENT_PATTERN.sub(_replace_comment_with_spaces, raw_line)


def find_tool_changes(source_text: str) -> list[ToolOccurrence]:
    """Return each line containing a tool number and an M6/M06 command."""
    occurrences: list[ToolOccurrence] = []
    lines = source_text.splitlines()

    for line_index, raw_line in enumerate(lines):
        comment_matches = list(_COMMENT_PATTERN.finditer(raw_line))
        code = _hide_comments(raw_line)

        tool_match = _TOOL_PATTERN.search(code)
        tool_change_match = _TOOL_CHANGE_PATTERN.search(code)
        if tool_match is None or tool_change_match is None:
            continue

        tool_call_end = max(tool_match.end(), tool_change_match.end())
        associated_comments: list[str] = []

        for comment_match in comment_matches:
            if comment_match.start() < tool_call_end:
                continue

            comment_text = comment_match.group(1).strip()
            if comment_text:
                associated_comments.append(comment_text)

        # The shop rule allows comments within five physical following lines.
        for following_line in lines[line_index + 1 : line_index + 6]:
            following_comment_matches = list(
                _COMMENT_PATTERN.finditer(following_line)
            )
            hidden_following_line = _hide_comments(following_line)
            remaining_content = hidden_following_line.strip()

            if remaining_content:
                break

            for comment_match in following_comment_matches:
                comment_text = comment_match.group(1).strip()
                if comment_text:
                    associated_comments.append(comment_text)

        occurrences.append(
            ToolOccurrence(
                tool_number=int(tool_match.group(1)),
                line_number=line_index + 1,
                raw_line=raw_line,
                comments=tuple(associated_comments),
            )
        )

    return occurrences
