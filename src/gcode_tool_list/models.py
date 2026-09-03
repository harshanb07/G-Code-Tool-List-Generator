"""Data models used by the G-code parser."""

from dataclasses import dataclass


@dataclass
class ToolOccurrence:
    """One tool change found in a G-code program."""

    tool_number: int
    line_number: int
    raw_line: str
    comments: tuple[str, ...]
    h_registers: tuple[int, ...] = ()
    d_registers: tuple[int, ...] = ()


@dataclass
class DeclaredTool:
    """One tool declared in a program's header tool list."""

    tool_number: int
    line_number: int
    raw_line: str
    details: str


@dataclass
class ToolGroup:
    """All tool-change occurrences for one normalized tool number."""

    tool_number: int
    occurrences: tuple[ToolOccurrence, ...]
