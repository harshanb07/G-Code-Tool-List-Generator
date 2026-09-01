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
            inline_comment=None,
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
            inline_comment="FINISH",
        )
    ]


def test_preserves_raw_line_and_uses_one_based_line_number() -> None:
    source = "G00 X0\n  T07 M6   (ROUGHER)  \nM30"

    assert find_tool_changes(source) == [
        ToolOccurrence(
            tool_number=7,
            line_number=2,
            raw_line="  T07 M6   (ROUGHER)  ",
            inline_comment="ROUGHER",
        )
    ]


def test_does_not_merge_repeated_tools() -> None:
    source = "T1 M06\nG00 X0\nM6 T01"

    assert find_tool_changes(source) == [
        ToolOccurrence(1, 1, "T1 M06", None),
        ToolOccurrence(1, 3, "M6 T01", None),
    ]
