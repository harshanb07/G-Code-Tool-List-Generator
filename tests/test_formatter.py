import pytest

from gcode_tool_list.formatter import format_tool_summaries
from gcode_tool_list.models import DeclaredTool, ToolSummary


def _summary(
    tool_number: int = 1,
    description: str = "",
    max_z_depth: str | None = None,
    h_registers: tuple[int, ...] = (),
    d_registers: tuple[int, ...] = (),
    documented_d_values: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
    declarations: tuple[DeclaredTool, ...] = (),
    warnings: tuple[str, ...] = (),
) -> ToolSummary:
    return ToolSummary(
        tool_number=tool_number,
        description=description,
        max_z_depth=max_z_depth,
        h_registers=h_registers,
        d_registers=d_registers,
        documented_d_values=documented_d_values,
        notes=notes,
        declarations=declarations,
        occurrences=(),
        warnings=warnings,
    )


def _declaration(
    tool_number: int,
    d_registers: tuple[int, ...] = (),
    documented_d_values: tuple[str, ...] = (),
) -> DeclaredTool:
    return DeclaredTool(
        tool_number=tool_number,
        line_number=1,
        raw_line=f"(T{tool_number} - TOOL)",
        details="TOOL",
        description="TOOL",
        d_registers=d_registers,
        documented_d_values=documented_d_values,
    )


def test_empty_summary_list_returns_no_tools_found() -> None:
    assert format_tool_summaries([]) == "NO TOOLS FOUND\n"


def test_formats_complete_normal_tool() -> None:
    declaration = _declaration(
        tool_number=1,
        d_registers=(1,),
        documented_d_values=('0.7500"',),
    )
    summary = _summary(
        description='3/4 EM FL 2.1" FL 2.25" OUT',
        max_z_depth='3.00"',
        h_registers=(1,),
        d_registers=(1,),
        documented_d_values=('0.7500"',),
        notes=(
            "INSIDE DIA IS PROGRAM TOP TOL",
            "FOR DRILLING AND TAPPING",
        ),
        declarations=(declaration,),
    )

    assert format_tool_summaries([summary]) == (
        'T1 (3/4 EM FL 2.1" FL 2.25" OUT)\n'
        "\n"
        'MINIMUM STICKOUT GUIDE (FROM MAX Z): 3.00"\n'
        "H: H1\n"
        'D: D1 = 0.7500"\n'
        "\n"
        "NOTES:\n"
        "- INSIDE DIA IS PROGRAM TOP TOL\n"
        "- FOR DRILLING AND TAPPING\n"
    )


def test_formats_multiple_tools_with_separator_in_summary_order() -> None:
    summaries = [
        _summary(tool_number=2, description="DRILL"),
        _summary(tool_number=1, description="ENDMILL"),
    ]

    assert format_tool_summaries(summaries) == (
        "T2 (DRILL)\n"
        "\n"
        "--------------------------------------------------\n"
        "\n"
        "T1 (ENDMILL)\n"
    )


def test_tool_without_description_uses_number_only() -> None:
    assert format_tool_summaries([_summary(tool_number=7)]) == "T7\n"


@pytest.mark.parametrize(
    "max_z_depth",
    ['3.00"', "12.7 MM", "0.5"],
)
def test_preserves_minimum_stickout_value_and_unit(
    max_z_depth: str,
) -> None:
    summary = _summary(max_z_depth=max_z_depth)

    assert format_tool_summaries([summary]) == (
        "T1\n"
        "\n"
        f"MINIMUM STICKOUT GUIDE (FROM MAX Z): {max_z_depth}\n"
    )


def test_formats_one_h_register() -> None:
    assert format_tool_summaries([_summary(h_registers=(1,))]) == (
        "T1\n\nH: H1\n"
    )


def test_formats_multiple_h_registers() -> None:
    assert format_tool_summaries([_summary(h_registers=(1, 7))]) == (
        "T1\n\nH: H1, H7\n"
    )


def test_missing_h_register_omits_h_line() -> None:
    output = format_tool_summaries([_summary(d_registers=(1,))])

    assert "\nH:" not in output


def test_safely_pairs_one_matching_d_register_and_value() -> None:
    declaration = _declaration(1, (1,), ('0.7500"',))
    summary = _summary(
        d_registers=(1,),
        documented_d_values=('0.7500"',),
        declarations=(declaration,),
    )

    assert format_tool_summaries([summary]) == 'T1\n\nD: D1 = 0.7500"\n'


def test_header_only_tool_uses_safe_d_pairing() -> None:
    declaration = _declaration(1, (1,), ('0.7500"',))
    summary = _summary(
        d_registers=(1,),
        documented_d_values=('0.7500"',),
        declarations=(declaration,),
    )

    assert format_tool_summaries([summary]) == 'T1\n\nD: D1 = 0.7500"\n'


