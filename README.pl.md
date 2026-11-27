epubQTools [![Release](https://img.shields.io/github/release/quiris11/epubqtools.svg)](https://github.com/quiris11/epubqtools/releases/latest)
==========

[English version](README.md)

Narzędzia do sprawdzania, poprawiania i dzielenia wyrazów w książkach EPUB,
przede wszystkim z myślą o czytnikach Kindle (Send to Kindle). epubQTools
poprawia to, co psuje czytanie (błędy w CSS, okładki, linki, przypisy,
zaciemnione fonty…), dzieli wyrazy w polskich książkach, dodaje przybliżoną
listę stron i usuwa teksty oraz strony dodawane przez niektóre księgarnie.

Można z niego korzystać na dwa sposoby:
* **wtyczka do calibre** – najprościej, bez terminala: zaznaczasz książki
  w calibre i klikasz przycisk. Wtyczka poprawia książki (tak jak `-e` niżej).
* **wiersz poleceń (terminal)** – wszystkie funkcje: poprawianie, sprawdzanie
  (także programem EpubCheck), zmiana nazw plików, przygotowanie plików do
  Send to Kindle, zamiana na MOBI programem kindlegen.

Oryginalne pliki nie są zmieniane: poprawione książki to nowe pliki (a w calibre
nowa wersja książki, przy czym oryginał zostaje zachowany). Oryginały zmieniają
tylko `-n`, `--author`, `--title` i `--fix-missing-container`.

## Wtyczka do calibre

### Instalacja
Potrzebny jest calibre 6.0 lub nowszy (https://calibre-ebook.com).
1. Pobierz plik **epubQTools-calibre-WERSJA.zip** z
   [najnowszego wydania](https://github.com/quiris11/epubQTools/releases/latest)
   (w części „Assets”). Nie rozpakowuj go.
2. W calibre wybierz **Ustawienia → Wtyczki → Wczytaj wtyczkę z pliku**
   i wskaż pobrany plik.
   Potwierdź ostrzeżenie o instalowaniu wtyczki.
3. calibre zapyta, gdzie pokazać przycisk wtyczki: zaznacz **Główny pasek
   narzędzi**.
4. Uruchom calibre ponownie. Przycisk **epubQTools** jest na pasku narzędzi.

Jeśli przycisku nie ma, dodaj go w **Ustawienia → Paski narzędzi i menu →
Główny pasek narzędzi** (wybierz „epubQTools” z listy dostępnych poleceń).

Aktualizacja: zainstaluj nowy plik tak samo (ustawienia zostają).
Usunięcie: **Ustawienia → Wtyczki**, zaznacz „epubQTools”, **Usuń wtyczkę**.

### Używanie
Wtyczka mówi językiem calibre: po polsku, gdy calibre jest po polsku, a w innym
razie po angielsku.

Zaznacz jedną lub więcej książek i kliknij przycisk **epubQTools** (albo strzałkę
obok niego, żeby otworzyć menu):
* **Popraw zaznaczone książki** – to samo co kliknięcie przycisku. Poprawiona
  książka zastępuje format EPUB, a oryginał zostaje zachowany jako format
  **ORIGINAL_EPUB**. Oryginał jest zachowywany tylko za pierwszym razem, więc
  ponowne poprawienie książki zaczyna się od oryginału, a nie od poprawionej
  wersji.
* **Przywróć oryginał** – format EPUB znowu staje się oryginałem, a
  ORIGINAL_EPUB jest usuwany.
* **Ustawienia…** – opis niżej.

Książki są poprawiane w tle (widać to na liście zadań calibre), więc w tym czasie
można dalej korzystać z calibre. Na koniec okienko pokazuje, ile książek
poprawiono, i wymienia książki zapisane z problemami (z ostrzeżeniem), książki,
których nie udało się poprawić (np. z DRM – zostają bez zmian), oraz książki bez
formatu EPUB. **Pokaż szczegóły** pokazuje wszystkie komunikaty dla każdej
książki.

### Ustawienia
Ustawienia domyślne dają ten sam wynik co `-c -r -e` w terminalu:

| Ustawienie | Domyślnie | Opcja w terminalu |
|---|---|---|
| Dziel wyrazy (tylko książki po polsku) | tak | `-s` wyłącza |
| Dziel też wyrazy w nagłówkach | nie | włączone bez `-r` |
| Dołącz reset CSS | nie | włączony bez `-c` |
| Wyrównanie tekstu: wyjustuj / do lewej / bez zmian | wyjustuj | – / `--left` / `--skip-justify` |
| Usuń kolory (nie przy „Bez zmian”) | nie | `--remove-colors` |
| Margines lewy i prawy (tylko z „Dołącz reset CSS”) | nie | `--book-margin` |
| Usuń wbudowane fonty | nie | `--remove-fonts` |
| Dodaj przybliżoną listę stron | tak | `--skip-page-list` wyłącza |

## Wiersz poleceń (terminal)

### Instalacja
1. Zainstaluj Pythona 3 (https://www.python.org; w Linuksie zwykle już jest).
2. Pobierz „Source code (zip)” z
   [najnowszego wydania](https://github.com/quiris11/epubQTools/releases/latest)
   i rozpakuj go, np. do katalogu `epubQTools-1.0`.
3. Zainstaluj biblioteki (w Windows zamiast `python3` wpisuj `py`, tu i niżej):
   ```
   python3 -m pip install lxml css-parser tinycss2
   ```
4. Dodatkowe narzędzia (nieobowiązkowe):
   * **EpubCheck** (do `-p`, wymaga Javy): pobierz plik zip z
     https://github.com/w3c/epubcheck/releases (nie rozpakowuj go)
   * **kindlegen** (do `-k`, wystarczy sam rozpakowany program)
   * **pytidylib** z systemową biblioteką libtidy (`python3 -m pip install
     pytidylib`): dodatkowe sprawdzanie HTML w `-q`

   EpubCheck i kindlegen umieść w katalogu narzędzi (albo wskaż inny katalog
   opcją `--tools KATALOG`):
   * Linux/macOS: `~/.local/share/epubQTools/` (`$XDG_DATA_HOME/epubQTools/`,
     jeśli ta zmienna jest ustawiona)
   * Windows: `%LOCALAPPDATA%\epubQTools\`

   Jeśli tego katalogu nie ma, używany jest katalog obok programu (jak
   w starszych wersjach). kindlegen jest szukany także w `PATH`.

### Na początek
Ostatni argument to katalog z książkami (razem z podkatalogami):
```
python3 epubQTools-1.0 -e ~/Książki        # popraw wszystkie książki, wyniki w ~/Książki/MOH/*_moh.epub
python3 epubQTools-1.0 -q ~/Książki        # sprawdź książki
python3 epubQTools-1.0 -q -m ~/Książki     # sprawdź poprawione książki (_moh.epub)
python3 epubQTools-1.0 -i -e ~/Książki     # wybierz w terminalu, które książki poprawić
python3 epubQTools-1.0 -n -e -t ~/Książki  # zmień nazwy oryginałów na „Autor - Tytuł.epub”, popraw je
                                           # i skopiuj do ~/Książki/TS2K jako „Tytuł.epub” do Send to Kindle
```
Książka już poprawiona jest pomijana; `-f` poprawia ją ponownie.

### Wszystkie opcje
Program wypisuje pomoc po angielsku (`-h`):
```
usage: epubQTools [-h] [-V] [--tools [DIR]] [-l [DIR]] [-i [NR]] [--author [Surname, First Name]] [--title [Title]]
                                                        [-v] [-a] [-n] [-t] [-q] [-p] [-w] [-u] [--list-fonts] [-m] [-e] [-s]
                                                        [-r] [--skip-page-list] [-c] [--skip-justify] [--left] [--remove-colors]
                                                        [--remove-fonts] [-k] [-d] [-f] [--fix-missing-container] [--book-margin [NUMBER]]
                                                        directory

positional arguments:
  directory             Directory with EPUB files stored

options:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  --tools [DIR]         path to additional tools: kindlegen, epubcheck zip (default: ~/.local/share/epubQTools)
  -l, --log [DIR]       path to directory to write log file. If DIR is omitted write log to directory with epub files
  -i, --individual [NR]
                        individual file mode: without NR select files in the console (or list them if not run in a terminal), NR
                        processes the files with the given numbers, e.g. "3" or "1,3,5-7"
  --author [Surname, First Name]
                        set new author name (only with -i)
  --title [Title]       set new book title (only with -i
  -v, --verbose         print all messages, also the information about every change (by default only warnings and errors are
                        printed, with the name of the book; the log file always gets all messages)
  -a, --alter           print every finding on one line beginning with the file name, without START and FINISH lines, e.g. for
                        grep or sort (only with -q)
  -n, --rename          rename .epub files to 'author - title.epub'
  -t, --prepare-send-to-kindle
                        copy MOH files to 'title.epub' (Send to Kindle friendly)
  -q, --qcheck          validate files with qcheck internal tool
  -p, --epubcheck       validate epub files with EpubCheck tool
  -w, --skip-font-mime  do not report non-standard font media types (only with -q)
  -u, --skip-css-warnings
                        do not report CSS warnings, only CSS errors (only with -q)
  --list-fonts          list all fonts in EPUB (only with -q)
  -m, --mod             validate only _moh.epub files (works only with -q or -p)
  -e, --epub            fix and hyphenate original epub files to _moh.epub files (saved in 'MOH' subfolder, in the same subfolders as the originals)
  -s, --skip-hyphenate  do not hyphenate book (only with -e)
  -r, --skip-hyphenate-headers
                        do not hyphenate headers like h1, h2, h3...(only with -e)
  --skip-page-list      do not add a list of approximate pages to books without one (only with -e)
  -c, --skip-reset-css  skip linking a full reset CSS file to every xthml file; if the book is hyphenated,
                        a CSS with "hyphens: manual" only is linked instead (only with -e)
  --skip-justify        skip replacing "text-align: left" with "text-align: justify" in all CSS files (only with -e)
  --left                replace "text-align: justify" with "text-align: left" in all CSS files (experimental) (only with -e)
  --remove-colors       remove all color definitions from CSS files (only with -e)
  --remove-fonts        remove all embedded font files (only with -e)
  -k, --kindlegen       convert _moh.epub files to .mobi with kindlegen
  -d, --huffdic         tell kindlegen to use huffdic compression (slow conversion) (only with -k)
  -f, --force           overwrite previously generated _moh.epub or .mobi files (only with -k or -e)
  --fix-missing-container
                        Fix missing META-INF/container.xml file and incorrect mimetype file (not first, compressed or wrong content) in original EPUB file (only with -e)
  --book-margin [NUMBER]
                        Add left and right book margin to reset CSS file (only with -e, not with -c)
```

Najważniejsze opcje po polsku:

| Opcja | Co robi |
|---|---|
| `-e` | poprawia książki i dzieli wyrazy; wyniki `*_moh.epub` w podkatalogu `MOH` (z tymi samymi podkatalogami co oryginały) |
| `-q` | sprawdza książki wewnętrznym narzędziem (`-m`: tylko poprawione) |
| `-p` | sprawdza książki programem EpubCheck (`-m`: tylko poprawione) |
| `-i [NR]` | wybór książek: bez numeru w terminalu, z numerem np. `3` albo `1,3,5-7` |
| `-n` | zmienia nazwy oryginałów na „autor - tytuł.epub” |
| `-t` | kopiuje poprawione książki do `TS2K` jako „tytuł.epub” (do Send to Kindle) |
| `-k` | zamienia poprawione książki na MOBI programem kindlegen |
| `-v` | wypisuje wszystkie komunikaty (domyślnie tylko problemy) |
| `-l [KATALOG]` | zapisuje dziennik ze wszystkimi komunikatami |
| `-f` | poprawia (`-e`) albo zamienia (`-k`) ponownie, nadpisując poprzednie wyniki |
| `-s`, `-r`, `-c`, `--skip-justify`, `--left`, `--remove-colors`, `--remove-fonts`, `--book-margin`, `--skip-page-list` | ustawienia poprawiania – jak w tabeli ustawień wtyczki wyżej |

`-m`, `-k` i `-t` biorą tylko pliki _moh.epub z podkatalogu `MOH`. Stare wyniki
wcześniejszych wersji (obok oryginałów albo, dla książek z podkatalogów,
bezpośrednio w `MOH`) są pomijane i wymienione w ostrzeżeniu.

### Komunikaty
Domyślnie (bez `-v`) podczas pracy wypisywane są tylko problemy: ostrzeżenia,
błędy oraz komunikaty EpubCheck i kindlegen, dla każdej książki po linii
`--- ścieżka/do/książki.epub`. Książki bez problemów nic nie wypisują; na koniec
każdego etapu wypisywane jest podsumowanie (np. lista książek zakończonych
z problemami). W terminalu książka, nad którą program pracuje, jest pokazywana
w linii postępu. `-v` wypisuje wszystkie komunikaty opisane niżej; dziennik (`-l`)
zawsze dostaje wszystkie.

* `* tekst` – informacja
* `! WARNING! tekst` – ostrzeżenie, książka jest przetwarzana dalej
* `! ERROR! tekst` – błąd, książka jest przetwarzana, ale z problemami
* `! CRITICAL! tekst` – książki (albo całego uruchomienia) nie da się przetworzyć
* `START ... for:`, `FINISH ... for:`, `FINISH (with PROBLEMS) ... for:` – początek
  i koniec każdego etapu

Wewnętrzne sprawdzanie (`-q`) wypisuje jedno znalezisko w linii (zaczynające się
od `* `, a z `-a` od nazwy pliku), oznaczone `CRITICAL!`, `ERROR!` albo
`WARNING!`, gdy to potrzebne.

### Sprawdzanie CSS (-q)
Pliki CSS są czytane biblioteką tinycss2 (CSS Syntax Level 3) i sprawdzane pod
kątem problemów ważnych w czytnikach (a nie zgodności z CSS 2.1 – przedrostki
przeglądarek i nowe właściwości są w porządku):
* `CSS ERROR!` – czytnik pominie deklarację albo regułę: błędy składni,
  deklaracja bez `:`, nieoczekiwany `}`, nieznane nazwy właściwości (literówki;
  lista znanych właściwości z MDN w `lib/resources/css_properties.txt`), twarda
  albo inna nietypowa spacja w wartości (poza cudzysłowem), brak średnika, więcej
  niż 4 wartości w `margin`/`padding`
* `CSS WARNING!` (wyłącza `-u`) – może sprawiać kłopoty w niektórych czytnikach:
  `!important` przy `font-size`, `font-family`, `line-height`, `color` albo
  `background-color`, `position: fixed/absolute`, `display: flex/grid`, jednostki
  `vh/vw/vmin/vmax`, kolor dla `body`/`html`, `@import`

## Dla programistów

### Wymagania
```
python -m pip install lxml css-parser tinycss2
python -m pip install pyinstaller    # tylko do samodzielnych programów
```

### Testy
Uruchamiane z głównego katalogu:
```
python -m unittest
```

### Budowanie wtyczki do calibre
```
python build_calibre_plugin.py [PLIK.zip]
```
Wtyczka to plik zip z `calibre_plugin/`, `lib/` i biblioteką tinycss2 (calibre
jej nie ma), wziętą z Pythona, którym uruchamiasz skrypt. Domyślnie powstaje
`epubQTools-calibre.zip` w głównym katalogu (git go pomija). Zainstaluj ją jak
wyżej albo poleceniem `calibre-customize -a epubQTools-calibre.zip` (w macOS jest
ono w `/Applications/calibre.app/Contents/MacOS/`; potem dodaj przycisk do paska
narzędzi w ustawieniach).

### Samodzielne programy (PyInstaller)
* na Macu:
```
pyinstaller -Fn epubQTools ~/github/epubQTools/__main__.py
```
* w Windows:
```
C:\Python37\Scripts\pyinstaller.exe -Fn epubQTools .\epubQTools\__main__.py
```
