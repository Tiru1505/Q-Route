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


# ------------------------------------------------ machine-translated languages
#
# The other twenty scheduled languages live one file per language in
# frontend/src/i18n/machine and are fetched only when chosen. They are machine
# translations and the picker says so — but they are held to the same rules
# as the three written for the app, because a missing phrase or a dropped
# {n} breaks a page just as badly whoever did the translating.

MACHINE_DIR = ROOT / "frontend" / "src" / "i18n" / "machine"


def machine_codes() -> list[str]:
    text = INDEX.read_text(encoding="utf-8")
    return re.findall(r"code: '(\w+)'[^}]*machine: true", text)


MACHINE = machine_codes()


def test_the_machine_languages_were_actually_found():
    """Twenty expected; a broken pattern would make the checks below vacuous."""
    assert len(MACHINE) == 20, f"found {len(MACHINE)} machine languages: {MACHINE}"


@pytest.mark.parametrize("language", MACHINE)
def test_each_machine_language_has_a_file(language):
    assert (MACHINE_DIR / f"{language}.json").is_file(), f"no machine/{language}.json"


@pytest.mark.parametrize("language", MACHINE)
def test_each_machine_language_is_complete(language):
    import json
    words = json.loads((MACHINE_DIR / f"{language}.json").read_text(encoding="utf-8"))
    missing = sorted(key for key in ALL if not str(words.get(key, "")).strip())
    stale = sorted(key for key in words if key not in ALL)
    assert not missing, f"{language}: {len(missing)} phrases missing, e.g. {missing[:5]}"
    assert not stale, f"{language}: phrases for keys that no longer exist: {stale[:5]}"


@pytest.mark.parametrize("language", MACHINE)
def test_each_machine_language_keeps_its_placeholders(language):
    import json
    words = json.loads((MACHINE_DIR / f"{language}.json").read_text(encoding="utf-8"))
    for key, english in ((k, v["en"]) for k, v in ALL.items()):
        expected = set(PLACEHOLDER.findall(english))
        got = set(PLACEHOLDER.findall(words.get(key, "")))
        assert got == expected, f"{key} ({language}) has {got}, English has {expected}"
