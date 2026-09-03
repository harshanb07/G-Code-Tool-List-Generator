"""Grouping of parsed tool-change occurrences."""

from gcode_tool_list.models import ToolGroup, ToolOccurrence


"""Grouping of parsed tool-change occurrences."""

from gcode_tool_list.models import ToolGroup, ToolOccurrence


def group_tool_occurrences(
    occurrences: list[ToolOccurrence],
) -> list[ToolGroup]:
    """Group occurrences by tool number in first-appearance order."""
    occurrences_by_tool: dict[int, list[ToolOccurrence]] = {}

    for occurrence in occurrences:
        occurrences_by_tool.setdefault(occurrence.tool_number, []).append(occurrence)

    return [
        ToolGroup(tool_number, tuple(grouped_occurrences))
        for tool_number, grouped_occurrences in occurrences_by_tool.items()
    ]
