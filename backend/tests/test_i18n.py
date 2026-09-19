"""
The interface languages, held to three rules.

The dictionary lives in the frontend (`frontend/src/i18n/strings.js`) because
that is where the words are used. These tests read it as text — no Node
needed — and check the things that break quietly:

  * every phrase exists in every language, so switching does not leave the
    page half English
  * placeholders survive translation: a sentence that loses its {n} renders
    the literal text and swallows the number
  * the server and the browser agree on which languages exist, so a
    preference the browser offers cannot be refused when it is saved
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
STRINGS = ROOT / "frontend" / "src" / "i18n" / "strings.js"
INDEX = ROOT / "frontend" / "src" / "i18n" / "index.js"

ENTRY = re.compile(r"^\s*'([\w.]+)':\s*\{(.*?)\},?\s*$", re.S | re.M)
LANG_VALUE = re.compile(r"\b(en|hi|te):\s*(['\"])(.*?)(?<!\\)\2", re.S)
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def phrases() -> dict[str, dict[str, str]]:
    text = STRINGS.read_text(encoding="utf-8")
    body = text[text.index("export const STRINGS = {"):]
    found: dict[str, dict[str, str]] = {}
    for key, block in ENTRY.findall(body):
        found[key] = {lang: value for lang, _q, value in LANG_VALUE.findall(block)}
    return found


ALL = phrases()


def test_the_dictionary_was_actually_read():
    """A parse that matched nothing would make every test below pass vacuously."""
    assert len(ALL) > 80, f"only {len(ALL)} phrases parsed from {STRINGS.name}"
    assert ALL["nav.dashboard"]["en"] == "Dashboard"


@pytest.mark.parametrize("language", ["hi", "te"])
def test_every_phrase_exists_in_every_language(language):
    missing = sorted(key for key, langs in ALL.items() if not langs.get(language))
    assert not missing, f"{language}: {len(missing)} phrases missing, e.g. {missing[:5]}"


def test_placeholders_survive_translation():
    """`{n} min` translated without its {n} would drop the number silently."""
    for key, langs in ALL.items():
        expected = set(PLACEHOLDER.findall(langs["en"]))
        for language, text in langs.items():
            assert set(PLACEHOLDER.findall(text)) == expected, (
                f"{key} ({language}) has {set(PLACEHOLDER.findall(text))}, "
                f"English has {expected}")


def test_the_server_and_the_browser_offer_the_same_languages():
    from app.services.auth_service import LANGUAGES

    in_browser = set(re.findall(r"code: '(\w+)'", INDEX.read_text(encoding="utf-8")))
    assert in_browser == set(LANGUAGES), (
        "the language picker offers what the server would refuse to save: "
        f"browser={sorted(in_browser)} server={sorted(LANGUAGES)}")
