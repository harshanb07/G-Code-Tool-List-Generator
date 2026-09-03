"""Grouping of parsed tool-change occurrences."""

import re
from decimal import Decimal, InvalidOperation

from gcode_tool_list.models import (
    DeclaredTool,
    ToolGroup,
    ToolOccurrence,
    ToolSummary,
)
from gcode_tool_list.parser import find_declared_tools, find_tool_changes


_COMMENT_PATTERN = re.compile(r"\(([^)]*)\)")
_MAX_Z_PATTERN = re.compile(
    r"\bMAX(?:IMUM)?\b\s*(?:-\s*)?Z\s*"
    r"(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r'(?P<unit>\s*(?:"|[A-Z]+))?'
    r"(?![\d.])",
    re.IGNORECASE,
)
_MIN_Z_LABEL_PATTERN = re.compile(
    r"\bMIN(?:IMUM)?\b\s*(?:-\s*)?Z(?![A-Z])",
    re.IGNORECASE,
)
_SUPPORTED_MAX_UNITS = {'"', "MM", "IN", "INCH", "INCHES"}


def group_tool_occurrences(
    occurrences: list[ToolOccurrence],
) -> list[ToolGroup]:
    """Group occurrences by tool number in first-appearance order."""

    occurrences_by_tool: dict[int, list[ToolOccurrence]] = {}

    for occurrence in occurrences:
        tool_number = occurrence.tool_number

        if tool_number not in occurrences_by_tool:
            occurrences_by_tool[tool_number] = []

        occurrences_by_tool[tool_number].append(occurrence)

    groups: list[ToolGroup] = []

    for tool_number, grouped_occurrences in occurrences_by_tool.items():
        group = ToolGroup(
            tool_number=tool_number,
            occurrences=tuple(grouped_occurrences),
        )
        groups.append(group)

    return groups


def _append_distinct_integers(
    destination: list[int],
    seen_values: set[int],
    new_values: tuple[int, ...],
) -> None:
    for value in new_values:
        if value not in seen_values:
            seen_values.add(value)
            destination.append(value)


def _append_distinct_strings(
    destination: list[str],
    seen_values: set[str],
    new_values: tuple[str, ...],
) -> None:
    for value in new_values:
        if value not in seen_values:
            seen_values.add(value)
            destination.append(value)


def _comment_appears_on_tool_change_line(
    occurrence: ToolOccurrence,
    comment: str,
) -> bool:
    for comment_match in _COMMENT_PATTERN.finditer(occurrence.raw_line):
        inline_comment = comment_match.group(1).strip()
        if inline_comment == comment:
            return True

    return False


def _select_description(
    declarations: tuple[DeclaredTool, ...],
    occurrences: tuple[ToolOccurrence, ...],
) -> str:
    for declaration in declarations:
        if declaration.description:
            return declaration.description

    for occurrence in occurrences:
        if not occurrence.comments:
            continue

        first_comment = occurrence.comments[0]
        if _comment_appears_on_tool_change_line(occurrence, first_comment):
            return first_comment

    return ""


def _parse_max_z_comment(comment: str) -> tuple[Decimal, str] | None:
    max_match = _MAX_Z_PATTERN.search(comment)
    if max_match is None:
        return None

    unit_text = max_match.group("unit") or ""
    if unit_text:
        normalized_unit = unit_text.strip().upper()
        if normalized_unit not in _SUPPORTED_MAX_UNITS:
            return None

    number_text = max_match.group("number")
    try:
        magnitude = abs(Decimal(number_text))
    except InvalidOperation:
        return None

    display_number = number_text
    if display_number.startswith(("+", "-")):
        display_number = display_number[1:]

    return magnitude, display_number + unit_text


def _is_inline_description_comment(
    occurrence: ToolOccurrence,
    comment_index: int,
    comment: str,
    description: str,
) -> bool:
    if comment_index != 0 or comment != description:
        return False

    return _comment_appears_on_tool_change_line(occurrence, comment)


def _collect_max_z_and_notes(
    occurrences: tuple[ToolOccurrence, ...],
    description: str,
) -> tuple[str | None, tuple[str, ...]]:
    largest_magnitude: Decimal | None = None
    max_z_depth: str | None = None
    notes: list[str] = []
    seen_notes: set[str] = set()

    for occurrence in occurrences:
        for comment_index, comment in enumerate(occurrence.comments):
            max_candidate = _parse_max_z_comment(comment)
            if max_candidate is not None:
                magnitude, display_value = max_candidate
                if largest_magnitude is None or magnitude > largest_magnitude:
                    largest_magnitude = magnitude
                    max_z_depth = display_value
                continue

            if _MIN_Z_LABEL_PATTERN.search(comment) is not None:
                continue

            if _is_inline_description_comment(
                occurrence=occurrence,
                comment_index=comment_index,
                comment=comment,
                description=description,
            ):
                continue

            if comment not in seen_notes:
                seen_notes.add(comment)
                notes.append(comment)

    return max_z_depth, tuple(notes)


def _format_registers(prefix: str, registers: list[int]) -> str:
    formatted_registers: list[str] = []

    for register in registers:
        formatted_registers.append(f"{prefix}{register}")

    return ", ".join(formatted_registers)


