import pytest

from gcode_tool_list.models import DeclaredTool, ToolOccurrence
from gcode_tool_list.parser import find_declared_tools, find_tool_changes


@pytest.mark.parametrize(
    ("source", "tool_number"),
    [
        ("T1 M06", 1),
        ("T1 M6", 1),
        ("T1M06", 1),
        ("M06 T1", 1),
        ("t2 m06", 2),
        ("t3m6", 3),
        ("m06 t4", 4),
        ("T01 M06", 1),
    ],
)
def test_recognizes_required_tool_change_formats(
    source: str,
    tool_number: int,
) -> None:
    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=tool_number,
            line_number=1,
            raw_line=source,
            comments=(),
        )
    ]


def test_ignores_tool_change_entirely_inside_comment() -> None:
    assert find_tool_changes("(T1 M06)") == []


def test_ignores_commented_call_beside_real_tool_change() -> None:
    source = "T2 M06 (FINISH) (T99 M06)"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=2,
            line_number=1,
            raw_line=source,
            comments=("FINISH", "T99 M06"),
        )
    ]


def test_preserves_raw_line_and_uses_one_based_line_number() -> None:
    source = "G00 X0\n  T07 M6   (ROUGHER)  \nM30"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=7,
            line_number=2,
            raw_line="  T07 M6   (ROUGHER)  ",
            comments=("ROUGHER",),
        )
    ]


def test_does_not_merge_repeated_tools() -> None:
    source = "T1 M06\nG00 X0\nM6 T01"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ()),
        ToolOccurrence(1, 3, "M6 T01", ()),
    ]


def test_collects_inline_tool_description() -> None:
    source = "T1 M06 (3/4 EM)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, source, ("3/4 EM",))
    ]


def test_collects_supervisor_normal_example() -> None:
    source = "T1 M06\n(Hello)\n(Include this)"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=("Hello", "Include this"),
        )
    ]


def test_collects_multiple_comments_on_one_comment_only_line() -> None:
    source = "T1 M06\n (FIRST)  ( SECOND ) "

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ("FIRST", "SECOND"))
    ]


def test_collects_multiple_comments_after_call_on_tool_line() -> None:
    source = "T1 M06 (3/4 EM) (CHECK HOLDER)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, source, ("3/4 EM", "CHECK HOLDER"))
    ]


def test_does_not_collect_comment_before_complete_tool_call() -> None:
    source = "(SETUP) T1 M06 (3/4 EM)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, source, ("3/4 EM",))
    ]


def test_skips_blank_lines_between_tool_comments() -> None:
    source = "T1 M06\n(FIRST)\n\n \t\n(SECOND)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ("FIRST", "SECOND"))
    ]


def test_includes_comment_on_fifth_following_physical_line() -> None:
    source = "T1 M06\n\n\n\n\n(FIFTH)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ("FIFTH",))
    ]


def test_excludes_comment_on_sixth_following_physical_line() -> None:
    source = "T1 M06\n\n\n\n\n\n(SIXTH)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_stops_immediately_at_executable_gcode() -> None:
    source = "T1 M06\nG00 X0\n(TOO LATE)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_excludes_comment_sharing_line_with_executable_gcode() -> None:
    source = "T2 M06\nG00 G01 X0 (DO NOT INCLUDE THIS)"

    assert find_tool_changes(source) == [
        ToolOccurrence(2, 1, "T2 M06", ())
    ]


def test_stops_at_next_tool_change() -> None:
    source = "T1 M06\n(FIRST)\nT2 M6 (SECOND)\n(AFTER SECOND)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ("FIRST",)),
        ToolOccurrence(2, 3, "T2 M6 (SECOND)", ("SECOND", "AFTER SECOND")),
    ]


def test_no_associated_comments_uses_empty_tuple() -> None:
    assert find_tool_changes("T1 M06") == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_empty_comments_are_ignored_without_stopping_scan() -> None:
    source = "T1 M06 ()\n(   )\n(VALID)"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06 ()", ("VALID",))
    ]


