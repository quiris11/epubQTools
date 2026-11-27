epubQTools [![Release](https://img.shields.io/github/release/quiris11/epubqtools.svg)](https://github.com/quiris11/epubqtools/releases/latest)
==========

Tools for checking, fixing and hyphenating EPUB books, especially for Kindle
readers (Send to Kindle). epubQTools fixes the problems which spoil reading
(broken CSS, covers, links, notes, obfuscated fonts...), hyphenates Polish books,
adds an approximate page list and removes texts and pages added by some shops.

There are two ways to use it:
* **calibre plugin** - the easiest way, no terminal needed: select books in
  calibre and click a button. It fixes books (like `-e` below).
* **command line** - all functions: fixing, checking (also with EpubCheck),
  renaming files, preparing files for Send to Kindle, converting with kindlegen.

The original files are not changed: fixed books are new files (or, in calibre,
a new version of the book with the original kept). Only `-n`, `--author`,
`--title` and `--fix-missing-container` change the original files.

## calibre plugin

### Installing
Requires calibre 6.0 or newer (https://calibre-ebook.com).
1. Download **epubQTools-calibre-VERSION.zip** from the
   [latest release](https://github.com/quiris11/epubQTools/releases/latest)
   (in "Assets"). Do not unpack it.
2. In calibre choose **Preferences → Plugins → Load plugin from file** and select
   the downloaded file. Confirm the warning about installing a plugin.
3. calibre asks where to show the plugin's button: select **The main toolbar**.
4. Restart calibre. The **epubQTools** button is on the toolbar.

If the button is not there, add it in **Preferences → Toolbars & menus → The main
toolbar** (choose "epubQTools" in the list of available actions).

To update the plugin, install the new file the same way (the settings are kept).
To remove it: **Preferences → Plugins**, select "epubQTools", **Remove plugin**.

### Using
Select one or more books and click the **epubQTools** button (or the arrow next to
it for the menu):
* **Popraw zaznaczone książki** (fix the selected books) - the same as the button.
  The fixed book replaces the EPUB format and the original is kept as the
  **ORIGINAL_EPUB** format. The original is kept only the first time, so fixing
  a book again starts from the original, not from the fixed version.
* **Przywróć oryginał** (restore the original) - the EPUB format becomes the
  original again and ORIGINAL_EPUB is removed.
* **Ustawienia…** (settings) - see below.

The books are fixed in the background (shown in calibre's Jobs), so calibre can
be used meanwhile. At the end a window shows how many books were fixed and lists
the books saved with problems (with a warning), the books which could not be fixed
(e.g. with DRM; they are not changed) and the books without the EPUB format.
**Show details** shows all messages for every book.

### Settings
The defaults give the same result as `-e` on the command line:

| Setting | Default | Command line option |
|---|---|---|
| Dziel wyrazy (hyphenate; Polish books only) | on | `-s` turns it off |
| Dziel też wyrazy w nagłówkach (hyphenate headers) | on | `-r` turns it off |
| Dołącz reset CSS (link the reset CSS) | on | `-c` turns it off |
| Wyrównanie tekstu (alignment): justify / left / no change | justify | – / `--left` / `--skip-justify` |
| Usuń kolory (remove colors; not with "no change") | off | `--remove-colors` |
| Margines lewy i prawy (left and right margin) | off | `--book-margin` |
| Usuń wbudowane fonty (remove embedded fonts) | off | `--remove-fonts` |
| Dodaj przybliżoną listę stron (approximate page list) | on | `--skip-page-list` turns it off |

## Command line

### Installing
1. Install Python 3 (https://www.python.org; on Linux it is usually installed).
2. Download "Source code (zip)" from the
   [latest release](https://github.com/quiris11/epubQTools/releases/latest)
   and unpack it, e.g. to the folder `epubQTools-1.0`.
3. Install the libraries (on Windows use `py` instead of `python3` here and below):
   ```
   python3 -m pip install lxml css-parser tinycss2
   ```
4. Optional external tools:
   * **EpubCheck** (for `-p`, needs Java): download the zip file from
     https://github.com/w3c/epubcheck/releases (do not unpack it)
   * **kindlegen** (for `-k`, only the unpacked program file is needed)
   * **pytidylib** with the system libtidy (`python3 -m pip install pytidylib`):
     additional HTML checks in `-q`

   Put EpubCheck and kindlegen into the tools folder (or point to another folder
   with `--tools DIR`):
   * Linux/macOS: `~/.local/share/epubQTools/` (`$XDG_DATA_HOME/epubQTools/` if set)
   * Windows: `%LOCALAPPDATA%\epubQTools\`

   If this folder does not exist, the folder next to the program is used (as in
   older versions). kindlegen is also looked up in `PATH`.

### Quick start
The last argument is the folder with the books (subfolders are included):
```
python3 epubQTools-1.0 -e ~/Books        # fix all books, results in ~/Books/MOH/*_moh.epub
python3 epubQTools-1.0 -q ~/Books        # check the books
python3 epubQTools-1.0 -q -m ~/Books     # check the fixed books (_moh.epub)
python3 epubQTools-1.0 -i -e ~/Books     # choose the books to fix in the console
python3 epubQTools-1.0 -n -e -t ~/Books  # rename the originals to "Author - Title.epub", fix them
                                         # and copy to ~/Books/TS2K as "Title.epub" for Send to Kindle
```
A book already fixed is skipped; `-f` fixes it again.

### All options
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
                        Add left and right book margin to reset CSS file (only with -e)
```

`-m`, `-k` and `-t` use only the _moh.epub files in the 'MOH' subfolder. Old results of earlier
versions (next to the originals, or directly in 'MOH' for books from subfolders) are skipped and
listed in a warning.

### Page list (-e):
Books without a page list (no NCX `pageList`, no nav `page-list`, no `pagebreak` markers) get
a list of approximate pages: empty `<span id="eqt_page_N"></span>` markers in the text, a
`pageList` in the NCX and, in EPUB 3, a hidden `<nav epub:type="page-list">`. Every spine file
starts a new page; a block (paragraph, heading, list item...) takes ceil(chars / 68) lines and a
page has 29 lines (calibrated on Polish books with print page numbers, average error ~15% per
book, systematic error under 4%).
Send to Kindle keeps such a list, so the "Pages" option works also for books for which Amazon
does not generate pages itself (e.g. books with tables). Turn it off with `--skip-page-list`.

### Pop-up notes (-e):
Note asides (linked with `epub:type="noteref"` or `role="doc-noteref"` links, or with
`epub:type` `footnote`, `endnote`, `rearnote` or `note`) are fixed for pop-ups of Send to Kindle.
If a note starts with its number and ends with a back link (e.g. "↩"), the number becomes the
back link: Kindle Paperwhite 1 and Voyage (AZW3) show also the next note in the pop-up if the back
link is at the end of a note.
A note which starts with its back link stays an `<aside>` and gets the `eqt_note` class. If the
CSS rules of asides (or of the classes of the notes) set borders or page breaks, a rule
`aside.eqt_note` turns them off with `!important` (Send to Kindle does not show notes with a
border in pop-ups, and a page break in note styles turns off pop-ups in the whole book in KFX);
the rules of the book are not changed, as they apply also to other asides. Such declarations are
also removed from the `style` attributes of the notes.
Other notes (without a back link at the start) are replaced with list items of an
`<ol class="eqt_notes">` list (consecutive notes in one list): Send to Kindle only jumps to such
asides, but shows such list items in pop-ups. An aside with a single `<p>` becomes a list item
with the contents of the paragraph. The list items keep the CSS styles of the asides, without
borders and page breaks.
Notes without note markup (e.g. in EPUB 2 books) in list items which end with a back link (e.g.
"[back]") get the back link at their start, on the number of the note: Send to Kindle only jumps
to such notes if the back link is at their end. This is done only for `<ol>` lists in which every
item is the target of a link with only a number (in the same file) and ends with a back link to that
link; the numbering of the list is turned off, as the numbers are now in the notes.
Soft hyphens are removed from all notes linked with noteref links and from the notes above: Kindle
Paperwhite 1 does not show the hyphen at a line break in pop-ups.
If the back link at the start of such a note (or an element around it, e.g. the `<span>` of the
number) has `display: inline-block` (in a CSS rule of its tag and classes or in its `style`
attribute), it gets the `eqt_note_number` class and a rule `.eqt_note_number` sets
`display: inline !important`: Send to Kindle (KFX) does not show such notes in pop-ups. The rules
of the book are not changed; the declaration is removed from the `style` attribute.

### Output messages:
By default (without `-v`) only problems are printed while the books are processed: warnings, errors
and messages of EpubCheck and kindlegen, each book's problems after a line `--- path/to/book.epub`.
Books without problems print nothing; at the end of each step a summary is printed (e.g. the list of
books finished with problems). In a terminal the book being processed is shown in a progress line.
`-v` prints all messages below; the log file (`-l`) always gets all of them.

* `* text` - information
* `! WARNING! text` - warning, the book is processed
* `! ERROR! text` - error, the book is processed with problems
* `! CRITICAL! text` - the book (or the whole run) cannot be processed
* `START ... for:`, `FINISH ... for:`, `FINISH (with PROBLEMS) ... for:` - start and end of each stage

The internal check (`-q`) prints one finding per line (`* ` or `file: ` with `-a`), marked
`CRITICAL!`, `ERROR!` or `WARNING!` where it applies.

### CSS check (-q):
CSS files are parsed with tinycss2 (CSS Syntax Level 3) and checked for problems that matter
in e-book readers (not for CSS 2.1 validity - vendor prefixes and modern properties are fine):
* `CSS ERROR!` - a reader drops the declaration or rule: syntax errors, a declaration without
  `:`, an unexpected `}`, unknown property names (typos; list of known properties from MDN in
  `lib/resources/css_properties.txt`), a non-breaking or other unusual space in a value (outside
  quotes), a missing semicolon, more than 4 values in `margin`/`padding`
* `CSS WARNING!` (silenced with `-u`) - may cause problems in some readers: `!important` on `font-size`,
  `font-family`, `line-height`, `color` or `background-color`, `position: fixed/absolute`,
  `display: flex/grid`, `vh/vw/vmin/vmax` units, a color on `body`/`html`, `@import`

## For developers

### Requirements
```
python -m pip install lxml css-parser tinycss2
python -m pip install pyinstaller    # for standalone applications only
```

### Tests
Run from the main folder:
```
python -m unittest
```

### Building the calibre plugin
```
python build_calibre_plugin.py [OUTPUT.zip]
```
The plugin is a zip file with `calibre_plugin/`, `lib/` and tinycss2 (calibre
lacks it), taken from the Python which runs the script. The default output is
`epubQTools-calibre.zip` in the main folder (ignored by git). Install it as above
or with `calibre-customize -a epubQTools-calibre.zip` (on macOS it is in
`/Applications/calibre.app/Contents/MacOS/`; then add the button to the toolbar
in the preferences).

### Standalone applications (PyInstaller)
* on Mac:
```
pyinstaller -Fn epubQTools ~/github/epubQTools/__main__.py
```
* on Windows:
```
C:\Python37\Scripts\pyinstaller.exe -Fn epubQTools .\epubQTools\__main__.py
```
