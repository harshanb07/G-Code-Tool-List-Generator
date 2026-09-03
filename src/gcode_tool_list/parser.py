"""Detection of CNC tool changes in G-code text."""

import re

from gcode_tool_list.models import DeclaredTool, ToolOccurrence


_COMMENT_PATTERN = re.compile(r"\(([^)]*)\)")
_TOOL_PATTERN = re.compile(r"(?<![A-Z])T(\d+)", re.IGNORECASE)
_TOOL_CHANGE_PATTERN = re.compile(r"(?<![A-Z])M0?6(?!\d)", re.IGNORECASE)
_G43_PATTERN = re.compile(r"(?<![A-Z])G43(?![\d.])", re.IGNORECASE)
_H_REGISTER_PATTERN = re.compile(r"(?<![A-Z])H(\d+)(?![\d.])", re.IGNORECASE)
_CUTTER_COMP_PATTERN = re.compile(r"(?<![A-Z])G4[12](?![\d.])", re.IGNORECASE)
_D_REGISTER_PATTERN = re.compile(r"(?<![A-Z])D(\d+)(?![\d.])", re.IGNORECASE)
_DECLARED_TOOL_PATTERN = re.compile(r"T(\d+)\s*-(.*)", re.IGNORECASE)
_DECLARED_H_REGISTER_PATTERN = re.compile(r"H(\d+)", re.IGNORECASE)
_DECLARED_D_REGISTER_PATTERN = re.compile(r"D(\d+)", re.IGNORECASE)
_DOCUMENTED_D_VALUE_PATTERN = re.compile(
    r'D((?:\d+\.\d+|\.\d+|\d+)(?:\s*(?:"|[A-Z]+))?)',
    re.IGNORECASE,
)


def _replace_comment_with_spaces(match: re.Match[str]) -> str:
    return " " * len(match.group(0))


def _hide_comments(raw_line: str) -> str:
    """Replace complete parenthesized comments with equal-length spaces."""
    return _COMMENT_PATTERN.sub(_replace_comment_with_spaces, raw_line)


def _scan_active_tool_registers(
    lines: list[str],
    section_start: int,
    section_end: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    h_registers: list[int] = []
    d_registers: list[int] = []
    seen_h_registers: set[int] = set()
    seen_d_registers: set[int] = set()

    for raw_line in lines[section_start:section_end]:
        code = _hide_comments(raw_line)

        if _G43_PATTERN.search(code) is not None:
            for h_match in _H_REGISTER_PATTERN.finditer(code):
                h_register = int(h_match.group(1))
                if h_register not in seen_h_registers:
                    seen_h_registers.add(h_register)
                    h_registers.append(h_register)

        if _CUTTER_COMP_PATTERN.search(code) is not None:
            for d_match in _D_REGISTER_PATTERN.finditer(code):
                d_register = int(d_match.group(1))
                if d_register not in seen_d_registers:
                    seen_d_registers.add(d_register)
                    d_registers.append(d_register)

    return tuple(h_registers), tuple(d_registers)


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

    occurrences_with_registers: list[ToolOccurrence] = []

    for occurrence_index, occurrence in enumerate(occurrences):
        section_start = occurrence.line_number - 1
        section_end = len(lines)

        if occurrence_index + 1 < len(occurrences):
            next_occurrence = occurrences[occurrence_index + 1]
            section_end = next_occurrence.line_number - 1

        h_registers, d_registers = _scan_active_tool_registers(
            lines=lines,
            section_start=section_start,
            section_end=section_end,
        )
        occurrences_with_registers.append(
            ToolOccurrence(
                tool_number=occurrence.tool_number,
                line_number=occurrence.line_number,
                raw_line=occurrence.raw_line,
                comments=occurrence.comments,
                h_registers=h_registers,
                d_registers=d_registers,
            )
        )

    return occurrences_with_registers


def _parse_declared_tool_details(
    details: str,
) -> tuple[str, tuple[int, ...], tuple[int, ...], tuple[str, ...]]:
    segments = details.split("-")
    first_metadata_index: int | None = None
    h_registers: list[int] = []
    d_registers: list[int] = []
    documented_d_values: list[str] = []
    seen_h_registers: set[int] = set()
    seen_d_registers: set[int] = set()
    seen_documented_d_values: set[str] = set()

    for segment_index, segment in enumerate(segments):
        stripped_segment = segment.strip()

        h_match = _DECLARED_H_REGISTER_PATTERN.fullmatch(stripped_segment)
        if h_match is not None:
            if first_metadata_index is None:
                first_metadata_index = segment_index

            h_register = int(h_match.group(1))
            if h_register not in seen_h_registers:
                seen_h_registers.add(h_register)
                h_registers.append(h_register)
            continue

        d_register_match = _DECLARED_D_REGISTER_PATTERN.fullmatch(
            stripped_segment
        )
        if d_register_match is not None:
            if first_metadata_index is None:
                first_metadata_index = segment_index

            d_register = int(d_register_match.group(1))
            if d_register not in seen_d_registers:
                seen_d_registers.add(d_register)
                d_registers.append(d_register)
            continue

        documented_d_match = _DOCUMENTED_D_VALUE_PATTERN.fullmatch(
            stripped_segment
        )
        if documented_d_match is not None:
            if first_metadata_index is None:
                first_metadata_index = segment_index

            documented_d_value = documented_d_match.group(1)
            if documented_d_value not in seen_documented_d_values:
                seen_documented_d_values.add(documented_d_value)
                documented_d_values.append(documented_d_value)

    description = details
    if first_metadata_index is not None:
        description_segments = segments[:first_metadata_index]
        description = "-".join(description_segments).strip()

    return (
        description,
        tuple(h_registers),
        tuple(d_registers),
        tuple(documented_d_values),
    )


def find_declared_tools(source_text: str) -> list[DeclaredTool]:
    """Return header tool declarations before the first real tool change."""
    lines = source_text.splitlines()
    header_end = len(lines)
    tool_occurrences = find_tool_changes(source_text)

    if tool_occurrences:
        header_end = tool_occurrences[0].line_number - 1

    declared_tools: list[DeclaredTool] = []

    for line_index in range(header_end):
        raw_line = lines[line_index]
        stripped_line = raw_line.strip()
        comment_match = _COMMENT_PATTERN.fullmatch(stripped_line)

        if comment_match is None:
            continue

        comment_content = comment_match.group(1)
        declaration_match = _DECLARED_TOOL_PATTERN.fullmatch(comment_content)

        if declaration_match is None:
            continue

        details = declaration_match.group(2).strip()
        if not details:
            continue

        (
            description,
            h_registers,
            d_registers,
            documented_d_values,
        ) = _parse_declared_tool_details(details)

        declared_tools.append(
            DeclaredTool(
                tool_number=int(declaration_match.group(1)),
                line_number=line_index + 1,
                raw_line=raw_line,
                details=details,
                description=description,
                h_registers=h_registers,
                d_registers=d_registers,
                documented_d_values=documented_d_values,
            )
        )

    return declared_tools
