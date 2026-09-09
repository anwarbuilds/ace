"""Tests for the shared HTML-unescape helper.

A single ``html.unescape`` pass was found leaving a literal six-
character ``&nbsp;`` in 14,855 stored Greenhouse descriptions, because
the source content was double-encoded (``&amp;nbsp;``). These tests
pin the fixed-point behaviour that fix depends on.
"""

from backend.app.adapters.html_text import unescape_fully


def test_a_single_encoded_entity_is_decoded() -> None:
    assert (
        unescape_fully("Full&nbsp;time")
        == "Full\xa0time"
    )


def test_a_double_encoded_entity_is_fully_decoded() -> None:
    # This is the exact shape found in stored Greenhouse content: one
    # html.unescape() pass only resolves the outer layer and leaves
    # the literal string "&nbsp;" behind, which looks clean but is
    # not whitespace to a phrase-matching regex.
    assert (
        unescape_fully("Full&amp;nbsp;time")
        == "Full\xa0time"
    )


def test_plain_text_with_no_entities_is_unchanged() -> None:
    text = "Software Engineer, New Grad"

    assert unescape_fully(text) == text


def test_ordinary_single_encoding_still_works() -> None:
    assert (
        unescape_fully("Terms &amp; Conditions")
        == "Terms & Conditions"
    )


def test_a_pathological_run_of_amp_does_not_loop_forever() -> None:
    # Each pass of html.unescape() only peels one "&amp;" layer off an
    # "&amp;amp;...;" run, so a deeply nested run legitimately needs
    # more than MAX_UNESCAPE_PASSES passes to fully resolve. The loop
    # must still terminate in bounded time rather than hang, even
    # though it will not have fully decoded a case that deep.
    text = "&amp;" * 20 + "nbsp;"

    result = unescape_fully(text)

    assert isinstance(result, str)
