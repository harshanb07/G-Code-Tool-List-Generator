"""Data models used by the G-code parser."""

from dataclasses import dataclass


@dataclass
class ToolOccurrence:
    """One tool change found in a G-code program."""

    tool_number: int
    line_number: int
    raw_line: str
    comments: tuple[str, ...]


@dataclass
class ToolGroup:
    """All tool-change occurrences for one normalized tool number."""

    tool_number: int
    occurrences: tuple[ToolOccurrence, ...]
