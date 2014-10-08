epubQTools
==========

Tools for checking, correcting and hyphenating epub files.

#### External apps used by this tool available for download:
* **kindlegen** (only unpacked binary is needed): http://www.amazon.com/kindleformat/kindlegen
* **epubcheck-3.0.1.zip** (Java installed is required for run it): https://github.com/IDPF/epubcheck/releases


```
usage: epubQTools [-h] [-V] [--tools [DIR]] [-l [DIR]] [-i [NR]]
                  [--author [Surname, First Name]] [--title [Title]]
                  [-o [DIR]] [-a] [-n] [-q] [-p] [-m] [-e] [--skip-hyphenate]
                  [--skip-reset-css] [--skip-justify] [--left]
                  [--replace-fonts] [--myk-fix] [--remove-colors]
                  [--remove-fonts] [-k] [-d] [-f]
                  directory

positional arguments:
  directory             Directory with EPUB files stored

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  --tools [DIR]         path to additional tools: kindlegen,
                        epubcheck-3.0.1.zip
  -l [DIR], --log [DIR]
                        path to directory to write log file. If DIR is omitted
                        write log to directory with epub files
  -i [NR], --individual [NR]
                        individual file mode
  --author [Surname, First Name]
                        set new author name (only with -i)
  --title [Title]       set new book title (only with -i
  -o [DIR], --font-dir [DIR]
                        path to directory with user fonts stored
  -a, --alter           alternative output display
  -n, --rename          rename .epub files to 'author - title.epub'
  -q, --qcheck          validate files with qcheck internal tool
  -p, --epubcheck       validate epub files with EpubCheck 3.0.1 tool
  -m, --mod             validate only _moh.epub files (works only with -q or
                        -p)
  -e, --epub            fix and hyphenate original epub files to _moh.epub
                        files
  --skip-hyphenate      do not hyphenate book (only with -e)
  --skip-reset-css      skip linking a reset CSS file to every xthml file
                        (only with -e)
  --skip-justify        skip replacing "text-align: left" with "text-align:
                        justify" in all CSS files (only with -e)
  --left                replace "text-align: justify" with "text-align: left"
                        in all CSS files (experimental) (only with -e)
  --replace-fonts       replace fonts (experimental) (only with -e)
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
```
