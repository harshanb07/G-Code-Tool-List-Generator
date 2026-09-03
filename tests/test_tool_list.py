import pytest

from gcode_tool_list.models import ToolGroup, ToolOccurrence, ToolSummary
from gcode_tool_list.parser import find_declared_tools, find_tool_changes
from gcode_tool_list.tool_list import (
    build_tool_summaries,
    group_tool_occurrences,
)


def test_empty_input_returns_empty_list() -> None:
    assert group_tool_occurrences([]) == []


def test_groups_one_occurrence() -> None:
    occurrence = ToolOccurrence(1, 4, "T1 M06", ("ROUGHER",))

    assert group_tool_occurrences([occurrence]) == [
        ToolGroup(1, (occurrence,))
    ]


def test_groups_repeated_tool_one_occurrences() -> None:
    first = ToolOccurrence(1, 1, "T1 M06", ())
    second = ToolOccurrence(1, 8, "M6 T1", ("FINISH",))

    assert group_tool_occurrences([first, second]) == [
        ToolGroup(1, (first, second))
    ]


def test_groups_t1_t2_then_t1_again() -> None:
    first_t1 = ToolOccurrence(1, 1, "T1 M06", ())
    t2 = ToolOccurrence(2, 5, "T2 M06", ())
    second_t1 = ToolOccurrence(1, 9, "T1 M06", ())

    assert group_tool_occurrences([first_t1, t2, second_t1]) == [
        ToolGroup(1, (first_t1, second_t1)),
        ToolGroup(2, (t2,)),
    ]


def test_preserves_first_appearance_tool_order() -> None:
    occurrences = [
        ToolOccurrence(3, 1, "T3 M06", ()),
        ToolOccurrence(1, 2, "T1 M06", ()),
        ToolOccurrence(2, 3, "T2 M06", ()),
        ToolOccurrence(3, 4, "T3 M06", ()),
    ]

    groups = group_tool_occurrences(occurrences)

    assert [group.tool_number for group in groups] == [3, 1, 2]


def test_preserves_occurrence_order_within_each_group() -> None:
    first = ToolOccurrence(2, 2, "T2 M06", ("FIRST",))
    other_tool = ToolOccurrence(1, 6, "T1 M06", ())
    second = ToolOccurrence(2, 10, "M06 T2", ("SECOND",))
    third = ToolOccurrence(2, 14, "T02M6", ("THIRD",))

    groups = group_tool_occurrences([first, other_tool, second, third])

    assert groups[0].occurrences == (first, second, third)


def test_preserves_all_occurrence_data_and_objects() -> None:
    occurrence = ToolOccurrence(
        tool_number=7,
        line_number=42,
        raw_line="  T07 M6 (3/4 EM)  ",
        comments=("3/4 EM", "CHECK HOLDER"),
    )

    grouped_occurrence = group_tool_occurrences([occurrence])[0].occurrences[0]

    assert grouped_occurrence is occurrence
    assert grouped_occurrence.tool_number == 7
    assert grouped_occurrence.line_number == 42
    assert grouped_occurrence.raw_line == "  T07 M6 (3/4 EM)  "
    assert grouped_occurrence.comments == ("3/4 EM", "CHECK HOLDER")


def test_does_not_mutate_input_list_or_occurrences() -> None:
    first = ToolOccurrence(2, 3, "T2 M06", ("ROUGH",))
    second = ToolOccurrence(1, 7, "T1 M06", ("FINISH",))
    occurrences = [first, second]
    original_list = list(occurrences)
    original_values = [
        (item.tool_number, item.line_number, item.raw_line, item.comments)
        for item in occurrences
    ]

    group_tool_occurrences(occurrences)

    assert occurrences == original_list
    assert occurrences[0] is first
    assert occurrences[1] is second
    assert [
        (item.tool_number, item.line_number, item.raw_line, item.comments)
        for item in occurrences
    ] == original_values


def test_groups_parser_results_from_t01_and_t1_together() -> None:
    parsed_occurrences = find_tool_changes("T01 M06\nT1 M6")

    assert group_tool_occurrences(parsed_occurrences) == [
        ToolGroup(1, tuple(parsed_occurrences))
    ]


def _only_summary(source: str) -> ToolSummary:
    summaries = build_tool_summaries(source)
    assert len(summaries) == 1
    return summaries[0]


