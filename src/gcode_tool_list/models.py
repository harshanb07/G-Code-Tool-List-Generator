"""Data models used by the G-code parser."""

from dataclasses import dataclass


@dataclass
class ToolOccurrence:
    """One tool change found in a G-code program."""

    tool_number: int
    line_number: int
    raw_line: str
    inline_comment: str | None
