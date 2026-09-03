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
    description: str = ""
    h_registers: tuple[int, ...] = ()
    d_registers: tuple[int, ...] = ()
    documented_d_values: tuple[str, ...] = ()


@dataclass
class ToolGroup:
    """All tool-change occurrences for one normalized tool number."""

    tool_number: int
    occurrences: tuple[ToolOccurrence, ...]


@dataclass
class ToolSummary:
    """Final structured information for one tool."""

    tool_number: int
    description: str
    max_z_depth: str | None
    h_registers: tuple[int, ...]
    d_registers: tuple[int, ...]
    documented_d_values: tuple[str, ...]
    notes: tuple[str, ...]
    declarations: tuple[DeclaredTool, ...]
    occurrences: tuple[ToolOccurrence, ...]
    warnings: tuple[str, ...] = ()