def test_conflicting_d_register_never_receives_header_value() -> None:
    declaration = _declaration(1, (1,), ('0.7500"',))
    warning = (
        'D register mismatch: header declares D1 with documented value 0.7500", '
        "but executable G-code uses D31. Verify the cutter compensation offset."
    )
    summary = _summary(
        d_registers=(31,),
        documented_d_values=('0.7500"',),
        declarations=(declaration,),
        warnings=(warning,),
    )

    output = format_tool_summaries([summary])

    assert "D USED: D31" in output
    assert 'HEADER D: D1 = 0.7500"' in output
    assert 'D31 = 0.7500"' not in output


def test_d_conflict_prints_warning_before_other_sections() -> None:
    declaration = _declaration(1, (1,), ('0.7500"',))
    warning = "D register mismatch: verify offsets."
    summary = _summary(
        d_registers=(31,),
        documented_d_values=('0.7500"',),
        notes=("CHECK TOOL",),
        declarations=(declaration,),
        warnings=(warning,),
    )

    output = format_tool_summaries([summary])

    assert output == (
        "T1\n"
        "\n"
        "D USED: D31\n"
        'HEADER D: D1 = 0.7500"\n'
        "\n"
        "*** WARNING - VERIFY BEFORE MACHINING ***\n"
        "- D register mismatch: verify offsets.\n"
        "\n"
        "NOTES:\n"
        "- CHECK TOOL\n"
    )


def test_multiple_d_registers_are_not_paired() -> None:
    declaration = _declaration(1, (1, 31), ('0.7500"',))
    summary = _summary(
        d_registers=(1, 31),
        documented_d_values=('0.7500"',),
        declarations=(declaration,),
    )

    output = format_tool_summaries([summary])

    assert "D REGISTERS: D1, D31" in output
    assert 'DOCUMENTED D VALUES: 0.7500"' in output
    assert "D1 =" not in output
    assert "D31 =" not in output


def test_multiple_documented_d_values_are_not_paired() -> None:
    declaration = _declaration(1, (1,), ('0.7500"', '0.5000"'))
    summary = _summary(
        d_registers=(1,),
        documented_d_values=('0.7500"', '0.5000"'),
        declarations=(declaration,),
    )

    assert format_tool_summaries([summary]) == (
        "T1\n"
        "\n"
        "D REGISTERS: D1\n"
        'DOCUMENTED D VALUES: 0.7500", 0.5000"\n'
    )


def test_notes_are_printed_one_per_line_without_added_parentheses() -> None:
    summary = _summary(notes=("FIRST NOTE", "(KEEP THESE PARENTHESES)"))

    assert format_tool_summaries([summary]) == (
        "T1\n"
        "\n"
        "NOTES:\n"
        "- FIRST NOTE\n"
        "- (KEEP THESE PARENTHESES)\n"
    )


def test_warnings_are_printed_prominently_before_notes() -> None:
    summary = _summary(
        warnings=("VERIFY H1", "VERIFY D1"),
        notes=("CHECK HOLDER",),
    )

    assert format_tool_summaries([summary]) == (
        "T1\n"
        "\n"
        "*** WARNING - VERIFY BEFORE MACHINING ***\n"
        "- VERIFY H1\n"
        "- VERIFY D1\n"
        "\n"
        "NOTES:\n"
        "- CHECK HOLDER\n"
    )


def test_tool_without_optional_fields_contains_only_heading() -> None:
    output = format_tool_summaries([_summary(tool_number=4)])

    assert output == "T4\n"


def test_output_ends_with_exactly_one_newline() -> None:
    output = format_tool_summaries([_summary(notes=("NOTE",))])

    assert output.endswith("\n")
    assert not output.endswith("\n\n")


def test_formatter_does_not_expose_internal_evidence() -> None:
    declaration = _declaration(1)
    summary = _summary(declarations=(declaration,))

    output = format_tool_summaries([summary])

    assert "line_number" not in output
    assert "raw_line" not in output
    assert "DeclaredTool" not in output
    assert "occurrence" not in output.lower()


def test_formatter_does_not_mutate_input_summaries() -> None:
    declaration = _declaration(1, (1,), ('0.7500"',))
    summary = _summary(
        description="TOOL",
        d_registers=(1,),
        documented_d_values=('0.7500"',),
        notes=("NOTE",),
        declarations=(declaration,),
    )
    summaries = [summary]
    original_summaries = list(summaries)
    original_summary = ToolSummary(
        tool_number=summary.tool_number,
        description=summary.description,
        max_z_depth=summary.max_z_depth,
        h_registers=summary.h_registers,
        d_registers=summary.d_registers,
        documented_d_values=summary.documented_d_values,
        notes=summary.notes,
        declarations=summary.declarations,
        occurrences=summary.occurrences,
        warnings=summary.warnings,
    )

    format_tool_summaries(summaries)

    assert summaries == original_summaries
    assert summaries[0] is summary
    assert summary == original_summary
