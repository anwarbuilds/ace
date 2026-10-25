"""The substring shortcut in extract_skills must never change its answer.

extract_skills skips an alias's regular expression when the text the
alias needs is absent. That is only safe if the needed text is truly
needed, and if case folding cannot hide it, so both are proved here.
"""

import re
import string

try:
    from re import _parser as sre_parse
except ImportError:  # Python before 3.11
    import sre_parse

from backend.app.matching import skills
from backend.app.matching.skills import (
    COMPILED_SKILLS,
    SKILL_ALIASES,
    extract_skills,
)


def reference(text: str) -> frozenset[str]:
    """extract_skills as it was: every pattern, every time."""

    if not text:
        return frozenset()
    return frozenset(
        skill
        for skill, patterns in COMPILED_SKILLS.items()
        if any(pattern.search(text) for pattern in patterns)
    )


def test_fold_table_is_every_character_ignorecase_matches_to_ascii() -> None:
    """Checked over the whole Basic Multilingual Plane.

    On 2026-10-25 the full Unicode range gave the same four characters.
    """

    patterns = {letter: re.compile(letter, re.IGNORECASE) for letter in string.ascii_lowercase}
    found = {}
    for code in range(0x80, 0x10000):
        character = chr(code)
        for letter, pattern in patterns.items():
            if pattern.fullmatch(character):
                found[character] = letter

    assert found == {"İ": "i", "ı": "i", "ſ": "s", "K": "k"}
    assert {chr(code): value for code, value in skills._FOLD_TO_ASCII.items()} == found


def mandatory_runs(pattern: str) -> list[str]:
    """Runs of plain characters every match of the pattern contains."""

    runs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            runs.append("".join(current))
            current.clear()

    def walk(items) -> None:
        for op, value in items:
            name = str(op)
            if name == "LITERAL":
                current.append(chr(value))
            elif name == "SUBPATTERN":
                walk(value[-1])
            else:
                # Optional or repeated parts, classes, alternatives and
                # boundaries all end a run.
                flush()

    walk(sre_parse.parse(pattern))
    flush()
    return runs


def test_every_alias_written_as_a_pattern_has_text_it_truly_needs() -> None:
    patterned = {
        alias
        for aliases in SKILL_ALIASES.values()
        for alias in aliases
        if skills._REGEX_SYNTAX.search(alias)
    }

    assert patterned == set(skills._PATTERN_REQUIRES)

    for alias, required in skills._PATTERN_REQUIRES.items():
        runs = [run.lower() for run in mandatory_runs(alias)]
        assert any(required in run for run in runs), (alias, required, runs)


def test_plain_aliases_need_exactly_their_own_text() -> None:
    for skill, aliases in SKILL_ALIASES.items():
        for alias, required in zip(aliases, skills._REQUIRED_TEXT[skill]):
            if not skills._REGEX_SYNTAX.search(alias):
                assert required == alias.lower()


SAMPLES = [
    "C++ and Node.js, Express.js, React.js, Next.js and Vue.js",
    "HuggingFace models; Hugging Face hub; huggingface",
    "on call rotation, on-call, oncall",
    "Single sign-on and single signon",
    "large-scale, large scale, high-throughput, high throughput",
    "horizontally scalable services; horizontal scaling",
    "high availability, fault-tolerant, fault tolerance, resilient, resilience",
    "low-latency, low latency, real-time, realtime, latency-sensitive",
    "event-driven, event driven, pub/sub, pubsub, publish-subscribe",
    "data modelling and data modeling, IaC, helm charts, helm chart",
    "A/B testing, a/b tests, A/B test",
    # The four characters case-insensitive matching treats as letters.
    "ſql and Kafka and İaC and kıtchen",
    # Near misses and boundaries.
    "javascripts, Javan, reacting, cpp, nodejs, c+, golang, go-to",
    "",
]


def test_samples_match_the_reference_exactly() -> None:
    for text in SAMPLES:
        assert extract_skills(text) == reference(text), text


def test_every_alias_in_every_case_matches_the_reference() -> None:
    for aliases in SKILL_ALIASES.values():
        for alias in aliases:
            if skills._REGEX_SYNTAX.search(alias):
                continue
            for variant in (alias, alias.upper(), alias.title(), f"x{alias}x", f"({alias})."):
                text = f"We use {variant} daily."
                assert extract_skills(text) == reference(text), text
