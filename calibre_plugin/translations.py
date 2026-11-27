# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Texts of the plugin in the language of the calibre interface: English
in the code, Polish in POLISH below, other languages get English. Plain
Python (calibre is only asked for its language), so it can be tested
without calibre."""

POLISH = {
    # __init__.py: description in Preferences > Plugins
    'Fixes the selected EPUB books like “epubQTools -e”. The fixed version '
    'becomes the EPUB format, the original is kept in the data files of '
    'the book.':
    'Poprawia zaznaczone książki EPUB tak jak „epubQTools -e”. Poprawiona '
    'wersja staje się formatem EPUB, oryginał zostaje w plikach danych '
    'książki.',

    # action.py: toolbar button and its menu
    'Fix the selected EPUB books (like epubQTools -e)':
    'Popraw zaznaczone książki EPUB (jak epubQTools -e)',
    'Fix the selected books': 'Popraw zaznaczone książki',
    'Restore the original': 'Przywróć oryginał',
    'Settings…': 'Ustawienia…',

    # action.py: fixing
    'No book is selected.': 'Nie zaznaczono żadnej książki.',
    'None of the selected books has the EPUB format.':
    'Żadna z zaznaczonych książek nie ma formatu EPUB.',
    'epubQTools: fixing books (%d)': 'epubQTools: poprawianie książek (%d)',
    'epubQTools: fixing books (%d)…':
    'epubQTools: poprawianie książek (%d)…',
    'epubQTools: unexpected error': 'epubQTools: nieoczekiwany błąd',
    'Another library was opened while working – the fixed books were not '
    'saved.':
    'W trakcie pracy otwarto inną bibliotekę – poprawione książki nie '
    'zostały zapisane.',

    # action.py: window with the result
    'Fixed: %d of %d': 'Poprawione: %d z %d',
    'Saved, but with problems (see details):':
    'Zapisane, ale z problemami (zob. szczegóły):',
    'Could not be fixed (no changes in the library):':
    'Nie udało się poprawić (bez zmian w bibliotece):',
    'Removed from the library while working:':
    'Usunięte z biblioteki w trakcie pracy:',
    'Without the EPUB format (skipped):': 'Bez formatu EPUB (pominięte):',

    # action.py: restoring the original
    'The selected books have no original saved by epubQTools.':
    'Zaznaczone książki nie mają oryginału zachowanego przez epubQTools.',
    'Restore the original in the selected books (%d)? The fixed EPUB will '
    'be replaced with the original saved by epubQTools.':
    'Przywrócić oryginał w zaznaczonych książkach (%d)? Poprawiona wersja '
    'EPUB zostanie zastąpiona oryginałem zachowanym przez epubQTools.',
    'epubQTools: original restored (%d)':
    'epubQTools: przywrócono oryginał (%d)',

    # config.py: settings window
    'Hyphenation': 'Dzielenie wyrazów',
    'Hyphenate words': 'Dziel wyrazy',
    'Hyphenate also words in headings (h1, h2, h3…)':
    'Dziel też wyrazy w nagłówkach (h1, h2, h3…)',
    'Text appearance': 'Wygląd tekstu',
    'Add a CSS reset': 'Dołącz reset CSS',
    'Without this option a hyphenated book gets only the CSS “hyphens: '
    'manual”.':
    'Bez tej opcji książka dzielona dostaje tylko CSS „hyphens: manual”.',
    'Text alignment:': 'Wyrównanie tekstu:',
    'Justify text aligned to the left':
    'Wyjustuj tekst wyrównany do lewej',
    'Align justified text to the left':
    'Wyrównaj do lewej tekst wyjustowany',
    'No change': 'Bez zmian',
    'Remove colors': 'Usuń kolory',
    'Colors are removed when the alignment is changed, so this option '
    'works only when the alignment is not “No change”.':
    'Kolory są usuwane przy zmianie wyrównania, więc ta opcja działa tylko '
    'wtedy, gdy wyrównanie nie jest „Bez zmian”.',
    'Left and right margin:': 'Margines lewy i prawy:',
    'Fonts': 'Fonty',
    'Remove embedded fonts': 'Usuń wbudowane fonty',
    'Other': 'Inne',
    'Add an approximate page list (in books without one)':
    'Dodaj przybliżoną listę stron (w książkach bez niej)',
    'The margin is written to the CSS reset, so this option works only '
    'with “Add a CSS reset”.':
    'Margines jest zapisywany w resecie CSS, więc ta opcja działa tylko '
    'z „Dołącz reset CSS”.',
    'Restore defaults': 'Przywróć domyślne',
    'Settings like “-c -r -e” in the terminal.':
    'Ustawienia jak „-c -r -e” w terminalu.',
}

TRANSLATIONS = {'pl': POLISH}


def language():
    """Language of the calibre interface, e.g. 'pl' or 'pt_BR' ('en'
    outside calibre)."""
    try:
        from calibre.utils.localization import get_lang
    except ImportError:
        return 'en'
    return get_lang() or 'en'


def tr(text, lang=None):
    """text (English) in the language of calibre, or in lang."""
    lang = (lang or language()).replace('-', '_').split('_')[0].lower()
    return TRANSLATIONS.get(lang, {}).get(text, text)