def test_empty_program_returns_no_summaries() -> None:
    assert build_tool_summaries("") == []


def test_header_only_tool_appears_without_executable_call() -> None:
    summary = _only_summary("(T1 - DRILL - H1 - D1 - D0.25)")

    assert summary.tool_number == 1
    assert summary.description == "DRILL"
    assert summary.h_registers == (1,)
    assert summary.d_registers == (1,)
    assert summary.documented_d_values == ("0.25",)
    assert summary.occurrences == ()


def test_header_tools_preserve_first_declaration_order() -> None:
    source = "(T3 - THIRD)\n(T1 - FIRST)\n(T2 - SECOND)"

    summaries = build_tool_summaries(source)

    assert [summary.tool_number for summary in summaries] == [3, 1, 2]


def test_called_tool_missing_from_header_is_appended() -> None:
    source = "(T2 - DECLARED)\nT2 M06\nT1 M06"

    summaries = build_tool_summaries(source)

    assert [summary.tool_number for summary in summaries] == [2, 1]


def test_no_header_uses_first_executable_tool_order() -> None:
    source = "T2 M06\nT1 M06\nT2 M06"

    summaries = build_tool_summaries(source)

    assert [summary.tool_number for summary in summaries] == [2, 1]


def test_repeated_declarations_become_one_summary() -> None:
    source = "(T1 - FIRST)\n(T1 - SECOND)\nT1 M06"

    summary = _only_summary(source)

    assert len(summary.declarations) == 2
    assert summary.description == "FIRST"


def test_repeated_occurrences_become_one_summary() -> None:
    source = "T1 M06\nT1 M06"

    summary = _only_summary(source)

    assert len(summary.occurrences) == 2


def test_header_description_is_preferred_over_inline_description() -> None:
    source = "(T1 - HEADER DESCRIPTION)\nT1 M06 (INLINE DESCRIPTION)"

    summary = _only_summary(source)

    assert summary.description == "HEADER DESCRIPTION"


def test_inline_tool_call_description_is_fallback() -> None:
    summary = _only_summary("T1 M06 (3/4 EM)")

    assert summary.description == "3/4 EM"


def test_following_setup_note_is_not_used_as_description() -> None:
    source = "T1 M06\n(FOR DRILLING)"

    summary = _only_summary(source)

    assert summary.description == ""
    assert summary.notes == ("FOR DRILLING",)


def test_executable_h_registers_take_precedence_over_declared_h() -> None:
    source = "(T1 - TOOL - H9)\nT1 M06\nG43 H2"

    summary = _only_summary(source)

    assert summary.h_registers == (2,)


def test_declared_h_is_used_when_executable_h_is_absent() -> None:
    source = "(T1 - TOOL - H9)\nT1 M06"

    summary = _only_summary(source)

    assert summary.h_registers == (9,)


def test_executable_d_registers_take_precedence_over_declared_d() -> None:
    source = "(T1 - TOOL - D9)\nT1 M06\nG41 D2"

    summary = _only_summary(source)

    assert summary.d_registers == (2,)


def test_declared_d_is_used_when_executable_d_is_absent() -> None:
    source = "(T1 - TOOL - D9)\nT1 M06"

    summary = _only_summary(source)

    assert summary.d_registers == (9,)


def test_executable_registers_preserve_distinct_first_use_order() -> None:
    source = (
        "T1 M06\nG43 H3\nG41 D4\n"
        "T1 M06\nG43 H1\nG42 D2\n"
        "T1 M06\nG43 H3\nG41 D4"
    )

    summary = _only_summary(source)

    assert summary.h_registers == (3, 1)
    assert summary.d_registers == (4, 2)


def test_documented_d_values_come_only_from_declarations() -> None:
    source = '(T1 - TOOL - D9 - D0.7500")\nT1 M06\nG41 D191'

    summary = _only_summary(source)

    assert summary.d_registers == (191,)
    assert summary.documented_d_values == ('0.7500"',)


def test_documented_d_value_units_remain_unchanged() -> None:
    source = '(T1 - TOOL - D0.5 - D0.7500" - D12.7 MM)'

    summary = _only_summary(source)

    assert summary.documented_d_values == (
        "0.5",
        '0.7500"',
        "12.7 MM",
    )


def test_extracts_basic_max_z_depth() -> None:
    summary = _only_summary("T1 M06 (MAX - Z3.)")

    assert summary.max_z_depth == "3."


