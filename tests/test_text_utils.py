from backend.text_utils import html_to_text, truncate


def test_html_to_text_strips_tags():
    result = html_to_text("<p>Hello <b>world</b></p>")
    assert result == "Hello world"


def test_html_to_text_decodes_entities():
    result = html_to_text("<p>AT&amp;T</p>")
    assert result == "AT&T"


def test_html_to_text_collapses_whitespace():
    result = html_to_text("<div>A  B   C</div>")
    assert result == "A B C"


def test_truncate_short_text():
    assert truncate("abcdef", 10) == "abcdef"


def test_truncate_long_text():
    assert truncate("abcdef", 3) == "abc"
