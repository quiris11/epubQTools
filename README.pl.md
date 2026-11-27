epubQTools [![Release](https://img.shields.io/github/release/quiris11/epubqtools.svg)](https://github.com/quiris11/epubqtools/releases/latest)
==========

<p align="center">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/English-lightgrey?style=for-the-badge"></a>
  <a href="README.pl.md"><img alt="Polski" src="https://img.shields.io/badge/Polski-0969da?style=for-the-badge"></a>
</p>

epubQTools poprawia książki EPUB tak, żeby dobrze się je czytało, przede
wszystkim na czytnikach Kindle (Send to Kindle).

## Co robi
* poprawia błędy, które psują czytanie: zepsute style, okładki, linki, puste
  tytuły, spis treści
* sprawia, że przypisy otwierają się na Kindle w okienku
* dzieli wyrazy w języku książki (zob. niżej)
* dodaje przybliżone numery stron do książek, które ich nie mają
* usuwa teksty i strony dodawane przez niektóre księgarnie (ukryte napisy,
  strony o zbiórkach i wsparciu)
* sprawia, że czytnik może odczytać wbudowane fonty (odszyfrowuje zaciemnione
  fonty)

Oryginalna książka nie jest zmieniana: poprawiona książka to nowy plik (w calibre
nowa wersja książki, a oryginał zostaje zachowany).

Można z niego korzystać na dwa sposoby:
* **wtyczka do calibre** – najprościej: zaznaczasz książki w calibre i klikasz
  przycisk.
* **wiersz poleceń (terminal)** – to samo poprawianie, a do tego sprawdzanie
  książek, zmiana nazw plików i przygotowanie ich do Send to Kindle.

## Dzielenie wyrazów
Wyrazy są dzielone według zasad języka książki. Można to wyłączyć: we wtyczce
ustawieniem „Dziel wyrazy”, w terminalu opcją `-s`.

Słownik polski jest częścią epubQTools. Inne języki korzystają ze słowników
calibre: wtyczka ma je zawsze, a terminal używa ich wtedy, gdy calibre jest
zainstalowany na komputerze. calibre nie ma słownika francuskiego, więc książki
francuskie nie są dzielone. Książka bez języka jest traktowana jak polska.

## Wtyczka do calibre

### Instalacja
Potrzebny jest calibre 6.17 lub nowszy (https://calibre-ebook.com).
1. Pobierz plik **epubQTools-calibre-WERSJA.zip** z
   [najnowszego wydania](https://github.com/quiris11/epubQTools/releases/latest)
   (w części „Assets”). Nie rozpakowuj go.
2. W calibre wybierz **Ustawienia → Wtyczki → Wczytaj wtyczkę z pliku**, wskaż
   pobrany plik i potwierdź ostrzeżenie.
3. Gdy calibre zapyta, gdzie pokazać przycisk, zaznacz **Główny pasek narzędzi**.
4. Uruchom calibre ponownie. Przycisk **epubQTools** jest na pasku narzędzi.

Nie ma przycisku? Dodaj go w **Ustawienia → Paski narzędzi i menu → Główny pasek
narzędzi**.
Aktualizacja: zainstaluj nowy plik tak samo (ustawienia zostają).
Usunięcie: **Ustawienia → Wtyczki**, zaznacz „epubQTools”, **Usuń wtyczkę**.

### Używanie
Zaznacz książki i kliknij **epubQTools**. Strzałka obok przycisku otwiera menu:
* **Popraw zaznaczone książki** – to samo co przycisk. Poprawiona książka staje
  się formatem EPUB, a oryginał zostaje w **plikach danych** książki (plik
  „epubQTools original.epub”). Ponowne poprawianie zawsze zaczyna się od
  oryginału. Konwersja książki w calibre (np. do MOBI) zaczyna się od
  poprawionego EPUB.
* **Przywróć oryginał** – przywraca oryginalny EPUB. W calibre starszym niż 8
  kopia oryginału zostaje w plikach danych.
* **Ustawienia…** – co zmieniać w książkach (niżej).

W czasie poprawiania można dalej korzystać z calibre. Na koniec okienko pokazuje
wynik; **Pokaż szczegóły** pokazuje wszystkie komunikaty. Książek z DRM nie da się
poprawić – zostają bez zmian.

Wtyczka mówi językiem calibre (po polsku albo po angielsku).

### Nowe wersje
Kilka sekund po uruchomieniu calibre wtyczka pyta GitHuba, czy wyszła nowsza
wersja epubQTools z wtyczką do calibre (najwyżej raz dziennie). Jeśli tak,
okienko raz pyta, czy otworzyć stronę pobierania, a w menu przycisku jest
**Nowa wersja … – pobierz…**, dopóki jej nie zainstalujesz. Żeby zaktualizować,
pobierz zip i wczytaj go tak jak przy pierwszej instalacji. Do GitHuba idzie
tylko to pytanie (GitHub widzi więc Twój adres internetowy, jak przy każdym
wejściu na jego strony), nic o Twoich książkach. Bez internetu nic się nie
pokazuje, a przy następnym uruchomieniu calibre wtyczka spróbuje znowu. Można to
wyłączyć w ustawieniach.

### Ustawienia
| Ustawienie | Domyślnie | Co robi |
|---|---|---|
| Dziel wyrazy | tak | Dzieli wyrazy w języku książki. Wyłączone: epubQTools nie dzieli wyrazów. |
| Dziel też wyrazy w nagłówkach (h1, h2, h3…) | nie | Dzieli także tytuły rozdziałów. Zwykle wyglądają lepiej bez tego. |
| Dołącz reset CSS | nie | Dodaje do każdej strony książki mały plik stylów: te same małe marginesy (5 pt) wokół tekstu, akapity bez lewego i prawego marginesu i w zwykłej wielkości, jeden font w całym tekście. Przydaje się, gdy książka wygląda inaczej w każdym czytniku. Bez tego książka zachowuje swój wygląd. |
| Wyrównanie tekstu | Wyjustuj tekst wyrównany do lewej | *Wyjustuj tekst wyrównany do lewej*: tekst dostaje równy prawy brzeg. *Wyrównaj do lewej tekst wyjustowany*: odwrotnie, prawy brzeg jest nierówny. *Bez zmian*: wyrównanie zostaje takie jak w książce. |
| Usuń kolory | nie | Usuwa kolory tekstu i tła, żeby książka wyglądała tak samo na czytnikach czarno-białych i w trybie nocnym. Działa tylko wtedy, gdy wyrównanie nie jest „Bez zmian”. |
| Margines lewy i prawy | nie | Dodaje z lewej i prawej strony margines podanej szerokości (w pikselach). Działa tylko z „Dołącz reset CSS”. |
| Usuń wbudowane fonty | nie | Usuwa fonty książki; czytnik używa własnego fontu. |
| Dodaj przybliżoną listę stron (w książkach bez niej) | tak | Dodaje numery stron (jedna strona = mniej więcej tyle samo tekstu), więc czytnik może pokazywać numery stron. Książki z własną listą stron nie są zmieniane. |
| Sprawdzaj nową wersję wtyczki na GitHubie (raz dziennie) | tak | Zob. [Nowe wersje](#nowe-wersje). Wyłączone: wtyczka nie łączy się z internetem. |

**Przywróć domyślne** w okienku ustawień przywraca wartości z tabeli, oprócz
sprawdzania nowych wersji.

## Wiersz poleceń (terminal)

### Instalacja
1. Zainstaluj Pythona 3 (https://www.python.org).
2. Pobierz „Source code (zip)” z
   [najnowszego wydania](https://github.com/quiris11/epubQTools/releases/latest)
   i rozpakuj go, np. do katalogu `epubQTools-1.0`.
3. Zainstaluj potrzebne biblioteki (w Windows zamiast `python3` wpisuj `py`, tu
   i niżej):
   ```
   python3 -m pip install lxml css-parser tinycss2
   ```

### Używanie
Na końcu polecenia podajesz katalog z książkami (razem z podkatalogami):
```
python3 epubQTools-1.0 -e ~/Książki      # popraw wszystkie książki; poprawione trafią do ~/Książki/MOH
python3 epubQTools-1.0 -i -e ~/Książki   # wybierz z listy, które książki poprawić
python3 epubQTools-1.0 -q ~/Książki      # sprawdź książki i wypisz ich problemy
```
Książki już poprawione są pomijane (`-f` poprawia je ponownie).

Opcje można łączyć, np. `-n -e -t` zmienia nazwy oryginałów, poprawia je
i przygotowuje do Send to Kindle. `-h` pokazuje krótko wszystkie opcje
(po angielsku).

#### Co zrobić
| Opcja | Co robi |
|---|---|
| `-e` | Poprawia książki i dzieli wyrazy. Poprawiona kopia `Nazwa_moh.epub` trafia do katalogu `MOH` w katalogu z książkami (książki z podkatalogów dostają te same podkatalogi w `MOH`). Oryginał się nie zmienia. |
| `-q` | Sprawdza książki i wypisuje ich problemy: błędy w plikach i stylach, problemy z okładką, brak autora, tytułu albo języka, fonty, których czytnik nie odczyta… Niczego nie zmienia. |
| `-p` | Sprawdza książki programem EpubCheck, oficjalnym programem do sprawdzania EPUB (zob. [Dodatkowe narzędzia](#dodatkowe-narzędzia-nieobowiązkowe)). Niczego nie zmienia. |
| `-k` | Zamienia poprawione książki na pliki MOBI dla starszych Kindle, programem kindlegen (zob. [Dodatkowe narzędzia](#dodatkowe-narzędzia-nieobowiązkowe)). Plik MOBI trafia obok poprawionej książki. |
| `-n` | Zmienia nazwy **oryginalnych** plików na „Autor - Tytuł.epub”, według autora i tytułu zapisanych w książce. Jeśli taki plik już jest, dodaje „ (1)”. |
| `-t` | Kopiuje poprawione książki do katalogu `TS2K` jako „Tytuł.epub” (bez autora i bez `_moh`), gotowe do wysłania przez Send to Kindle. Potrzebuje nazw „Autor - Tytuł”, więc używaj go z `-n`. Katalog jest najpierw opróżniany (z `-i` podmieniane są tylko wybrane książki). |
| `--author "Nazwisko, Imię"` | Zmienia autora zapisanego w **oryginalnej** książce. Tylko z `-i` i dla jednej książki. |
| `--title "Tytuł"` | Zmienia tytuł zapisany w **oryginalnej** książce. Tylko z `-i` i dla jednej książki. |

#### Które książki
| Opcja | Co robi |
|---|---|
| `-i` | Pokazuje listę książek do wyboru. Z numerami bierze książki o tych numerach z listy: `-i 3`, `-i 1,3,5-7`. |
| `-m` | Z `-q` albo `-p`: sprawdza poprawione książki (`_moh.epub`) zamiast oryginałów. |
| `-f` | Poprawia (`-e`) albo zamienia (`-k`) ponownie książki zrobione wcześniej, zastępując poprzednie wyniki. |

#### Jak poprawiać (z `-e`)
W terminalu reset CSS i dzielenie nagłówków są włączone; `-c -r` daje ten sam
wynik co wtyczka z ustawieniami domyślnymi. Dokładniejszy opis każdej opcji jest
w [ustawieniach wtyczki](#ustawienia).

| Opcja | Co robi |
|---|---|
| `-s` | Nie dzieli wyrazów. |
| `-r` | Nie dzieli wyrazów w nagłówkach (h1, h2, h3…). |
| `-c` | Nie dodaje resetu CSS (książka zachowuje swój wygląd). |
| `--skip-justify` | Zostawia wyrównanie tekstu takie jak w książce (zwykle tekst wyrównany do lewej jest justowany). |
| `--left` | Wyrównuje do lewej tekst wyjustowany (wersja próbna). |
| `--remove-colors` | Usuwa kolory tekstu i tła. Nie działa z `--skip-justify`. |
| `--remove-fonts` | Usuwa fonty książki; czytnik używa własnego fontu. |
| `--book-margin LICZBA` | Dodaje lewy i prawy margines szerokości LICZBA pikseli. Nie działa z `-c`. |
| `--skip-page-list` | Nie dodaje przybliżonych numerów stron. |
| `--fix-missing-container` | Naprawia książkę, która się nie otwiera, bo brakuje pliku wskazującego, gdzie jest treść (`container.xml`), albo zły jest wpis o rodzaju pliku (`mimetype`). Zmienia **oryginalny** plik. |

#### Co zgłaszać (z `-q`)
| Opcja | Co robi |
|---|---|
| `-u` | Zgłasza tylko błędy stylów, bez ostrzeżeń (rzeczy, które sprawiają kłopot tylko w niektórych czytnikach). |
| `-w` | Nie zgłasza fontów zapisanych z nietypowym rodzajem pliku. |
| `--list-fonts` | Wypisuje wszystkie fonty każdej książki. |
| `-a` | Wypisuje każdy problem w jednej linii zaczynającej się od nazwy pliku (łatwo sortować i przeszukiwać). |

#### Komunikaty i narzędzia
| Opcja | Co robi |
|---|---|
| `-v` | Pokazuje wszystkie komunikaty, także o każdej zmianie. Zwykle pokazywane są tylko problemy. |
| `-l [KATALOG]` | Zapisuje wszystkie komunikaty do pliku `eQT-DATA.log`, w podanym katalogu albo w katalogu z książkami. |
| `--tools KATALOG` | Gdzie szukać EpubCheck i kindlegen (zob. niżej). |
| `-d` | Z `-k`: mniejsze pliki MOBI, ale wolniejsza zamiana. |
| `-V` | Pokazuje wersję epubQTools. |
| `-h` | Pokazuje krótko wszystkie opcje (po angielsku). |

### Dodatkowe narzędzia (nieobowiązkowe)
* **EpubCheck** (`-p`) – oficjalny program do sprawdzania EPUB, wymaga Javy.
  Jego plik zip (nierozpakowany) umieść w katalogu narzędzi.
* **kindlegen** (`-k`) – zamienia poprawione książki na MOBI dla starszych
  Kindle. Sam program umieść w katalogu narzędzi (jest też znajdowany, gdy jest
  zainstalowany w systemie).

Katalog narzędzi to `~/.local/share/epubQTools/` w Linuksie i macOS oraz
`%LOCALAPPDATA%\epubQTools\` w Windows (inny: `--tools KATALOG`).