def _build_warnings(
    tool_number: int,
    declared_h_registers: list[int],
    declared_d_registers: list[int],
    executable_h_registers: list[int],
    executable_d_registers: list[int],
    documented_d_values: list[str],
) -> tuple[str, ...]:
    warnings: list[str] = []

    if (
        declared_h_registers
        and executable_h_registers
        and set(declared_h_registers) != set(executable_h_registers)
    ):
        declared_h_text = _format_registers("H", declared_h_registers)
        executable_h_text = _format_registers("H", executable_h_registers)
        warnings.append(
            "H register mismatch: "
            f"header declares {declared_h_text}, "
            f"but executable G-code uses {executable_h_text}. "
            "Verify the tool-length offset."
        )

    if (
        declared_d_registers
        and executable_d_registers
        and set(declared_d_registers) != set(executable_d_registers)
    ):
        declared_d_text = _format_registers("D", declared_d_registers)
        executable_d_text = _format_registers("D", executable_d_registers)
        documented_value_text = ""

        if len(documented_d_values) == 1:
            documented_value_text = (
                f" with documented value {documented_d_values[0]}"
            )
        elif len(documented_d_values) > 1:
            joined_values = ", ".join(documented_d_values)
            documented_value_text = f" with documented values {joined_values}"

        warnings.append(
            "D register mismatch: "
            f"header declares {declared_d_text}{documented_value_text}, "
            f"but executable G-code uses {executable_d_text}. "
            "Verify the cutter compensation offset."
        )

    if len(executable_h_registers) > 1:
        executable_h_text = _format_registers("H", executable_h_registers)
        warnings.append(
            f"Multiple executable H registers found for T{tool_number}: "
            f"{executable_h_text}. Verify the tool-length offsets."
        )

    if len(executable_d_registers) > 1:
        executable_d_text = _format_registers("D", executable_d_registers)
        warnings.append(
            f"Multiple executable D registers found for T{tool_number}: "
            f"{executable_d_text}. Verify the cutter compensation offsets."
        )

    return tuple(warnings)


def _build_tool_summary(
    tool_number: int,
    declarations: tuple[DeclaredTool, ...],
    occurrences: tuple[ToolOccurrence, ...],
) -> ToolSummary:
    declared_h_registers: list[int] = []
    declared_d_registers: list[int] = []
    executable_h_registers: list[int] = []
    executable_d_registers: list[int] = []
    documented_d_values: list[str] = []
    seen_declared_h: set[int] = set()
    seen_declared_d: set[int] = set()
    seen_executable_h: set[int] = set()
    seen_executable_d: set[int] = set()
    seen_documented_d_values: set[str] = set()

    for declaration in declarations:
        _append_distinct_integers(
            declared_h_registers,
            seen_declared_h,
            declaration.h_registers,
        )
        _append_distinct_integers(
            declared_d_registers,
            seen_declared_d,
            declaration.d_registers,
        )
        _append_distinct_strings(
            documented_d_values,
            seen_documented_d_values,
            declaration.documented_d_values,
        )

    for occurrence in occurrences:
        _append_distinct_integers(
            executable_h_registers,
            seen_executable_h,
            occurrence.h_registers,
        )
        _append_distinct_integers(
            executable_d_registers,
            seen_executable_d,
            occurrence.d_registers,
        )

    selected_h_registers = declared_h_registers
    if executable_h_registers:
        selected_h_registers = executable_h_registers

    selected_d_registers = declared_d_registers
    if executable_d_registers:
        selected_d_registers = executable_d_registers

    description = _select_description(declarations, occurrences)
    max_z_depth, notes = _collect_max_z_and_notes(occurrences, description)
    warnings = _build_warnings(
        tool_number=tool_number,
        declared_h_registers=declared_h_registers,
        declared_d_registers=declared_d_registers,
        executable_h_registers=executable_h_registers,
        executable_d_registers=executable_d_registers,
        documented_d_values=documented_d_values,
    )

    return ToolSummary(
        tool_number=tool_number,
        description=description,
        max_z_depth=max_z_depth,
        h_registers=tuple(selected_h_registers),
        d_registers=tuple(selected_d_registers),
        documented_d_values=tuple(documented_d_values),
        notes=notes,
        declarations=declarations,
        occurrences=occurrences,
        warnings=warnings,
    )


def build_tool_summaries(source_text: str) -> list[ToolSummary]:
    """Build one reconciled summary for each declared or called tool."""
    declarations = find_declared_tools(source_text)
    occurrences = find_tool_changes(source_text)
    occurrence_groups = group_tool_occurrences(occurrences)
    declarations_by_tool: dict[int, list[DeclaredTool]] = {}
    groups_by_tool: dict[int, ToolGroup] = {}
    tool_order: list[int] = []

    for declaration in declarations:
        tool_number = declaration.tool_number
        if tool_number not in declarations_by_tool:
            declarations_by_tool[tool_number] = []
            tool_order.append(tool_number)
        declarations_by_tool[tool_number].append(declaration)

    for group in occurrence_groups:
        tool_number = group.tool_number
        groups_by_tool[tool_number] = group
        if tool_number not in declarations_by_tool:
            tool_order.append(tool_number)

    summaries: list[ToolSummary] = []

    for tool_number in tool_order:
        tool_declarations = tuple(declarations_by_tool.get(tool_number, []))
        tool_occurrences: tuple[ToolOccurrence, ...] = ()
        if tool_number in groups_by_tool:
            tool_occurrences = groups_by_tool[tool_number].occurrences

        summary = _build_tool_summary(
            tool_number=tool_number,
            declarations=tool_declarations,
            occurrences=tool_occurrences,
        )
        summaries.append(summary)

    return summaries