def test_max_z_uses_largest_absolute_magnitude() -> None:
    source = "T1 M06 (MAX Z0.27) (MAX Z-3.0) (MAX Z2.5)"

    summary = _only_summary(source)

    assert summary.max_z_depth == "3.0"


def test_extracts_leading_decimal_max_z() -> None:
    summary = _only_summary('T1 M06 (MAX Z.750")')

    assert summary.max_z_depth == '.750"'


def test_accepts_maximum_and_lowercase_labels() -> None:
    source = "T1 M06 (maximum z+1.250)"

    summary = _only_summary(source)

    assert summary.max_z_depth == "1.250"


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ('"', '12.7"'),
        (" MM", "12.7 MM"),
        (" IN", "12.7 IN"),
        (" INCH", "12.7 INCH"),
        (" INCHES", "12.7 INCHES"),
    ],
)
def test_preserves_supported_max_z_units(unit: str, expected: str) -> None:
    source = f"T1 M06 (MAX Z12.7{unit})"

    summary = _only_summary(source)

    assert summary.max_z_depth == expected


def test_unitless_max_z_remains_unitless() -> None:
    summary = _only_summary("T1 M06 (MAX Z0.5)")

    assert summary.max_z_depth == "0.5"


def test_largest_max_z_is_selected_across_repeated_occurrences() -> None:
    source = "T1 M06 (MAX Z-2.0)\nT1 M06 (MAX Z3.5)"

    summary = _only_summary(source)

    assert summary.max_z_depth == "3.5"


def test_equal_max_magnitude_keeps_first_display_value() -> None:
    source = "T1 M06 (MAX Z-3.0)\nT1 M06 (MAX Z3.00)"

    summary = _only_summary(source)

    assert summary.max_z_depth == "3.0"


def test_min_z_does_not_affect_max_depth_or_notes() -> None:
    source = "T1 M06 (MIN Z-99.0) (MAX Z1.0)"

    summary = _only_summary(source)

    assert summary.max_z_depth == "1.0"
    assert summary.notes == ()


@pytest.mark.parametrize(
    "comment",
    [
        "MAX Z",
        "MAX Z.",
        "MAX Z--3",
        "MAX Z1.2.3",
        "MAX Z1.0 METERS",
    ],
)
def test_malformed_or_unsupported_max_z_is_ignored(comment: str) -> None:
    summary = _only_summary(f"T1 M06 ({comment})")

    assert summary.max_z_depth is None


def test_no_max_z_comment_produces_none() -> None:
    summary = _only_summary("T1 M06 (ORDINARY NOTE)")

    assert summary.max_z_depth is None


def test_notes_from_repeated_occurrences_preserve_order() -> None:
    source = (
        "T1 M06 (TOOL DESCRIPTION) (FIRST)\n"
        "T1 M06 (SECOND) (THIRD)"
    )

    summary = _only_summary(source)

    assert summary.notes == ("FIRST", "SECOND", "THIRD")


def test_exact_duplicate_notes_are_removed() -> None:
    source = "T1 M06 (TOOL) (CHECK)\nT1 M06 (CHECK) (OTHER)"

    summary = _only_summary(source)

    assert summary.notes == ("CHECK", "OTHER")


def test_selected_inline_description_is_excluded_from_notes() -> None:
    summary = _only_summary("T1 M06 (3/4 EM) (CHECK HOLDER)")

    assert summary.description == "3/4 EM"
    assert summary.notes == ("CHECK HOLDER",)


def test_max_and_min_comments_are_excluded_from_printable_notes() -> None:
    source = "T1 M06 (TOOL) (MAX Z2.0) (MIN Z-0.1) (KEEP)"

    summary = _only_summary(source)

    assert summary.notes == ("KEEP",)


def test_underlying_occurrence_comments_remain_unchanged() -> None:
    source = "T1 M06 (TOOL) (MAX Z2.0) (MIN Z-0.1) (KEEP)"

    summary = _only_summary(source)

    assert summary.occurrences[0].comments == (
        "TOOL",
        "MAX Z2.0",
        "MIN Z-0.1",
        "KEEP",
    )


def test_summary_preserves_declaration_and_occurrence_evidence() -> None:
    source = "(T1 - HEADER - H9)\nT1 M06 (INLINE)\nG43 H1"
    declarations = find_declared_tools(source)
    occurrences = find_tool_changes(source)

    summary = _only_summary(source)

    assert summary.declarations == tuple(declarations)
    assert summary.occurrences == tuple(occurrences)