def test_does_not_pair_tool_and_change_on_separate_lines() -> None:
    source = "T1\nM06\n(TOOL DESCRIPTION)"

    assert find_tool_changes(source) == []


def test_stops_after_executable_line_even_when_later_comment_is_close() -> None:
    source = "T3 M06 (DRILL)\n(FIRST)\nG00 X0\n(TOO LATE)"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=3,
            line_number=1,
            raw_line="T3 M06 (DRILL)",
            comments=("DRILL", "FIRST"),
        )
    ]


def test_assigns_g43_h_register_to_active_tool() -> None:
    source = "T1 M06\nG43 H1"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(1,),
        )
    ]


def test_assigns_g41_d_register_to_active_tool() -> None:
    source = "T1 M06\nG41 D1"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            d_registers=(1,),
        )
    ]


def test_assigns_g42_d_register_to_active_tool() -> None:
    source = "T1 M06\nG42 D31"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            d_registers=(31,),
        )
    ]


def test_detects_h_and_d_on_tool_change_line() -> None:
    source = "T1 M06 G43 H7 G41 D12"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line=source,
            comments=(),
            h_registers=(7,),
            d_registers=(12,),
        )
    ]


def test_accepts_compact_lowercase_and_leading_zero_registers() -> None:
    source = "t1m6\ng43h007\ng42d031"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="t1m6",
            comments=(),
            h_registers=(7,),
            d_registers=(31,),
        )
    ]


def test_accepts_register_before_activation_command() -> None:
    source = "T1 M06\nH7 G43\nD31 G42"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(7,),
            d_registers=(31,),
        )
    ]


def test_ignores_h_and_d_values_inside_comments() -> None:
    source = (
        "T1 M06\n"
        "(G43 H99)\n"
        "G43 H1 (H2)\n"
        "(G41 D99)\n"
        "G41 D1 (D2)"
    )

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=("G43 H99",),
            h_registers=(1,),
            d_registers=(1,),
        )
    ]


def test_ignores_standalone_h_without_g43() -> None:
    source = "T1 M06\nH7"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_ignores_standalone_d_without_g41_or_g42() -> None:
    source = "T1 M06\nD31"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_g40_does_not_activate_d_register_detection() -> None:
    source = "T1 M06\nG40 D31"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_standalone_preloaded_tool_does_not_end_active_section() -> None:
    source = "T1 M06\nT2\nG43 H1\nG41 D1\nT2 M06"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(1,),
            d_registers=(1,),
        ),
        ToolOccurrence(
            tool_number=2,
            line_number=5,
            raw_line="T2 M06",
            comments=(),
        ),
    ]


def test_next_real_tool_change_starts_new_register_section() -> None:
    source = "T1 M06\nG43 H1\nG41 D1\nT2 M06\nG43 H2\nG42 D2"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(1,),
            d_registers=(1,),
        ),
        ToolOccurrence(
            tool_number=2,
            line_number=4,
            raw_line="T2 M06",
            comments=(),
            h_registers=(2,),
            d_registers=(2,),
        ),
    ]


def test_commented_tool_change_does_not_end_active_section() -> None:
    source = "T1 M06\n(T6 M06)\nG43 H1\nG41 D1\nT2 M06"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=("T6 M06",),
            h_registers=(1,),
            d_registers=(1,),
        ),
        ToolOccurrence(
            tool_number=2,
            line_number=5,
            raw_line="T2 M06",
            comments=(),
        ),
    ]


def test_commented_tool_change_beside_gcode_does_not_create_boundary() -> None:
    source = "T1 M06\nG00 X0 (T6 M06)\nG43 H1\nT2 M06\nG43 H2"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(1,),
        ),
        ToolOccurrence(
            tool_number=2,
            line_number=4,
            raw_line="T2 M06",
            comments=(),
            h_registers=(2,),
        ),
    ]


def test_commented_t6_m06_alone_creates_no_occurrence() -> None:
    assert find_tool_changes("(T6 M06)") == []


