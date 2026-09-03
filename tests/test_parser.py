import pytest

from gcode_tool_list.models import ToolOccurrence
from gcode_tool_list.parser import find_tool_changes


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