from gcode_tool_list.models import ToolGroup, ToolOccurrence
from gcode_tool_list.parser import find_tool_changes
from gcode_tool_list.tool_list import group_tool_occurrences


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