def test_deduplicates_repeated_registers_within_active_section() -> None:
    source = (
        "T1 M06\n"
        "G43 H1\n"
        "G43 H01\n"
        "G41 D2\n"
        "G42 D002"
    )

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(1,),
            d_registers=(2,),
        )
    ]


def test_preserves_distinct_registers_in_first_use_order() -> None:
    source = (
        "T1 M06\n"
        "G43 H3\n"
        "G43 H1\n"
        "G43 H2\n"
        "G41 D4\n"
        "G42 D2\n"
        "G41 D3"
    )

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(3, 1, 2),
            d_registers=(4, 2, 3),
        )
    ]


def test_repeated_tool_calls_keep_separate_register_sets() -> None:
    source = "T1 M06\nG43 H1\nG41 D1\nT1 M06\nG43 H2\nG42 D2"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(1,),
            d_registers=(1,),
        ),
        ToolOccurrence(
            tool_number=1,
            line_number=4,
            raw_line="T1 M06",
            comments=(),
            h_registers=(2,),
            d_registers=(2,),
        ),
    ]


def test_ignores_registers_before_first_real_tool_change() -> None:
    source = "G43 H9\nG41 D9\nT1 M06"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 3, "T1 M06", ())
    ]


def test_register_scanning_preserves_existing_comment_association() -> None:
    source = "T1 M06 (INLINE)\n(FOLLOWING)\nG43 H1\n(TOO LATE)"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06 (INLINE)",
            comments=("INLINE", "FOLLOWING"),
            h_registers=(1,),
        )
    ]


def test_decimal_d_value_is_not_treated_as_integer_register() -> None:
    source = "T1 M06\nG41 D0.7500"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_decimal_h_value_is_not_treated_as_integer_register() -> None:
    source = "T1 M06\nG43 H1.250"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_decimal_g43_variant_is_not_treated_as_g43() -> None:
    source = "T1 M06\nG43.4 H9"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_decimal_g41_and_g42_variants_do_not_activate_d_registers() -> None:
    source = "T1 M06\nG41.1 D5\nG42.1 D5"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", ())
    ]


def test_integer_register_forms_remain_supported() -> None:
    source = "T1 M06\nG43H7\nG41D31\nG42 D4"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=1,
            raw_line="T1 M06",
            comments=(),
            h_registers=(7,),
            d_registers=(31, 4),
        )
    ]


def test_empty_program_has_no_declared_tools() -> None:
    assert find_declared_tools("") == []


def test_program_without_header_tool_list_has_no_declarations() -> None:
    source = "(OPERATION 1)\nG00 X0\nT1 M06"

    assert find_declared_tools(source) == []


def test_finds_one_declared_tool() -> None:
    source = (
        '(T17 - 3/16 EM 0.375"FL 0.5"OUT ER16 - H17 - D17 - D0.1875")'
    )

    assert find_declared_tools(source) == [
        DeclaredTool(
            tool_number=17,
            line_number=1,
            raw_line=source,
            details='3/16 EM 0.375"FL 0.5"OUT ER16 - H17 - D17 - D0.1875"',
        )
    ]


def test_preserves_multiple_declarations_in_header_order() -> None:
    source = (
        "(T3 - DRILL)\n"
        "(PROGRAM INFORMATION)\n"
        "(T1 - ROUGHER)\n"
        "(ANOTHER HEADER COMMENT)\n"
        "(T2 - FINISHER)\n"
        "T3 M06"
    )

    assert find_declared_tools(source) == [
        DeclaredTool(3, 1, "(T3 - DRILL)", "DRILL"),
        DeclaredTool(1, 3, "(T1 - ROUGHER)", "ROUGHER"),
        DeclaredTool(2, 5, "(T2 - FINISHER)", "FINISHER"),
    ]


def test_accepts_lowercase_declared_tool() -> None:
    source = "(t4 - SPOT DRILL)"

    assert find_declared_tools(source) == [
        DeclaredTool(4, 1, source, "SPOT DRILL")
    ]


