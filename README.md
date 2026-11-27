epubQTools [![Release](https://img.shields.io/github/release/quiris11/epubqtools.svg)](https://github.com/quiris11/epubqtools/releases/latest)
==========

<p align="center">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/English-0969da?style=for-the-badge"></a>
  <a href="README.pl.md"><img alt="Polski" src="https://img.shields.io/badge/Polski-lightgrey?style=for-the-badge"></a>
</p>

epubQTools fixes EPUB e-books so that they read well, especially on Kindle
readers (Send to Kindle).

## What it does
* fixes errors which spoil reading: broken styles, covers, links, empty titles,
  the table of contents
* makes notes open in a pop-up window on Kindle
* hyphenates words in the language of the book (see below)
* adds approximate page numbers to books which have none
* removes texts and pages added by some shops (hidden texts, fundraising and
  support pages)
* makes embedded fonts readable for readers (decrypts obfuscated fonts)

The original book is not changed: the fixed book is a new file (in calibre a new
version of the book, with the original kept).

You can use it in two ways:
* **calibre plugin** - the easiest: select books in calibre and click a button.
* **command line (terminal)** - the same fixing, plus checking books, renaming
  files and preparing them for Send to Kindle.

## Hyphenation
Words are hyphenated by the rules of the book's language. You can turn it off:
the "Hyphenate words" setting in the plugin, `-s` in the terminal.

The Polish dictionary is part of epubQTools. Other languages use the dictionaries
of calibre: the plugin always has them, the terminal uses them when calibre is
installed on the computer. calibre has no French dictionary, so French books are
not hyphenated. A book without a language is treated as Polish.

## calibre plugin

### Installing
Requires calibre 6.17 or newer (https://calibre-ebook.com).
1. Download **epubQTools-calibre-VERSION.zip** from the
   [latest release](https://github.com/quiris11/epubQTools/releases/latest)
   (under "Assets"). Do not unpack it.
2. In calibre choose **Preferences → Plugins → Load plugin from file**, select the
   downloaded file and confirm the warning.
3. When calibre asks where to show the button, select **The main toolbar**.
4. Restart calibre. The **epubQTools** button is on the toolbar.

No button? Add it in **Preferences → Toolbars & menus → The main toolbar**.
To update the plugin, install the new file the same way (the settings are kept).
To remove it: **Preferences → Plugins**, select "epubQTools", **Remove plugin**.

### Using
Select books and click **epubQTools**. The arrow next to the button opens a menu:
* **Fix the selected books** - the same as the button. The fixed book becomes the
  EPUB format, the original is kept in the **Data files** of the book (file
  "epubQTools original.epub"). Fixing a book again always starts from the
  original. Converting the book in calibre (e.g. to MOBI) starts from the fixed
  EPUB.
* **Restore the original** - brings the original EPUB back. In calibre older
  than 8 the copy of the original stays in the data files.
* **Settings…** - what to change in the books (below).

You can keep using calibre while the books are being fixed. At the end a window
shows the result; **Show details** shows all messages. Books with DRM cannot be
fixed and stay unchanged.

The plugin speaks the language of calibre (Polish or English).

### Settings
| Setting | Default | What it does |
|---|---|---|
| Hyphenate words | on | Hyphenates words in the language of the book. Off: words are not hyphenated by epubQTools. |
| Hyphenate also words in headings (h1, h2, h3…) | off | Hyphenates also the chapter titles. Usually they look better without it. |
| Add a CSS reset | off | Adds a small style file to every page of the book: the same small margins (5 pt) around the text, paragraphs without left and right margins and in the normal font size, one font for the whole text. Use it when the book looks different in every reader. Without it the book keeps its own look. |
| Text alignment | Justify text aligned to the left | *Justify text aligned to the left*: the text gets even right edges. *Align justified text to the left*: the other way round, the right edge is uneven. *No change*: the alignment stays as in the book. |
| Remove colors | off | Removes the colors of the text and the background, so the book looks the same on black-and-white readers and in the night mode. Works only when the alignment is not “No change”. |
| Left and right margin | off | Adds a margin of the given width (in pixels) on the left and right side. Works only with “Add a CSS reset”. |
| Remove embedded fonts | off | Removes the fonts of the book; the reader uses its own font. |
| Add an approximate page list (in books without one) | on | Adds page numbers (one page = about the same amount of text), so the reader can show page numbers. Books with their own page list are not changed. |

**Restore defaults** in the settings window brings back the values above.

## Command line

### Installing
1. Install Python 3 (https://www.python.org).
2. Download "Source code (zip)" from the
   [latest release](https://github.com/quiris11/epubQTools/releases/latest)
   and unpack it, e.g. to the folder `epubQTools-1.0`.
3. Install the libraries it needs (on Windows type `py` instead of `python3`,
   here and below):
   ```
   python3 -m pip install lxml css-parser tinycss2
   ```

### Using
The last part of the command is the folder with the books (subfolders are
included):
```
python3 epubQTools-1.0 -e ~/Books      # fix all books; the fixed books go to ~/Books/MOH
python3 epubQTools-1.0 -i -e ~/Books   # choose from a list which books to fix
python3 epubQTools-1.0 -q ~/Books      # check the books and list their problems
```
Books already fixed are skipped (`-f` fixes them again).

Options can be joined, e.g. `-n -e -t` renames the originals, fixes them and
prepares them for Send to Kindle. `-h` lists all options in short.

#### What to do
| Option | What it does |
|---|---|
| `-e` | Fixes the books and hyphenates words. The fixed copy `Name_moh.epub` is saved in the `MOH` folder inside the folder with the books (books from subfolders get the same subfolders in `MOH`). The original is not changed. |
| `-q` | Checks the books and lists their problems: errors in the files and styles, problems with the cover, a missing author, title or language, fonts which readers cannot open… Nothing is changed. |
| `-p` | Checks the books with EpubCheck, the official EPUB checker (see [Extra tools](#extra-tools-optional)). Nothing is changed. |
| `-k` | Converts the fixed books to MOBI files for old Kindles, with kindlegen (see [Extra tools](#extra-tools-optional)). The MOBI file is saved next to the fixed book. |
| `-n` | Renames the **original** files to "Author - Title.epub", with the author and the title written in the book. If such a file already exists, " (1)" is added. |
| `-t` | Copies the fixed books to the `TS2K` folder as "Title.epub" (without the author and without `_moh`), ready to send with Send to Kindle. Needs file names "Author - Title", so use it with `-n`. The folder is emptied first (with `-i` only the selected books are replaced). |
| `--author "Surname, First Name"` | Changes the author written in the **original** book. Only with `-i` and one book. |
| `--title "Title"` | Changes the title written in the **original** book. Only with `-i` and one book. |

#### Which books
| Option | What it does |
|---|---|
| `-i` | Shows the list of books to choose from. With numbers it takes the books with these numbers from the list: `-i 3`, `-i 1,3,5-7`. |
| `-m` | With `-q` or `-p`: checks the fixed books (`_moh.epub`) instead of the originals. |
| `-f` | Fixes (`-e`) or converts (`-k`) again the books done before, replacing the earlier results. |

#### How to fix (with `-e`)
In the terminal the CSS reset and the hyphenation of headings are on; `-c -r`
gives the same result as the plugin with its default settings. Each option is
explained in more detail in the [plugin settings](#settings).

| Option | What it does |
|---|---|
| `-s` | Does not hyphenate words. |
| `-r` | Does not hyphenate words in headings (h1, h2, h3…). |
| `-c` | Does not add the CSS reset (the book keeps its own look). |
| `--skip-justify` | Leaves the text alignment as in the book (normally text aligned to the left gets justified). |
| `--left` | Aligns justified text to the left (test version). |
| `--remove-colors` | Removes the colors of the text and the background. Not with `--skip-justify`. |
| `--remove-fonts` | Removes the fonts of the book; the reader uses its own font. |
| `--book-margin NUMBER` | Adds a left and right margin of NUMBER pixels. Not with `-c`. |
| `--skip-page-list` | Does not add approximate page numbers. |
| `--fix-missing-container` | Repairs a book which does not open because the file telling where the content is (`container.xml`) is missing or the file type entry (`mimetype`) is wrong. Changes the **original** file. |

#### What to report (with `-q`)
| Option | What it does |
|---|---|
| `-u` | Reports only style errors, without warnings (things which cause problems only in some readers). |
| `-w` | Does not report fonts saved with an unusual file type. |
| `--list-fonts` | Lists all fonts of every book. |
| `-a` | Prints every problem in one line beginning with the file name (easy to sort or search). |

#### Messages and tools
| Option | What it does |
|---|---|
| `-v` | Shows all messages, also about every change. Normally only problems are shown. |
| `-l [FOLDER]` | Saves all messages to the file `eQT-DATE.log`, in the given folder or in the folder with the books. |
| `--tools FOLDER` | Where to look for EpubCheck and kindlegen (see below). |
| `-d` | With `-k`: smaller MOBI files, but a slower conversion. |
| `-V` | Shows the version of epubQTools. |
| `-h` | Shows all options in short. |

### Extra tools (optional)
* **EpubCheck** (`-p`) - the official EPUB checker, needs Java. Put its zip file
  (not unpacked) into the tools folder.
* **kindlegen** (`-k`) - converts the fixed books to MOBI for old Kindles. Put
  the program into the tools folder (it is also found when it is installed in
  the system).

The tools folder is `~/.local/share/epubQTools/` on Linux and macOS and
`%LOCALAPPDATA%\epubQTools\` on Windows (another one: `--tools FOLDER`).
