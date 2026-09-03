"""Plain-text formatting for final tool summaries."""

from gcode_tool_list.models import ToolSummary


_TOOL_SEPARATOR = "--------------------------------------------------"
_WARNING_HEADING = "*** WARNING - VERIFY BEFORE MACHINING ***"


def _format_registers(prefix: str, registers: tuple[int, ...]) -> str:
    formatted_registers: list[str] = []

    for register in registers:
        formatted_registers.append(f"{prefix}{register}")

    return ", ".join(formatted_registers)


def _collect_declared_d_registers(summary: ToolSummary) -> tuple[int, ...]:
    declared_registers: list[int] = []
    seen_registers: set[int] = set()

    for declaration in summary.declarations:
        for register in declaration.d_registers:
            if register not in seen_registers:
                seen_registers.add(register)
                declared_registers.append(register)

    return tuple(declared_registers)


def _format_d_lines(summary: ToolSummary) -> list[str]:
    selected_registers = summary.d_registers
    declared_registers = _collect_declared_d_registers(summary)
    documented_values = summary.documented_d_values
    lines: list[str] = []

    safe_pairing = (
        len(selected_registers) == 1
        and len(declared_registers) == 1
        and selected_registers[0] == declared_registers[0]
        and len(documented_values) == 1
    )

    if safe_pairing:
        register_text = _format_registers("D", selected_registers)
        lines.append(f"D: {register_text} = {documented_values[0]}")
        return lines

    conflicting_registers = (
        selected_registers
        and declared_registers
        and set(selected_registers) != set(declared_registers)
    )

    if conflicting_registers:
        selected_text = _format_registers("D", selected_registers)
        lines.append(f"D USED: {selected_text}")

        declared_text = _format_registers("D", declared_registers)
        if len(declared_registers) == 1 and len(documented_values) == 1:
            lines.append(f"HEADER D: {declared_text} = {documented_values[0]}")
        else:
            lines.append(f"HEADER D REGISTERS: {declared_text}")
            if documented_values:
                values_text = ", ".join(documented_values)
                lines.append(f"DOCUMENTED D VALUES: {values_text}")

        return lines

    if selected_registers:
        selected_text = _format_registers("D", selected_registers)
        if len(selected_registers) == 1 and not documented_values:
            lines.append(f"D: {selected_text}")
        else:
            lines.append(f"D REGISTERS: {selected_text}")

    if documented_values:
        values_text = ", ".join(documented_values)
        lines.append(f"DOCUMENTED D VALUES: {values_text}")

    return lines


def _format_tool_summary(summary: ToolSummary) -> str:
    if summary.description:
        heading = f"T{summary.tool_number} ({summary.description})"
    else:
        heading = f"T{summary.tool_number}"

    sections: list[str] = [heading]
    technical_lines: list[str] = []

    if summary.max_z_depth is not None:
        technical_lines.append(
            "MINIMUM STICKOUT GUIDE (FROM MAX Z): "
            f"{summary.max_z_depth}"
        )

    if summary.h_registers:
        h_registers = _format_registers("H", summary.h_registers)
        technical_lines.append(f"H: {h_registers}")

    technical_lines.extend(_format_d_lines(summary))
    if technical_lines:
        sections.append("\n".join(technical_lines))

    if summary.warnings:
        warning_lines: list[str] = [_WARNING_HEADING]
        for warning in summary.warnings:
            warning_lines.append(f"- {warning}")
        sections.append("\n".join(warning_lines))

    if summary.notes:
        note_lines: list[str] = ["NOTES:"]
        for note in summary.notes:
            note_lines.append(f"- {note}")
        sections.append("\n".join(note_lines))

    return "\n\n".join(sections)


def format_tool_summaries(summaries: list[ToolSummary]) -> str:
    """Return final tool summaries as printable plain text."""
    if not summaries:
        return "NO TOOLS FOUND\n"

    tool_blocks: list[str] = []
    for summary in summaries:
        tool_blocks.append(_format_tool_summary(summary))

    separator = f"\n\n{_TOOL_SEPARATOR}\n\n"
    return separator.join(tool_blocks) + "\n"