def test_normalizes_leading_zero_declared_tool() -> None:
    source = "(T007 - FINISHER)"

    assert find_declared_tools(source) == [
        DeclaredTool(7, 1, source, "FINISHER")
    ]


@pytest.mark.parametrize(
    "source",
    [
        "(T1 - DESCRIPTION)",
        "(T1- DESCRIPTION)",
        "(T1 -DESCRIPTION)",
        "(T1-DESCRIPTION)",
    ],
)
def test_accepts_flexible_spacing_around_declaration_hyphen(
    source: str,
) -> None:
    assert find_declared_tools(source) == [
        DeclaredTool(1, 1, source, "DESCRIPTION")
    ]


def test_preserves_declaration_raw_line_and_one_based_line_number() -> None:
    raw_line = " \t(T2 - BALL MILL)  "
    source = f"(HEADER)\n{raw_line}\nT2 M06"

    assert find_declared_tools(source) == [
        DeclaredTool(
            tool_number=2,
            line_number=2,
            raw_line=raw_line,
            details="BALL MILL",
        )
    ]


def test_preserves_repeated_declarations_separately() -> None:
    source = "(T1 - FIRST)\n(T1 - SECOND)\nT1 M06"

    assert find_declared_tools(source) == [
        DeclaredTool(1, 1, "(T1 - FIRST)", "FIRST"),
        DeclaredTool(1, 2, "(T1 - SECOND)", "SECOND"),
    ]


def test_ignores_ordinary_header_comments() -> None:
    source = "(OPERATION 1)\n(USE T1 - CHECK)\n()\n(T2 - DRILL)"

    assert find_declared_tools(source) == [
        DeclaredTool(2, 4, "(T2 - DRILL)", "DRILL")
    ]


def test_commented_tool_call_is_not_a_declaration() -> None:
    assert find_declared_tools("(T1 M06)") == []


def test_commented_fake_tool_call_does_not_end_header_scan() -> None:
    source = "(T6 M06)\n(T1 - ROUGHER)\nT1 M06"

    assert find_declared_tools(source) == [
        DeclaredTool(1, 2, "(T1 - ROUGHER)", "ROUGHER")
    ]


def test_executable_tool_call_with_comment_is_not_a_declaration() -> None:
    source = "T1 M06 (DESCRIPTION)"

    assert find_declared_tools(source) == []


def test_ignores_declaration_like_comments_after_first_real_tool_change() -> None:
    source = "(T1 - BEFORE)\nT1 M06\n(T2 - AFTER)"

    assert find_declared_tools(source) == [
        DeclaredTool(1, 1, "(T1 - BEFORE)", "BEFORE")
    ]


def test_searches_entire_program_when_no_real_tool_change_exists() -> None:
    source = "G00 X0\n(ORDINARY COMMENT)\n(T4 - LATE DECLARATION)"

    assert find_declared_tools(source) == [
        DeclaredTool(4, 3, "(T4 - LATE DECLARATION)", "LATE DECLARATION")
    ]


@pytest.mark.parametrize("source", ["(T1 - )", "(T1-)", "(T1 -    )"])
def test_rejects_declarations_with_empty_details(source: str) -> None:
    assert find_declared_tools(source) == []


@pytest.mark.parametrize(
    "source",
    [
        "(T1 - UNCLOSED",
        "T1 - MISSING OPEN)",
        "(T1 - FIRST)(T2 - SECOND)",
    ],
)
def test_rejects_malformed_declaration_comments(source: str) -> None:
    assert find_declared_tools(source) == []


def test_declared_tool_scanning_does_not_change_tool_occurrences() -> None:
    source = "(T1 - ROUGHER)\nT1 M06 (INLINE)\nG43 H1\nG41 D1"

    find_declared_tools(source)

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=1,
            line_number=2,
            raw_line="T1 M06 (INLINE)",
            comments=("INLINE",),
            h_registers=(1,),
            d_registers=(1,),
        )
    ]