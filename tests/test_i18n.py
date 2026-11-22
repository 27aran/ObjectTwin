import string

import pytest

from objecttwin.gui import i18n


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.mark.parametrize("key", sorted(i18n.all_keys()))
def test_every_key_is_translated_consistently(key: str) -> None:
    entry = i18n.all_keys()[key]
    assert set(entry) == set(i18n.LANGUAGES), f"{key}: missing languages"
    assert all(entry.values()), f"{key}: empty translation"
    reference = _placeholders(entry[i18n.DEFAULT_LANGUAGE])
    for code, text in entry.items():
        assert _placeholders(text) == reference, f"{key} [{code}]: placeholders differ"


def test_switch_language() -> None:
    try:
        i18n.set_language("de")
        assert i18n.tr("btn.search") == "Suchen"
        assert i18n.tr("status.done", scanned=3, seconds="1,5") == "3 Bilder in 1,5 s verglichen"
        i18n.set_language("en")
        assert i18n.tr("btn.search") == "Search"
    finally:
        i18n.set_language(i18n.DEFAULT_LANGUAGE)


def test_unknown_language_rejected() -> None:
    with pytest.raises(ValueError):
        i18n.set_language("fr")
