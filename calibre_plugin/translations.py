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
    'Download the new version…': 'Pobierz nową wersję…',

    # action.py: new version on GitHub
    'New version %s – download…': 'Nowa wersja %s – pobierz…',
    'A new version of epubQTools is available: %s (you have %s). Open the '
    'download page?':
    'Jest nowa wersja epubQTools: %s (masz %s). Otworzyć stronę '
    'pobierania?',

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

    # action.py, sendtokindle.py: passing to Send to Kindle
    'Pass to Send to Kindle…': 'Przekaż do Send to Kindle…',
    'None of the selected books was fixed by epubQTools – fix them first.':
    'Żadna z zaznaczonych książek nie została poprawiona przez epubQTools '
    '– najpierw je popraw.',
    'calibre has no built-in browser, so the page was opened in your web '
    'browser and the folder with the books (%d) next to it. Drag the books '
    'to the page and click the button for sending.':
    'calibre nie ma wbudowanej przeglądarki, więc strona otworzyła się '
    'w Twojej przeglądarce, a obok folder z książkami (%d). Przeciągnij '
    'książki na stronę i kliknij przycisk wysyłania.',
    'Skipped – not fixed by epubQTools:':
    'Pominięte – niepoprawione przez epubQTools:',
    'Ready to send (%d): %s': 'Gotowe do wysłania (%d): %s',
    'Skipped – not fixed by epubQTools (%d): %s':
    'Pominięte – niepoprawione przez epubQTools (%d): %s',
    'Click the button for choosing files on the page – the books are added '
    'by themselves – and then the button for sending.':
    'Kliknij na stronie przycisk wybierania plików – książki dodadzą się '
    'same – a potem przycisk wysyłania.',
    'Send via my browser…': 'Wyślij przez moją przeglądarkę…',
    'For sending without logging in here: opens the page in your web '
    'browser and the folder with the books next to it – drag the books to '
    'the page.':
    'Do wysyłania bez logowania się tutaj: otwiera stronę w Twojej '
    'przeglądarce, a obok folder z książkami – przeciągnij książki na '
    'stronę.',
    'Forget the saved login': 'Usuń zapamiętane logowanie',
    'Prefer not to log in here? Use “Send via my browser…”.':
    'Wolisz nie logować się tutaj? Użyj przycisku „Wyślij przez moją '
    'przeglądarkę…”.',
    'Removes the Amazon login remembered on this computer.':
    'Usuwa zapamiętane na tym komputerze logowanie do Amazona.',
    'Secure connection: %s': 'Bezpieczne połączenie: %s',
    '%s – not a secure Amazon page, do not log in here':
    '%s – to nie jest bezpieczna strona Amazona, nie loguj się tutaj',
    'You log in directly on the Amazon page. The plugin does not read your '
    'password and sends nothing by itself – its code is open.':
    'Logujesz się bezpośrednio na stronie Amazona. Wtyczka nie czyta hasła '
    'i sama niczego nie wysyła – jej kod jest otwarty.',
    'The page was opened in your web browser and the folder with the books '
    'next to it. Drag the books to the page and click the button for '
    'sending. The folder is removed when calibre is closed.':
    'Strona otworzyła się w Twojej przeglądarce, a obok folder z książkami. '
    'Przeciągnij książki na stronę i kliknij przycisk wysyłania. Folder '
    'zostanie usunięty po zamknięciu calibre.',
    'The Amazon login remembered on this computer was removed.':
    'Usunięto zapamiętane na tym komputerze logowanie do Amazona.',

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
    'Remove embedded fonts': 'Usuń wbudowane fonty',
    'Other': 'Inne',
    'Add an approximate page list (in books without one)':
    'Dodaj przybliżoną listę stron (w książkach bez niej)',
    'The margin is written to the CSS reset, so this option works only '
    'with “Add a CSS reset”.':
    'Margines jest zapisywany w resecie CSS, więc ta opcja działa tylko '
    'z „Dołącz reset CSS”.',
    'Passing to Send to Kindle': 'Przekazywanie do Send to Kindle',
    'Amazon site:': 'Strona Amazona:',
    'The site of your Amazon account, where “Pass to Send to Kindle…” '
    'opens the Send to Kindle page.':
    'Strona Twojego konta Amazon, na której „Przekaż do Send to Kindle…” '
    'otwiera stronę Send to Kindle.',
    'New versions': 'Nowe wersje',
    'Check for a new version of the plugin on GitHub (once a day)':
    'Sprawdzaj nową wersję wtyczki na GitHubie (raz dziennie)',
    'calibre asks GitHub once a day whether a newer version of epubQTools '
    'was released. Nothing about your books is sent.':
    'calibre raz dziennie pyta GitHuba, czy wyszła nowsza wersja '
    'epubQTools. Nic o Twoich książkach nie jest wysyłane.',
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