def test_building_summaries_does_not_change_source_text() -> None:
    source = "(T1 - TOOL)\nT1 M06 (NOTE)"
    original_source = source

    build_tool_summaries(source)

    assert source == original_source


def test_matching_declared_and_executable_h_has_no_warning() -> None:
    source = "(T1 - TOOL - H1)\nT1 M06\nG43 H1"

    summary = _only_summary(source)

    assert summary.warnings == ()


def test_matching_declared_and_executable_d_has_no_warning() -> None:
    source = "(T1 - TOOL - D1)\nT1 M06\nG41 D1"

    summary = _only_summary(source)

    assert summary.warnings == ()


def test_h_register_mismatch_produces_warning() -> None:
    source = "(T1 - TOOL - H1)\nT1 M06\nG43 H7"

    summary = _only_summary(source)

    assert summary.warnings == (
        "H register mismatch: header declares H1, "
        "but executable G-code uses H7. Verify the tool-length offset.",
    )


def test_d_register_mismatch_includes_documented_header_value() -> None:
    source = '(T1 - TOOL - D1 - D0.7500")\nT1 M06\nG41 D31'

    summary = _only_summary(source)

    assert summary.warnings == (
        'D register mismatch: header declares D1 with documented value 0.7500", '
        "but executable G-code uses D31. "
        "Verify the cutter compensation offset.",
    )
    assert summary.documented_d_values == ('0.7500"',)


def test_d_mismatch_does_not_attach_header_value_to_executable_register() -> None:
    source = '(T1 - TOOL - D1 - D0.7500")\nT1 M06\nG41 D31'

    warning = _only_summary(source).warnings[0]

    assert 'D31 with documented value 0.7500"' not in warning
    assert 'header declares D1 with documented value 0.7500"' in warning


def test_multiple_executable_h_registers_produce_warning() -> None:
    source = "T1 M06\nG43 H1\nG43 H7"

    summary = _only_summary(source)

    assert summary.warnings == (
        "Multiple executable H registers found for T1: "
        "H1, H7. Verify the tool-length offsets.",
    )


def test_multiple_executable_d_registers_produce_warning() -> None:
    source = "T1 M06\nG41 D1\nG42 D31"

    summary = _only_summary(source)

    assert summary.warnings == (
        "Multiple executable D registers found for T1: "
        "D1, D31. Verify the cutter compensation offsets.",
    )


def test_declared_only_registers_have_no_warning() -> None:
    source = "(T1 - TOOL - H1 - D1)\nT1 M06"

    summary = _only_summary(source)

    assert summary.warnings == ()


def test_executable_only_registers_have_no_warning() -> None:
    source = "T1 M06\nG43 H7\nG41 D31"

    summary = _only_summary(source)

    assert summary.warnings == ()


def test_header_only_tool_has_no_warning() -> None:
    summary = _only_summary("(T1 - TOOL - H1 - D1)")

    assert summary.occurrences == ()
    assert summary.warnings == ()


def test_warning_order_is_stable() -> None:
    source = (
        '(T1 - TOOL - H9 - D9 - D0.7500")\n'
        "T1 M06\n"
        "G43 H1\n"
        "G43 H7\n"
        "G41 D1\n"
        "G42 D31"
    )

    summary = _only_summary(source)

    assert summary.warnings == (
        "H register mismatch: header declares H9, "
        "but executable G-code uses H1, H7. Verify the tool-length offset.",
        'D register mismatch: header declares D9 with documented value 0.7500", '
        "but executable G-code uses D1, D31. "
        "Verify the cutter compensation offset.",
        "Multiple executable H registers found for T1: "
        "H1, H7. Verify the tool-length offsets.",
        "Multiple executable D registers found for T1: "
        "D1, D31. Verify the cutter compensation offsets.",
    )


def test_mismatch_warning_preserves_declarations_and_occurrences() -> None:
    source = '(T1 - TOOL - D1 - D0.7500")\nT1 M06\nG41 D31'
    expected_declarations = tuple(find_declared_tools(source))
    expected_occurrences = tuple(find_tool_changes(source))

    summary = _only_summary(source)

    assert summary.declarations == expected_declarations
    assert summary.occurrences == expected_occurrences
