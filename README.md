epubQTools [![Release](https://img.shields.io/github/release/quiris11/epubqtools.svg)](https://github.com/quiris11/epubqtools/releases/latest)
==========

Tools for checking, correcting and hyphenating EPUB files.

#### External apps used by this tool available for download:
* **kindlegen** (only unpacked binary is needed): http://www.amazon.com/kindleformat/kindlegen
* **epubcheck-4.0.1.zip** (Java installed is required for run it): https://github.com/IDPF/epubcheck/releases


```
usage: epubQTools [-h] [-V] [--tools [DIR]] [-l [DIR]] [-i [NR]]
                  [--author [Surname, First Name]] [--title [Title]]
                  [--font-dir [DIR]] [--replace-font-family [old,new]] [-a]
                  [-n] [-q] [-p] [--list-fonts] [-m] [-e] [--skip-hyphenate]
                  [--skip-hyphenate-headers] [--skip-reset-css]
                  [--skip-justify] [--left] [--replace-font-files] [--myk-fix]
                  [--remove-colors] [--remove-fonts] [-k] [-d] [-f]
                  [--fix-missing-container] [--book-margin [NUMBER]]
                  directory

positional arguments:
  directory             Directory with EPUB files stored

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  --tools [DIR]         path to additional tools: kindlegen, epubcheck zip
  -l [DIR], --log [DIR]
                        path to directory to write log file. If DIR is omitted
                        write log to directory with epub files
  -i [NR], --individual [NR]
                        individual file mode
  --author [Surname, First Name]
                        set new author name (only with -i)
  --title [Title]       set new book title (only with -i
  --font-dir [DIR]      path to directory with user fonts stored
  --replace-font-family [old,new]
                        pair of "old_font_family,new_font_family"(only with -e
                        and with --font-dir)
  -a, --alter           alternative output display
  -n, --rename          rename .epub files to 'author - title.epub'
  -q, --qcheck          validate files with qcheck internal tool
  -p, --epubcheck       validate epub files with EpubCheck 4 tool
  --list-fonts          list all fonts in EPUB (only with -q)
  -m, --mod             validate only _moh.epub files (works only with -q or
                        -p)
  -e, --epub            fix and hyphenate original epub files to _moh.epub
                        files
  --skip-hyphenate      do not hyphenate book (only with -e)
  --skip-hyphenate-headers
                        do not hyphenate headers like h1, h2, h3...(only with
                        -e)
  --skip-reset-css      skip linking a reset CSS file to every xthml file
                        (only with -e)
  --skip-justify        skip replacing "text-align: left" with "text-align:
                        justify" in all CSS files (only with -e)
  --left                replace "text-align: justify" with "text-align: left"
                        in all CSS files (experimental) (only with -e)
  --replace-font-files  replace font files (only with -e)
  --myk-fix             fix for MYK conversion oddity (experimental) (only
                        with -e)
  --remove-colors       remove all color definitions from CSS files (only with
                        -e)
  --remove-fonts        remove all embedded font files (only with -e)
  -k, --kindlegen       convert _moh.epub files to .mobi with kindlegen
  -d, --huffdic         tell kindlegen to use huffdic compression (slow
                        conversion) (only with -k)
  -f, --force           overwrite previously generated _moh.epub or .mobi
                        files (only with -k or -e)
  --fix-missing-container
                        Fix missing META-INF/container.xml file in original
                        EPUB file (only with -e)
  --book-margin [NUMBER]
                        Add left and right book margin to reset CSS file (only
                        with -e)
```

#### Additional requirements:
* python -m pip install lxml
* python -m pip install cssutils
* python -m pip install pyinstaller (for compilation only)

#### Compilation tips for creating standalone applications with Pyinstaller tool:
* build on Mac (with Python 2.7.x from Homebrew):
```
pyinstaller -Fn epubQTools ~/github/epubQTools/__main__.py
```
* build on Windows (with Python 2.7.x):
```
C:\Python27\Scripts\pyinstaller.exe -Fn epubQTools .\epubQTools\__main__.py
```
