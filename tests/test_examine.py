from gcode_tool_list.examine import filter_lines


def test_searches_for_opening_parenthesis() -> None:
    source = "G00 X0\n(T1 ROUGHER)\nG01 X1\n(END)\n"

    assert filter_lines(source, "(") == "(T1 ROUGHER)\n(END)\n"


def test_searches_for_m06() -> None:
    source = "T01 M06\nG00 X0\nT02 M06\n"

    assert filter_lines(source, "M06") == "T01 M06\nT02 M06\n"


def test_search_is_case_insensitive_by_default() -> None:
    source = "M06\nm06\nM03\n"

    assert filter_lines(source, "m06") == "M06\nm06\n"


def test_returns_empty_string_when_no_lines_match() -> None:
    assert filter_lines("G00 X0\nG01 X1\n", "M06") == ""


def test_returns_empty_string_for_empty_search() -> None:
    assert filter_lines("G00 X0\nM06\n", "") == ""


def test_preserves_exact_whitespace_and_line_endings() -> None:
    source = "  M06  \r\n\tG00 M06 X0\nM03\rM06"

    assert filter_lines(source, "M06") == "  M06  \r\n\tG00 M06 X0\nM06"


def test_case_sensitive_search_only_returns_exact_case() -> None:
    source = "M06\nm06\n"

    assert filter_lines(source, "M06", case_sensitive=True) == "M06\n"
