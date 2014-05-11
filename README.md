epubQTools
==========

Tools for checking, correcting and hyphenating epub files.

```
usage: python epubQTools.zip [-h] [--tools [DIR]] [-l [DIR]] [-a] [-n] [-q] 
                             [-p] [-m] [-e] [-r] [-c] [-t] [-k] [-d] [-f]
                             directory

positional arguments:
  directory             Directory with EPUB files stored

optional arguments:
  -h, --help            show this help message and exit
  --tools [DIR]         path to additional tools: kindlegen,
                        epubcheck-3.0.1.zip, zip-3.0-bin.zip
  -l [DIR], --log [DIR]
                        path to directory to write log file. If DIR is omitted
                        write log to directory with epub files
  -a, --alter           alternative output display
  -n, --rename          rename .epub files to 'author - title.epub'
  -q, --qcheck          validate files with qcheck internal tool
  -p, --epubcheck       validate epub files with EpubCheck 3.0.1 tool
  -m, --mod             validate only _moh.epub files (works only with -q or
                        -p)
  -e, --epub            fix and hyphenate original epub files to _moh.epub
                        files
  -r, --resetmargins    reset CSS margins for body, html and @page in
                        _moh.epub files (only with -e)
  -c, --findcover       force find cover (risky) (only with -e)
  -t, --replacefonts    replace font (experimental) (only with -e)
  -k, --kindlegen       convert _moh.epub files to .mobi with kindlegen
  -d, --huffdic         tell kindlegen to use huffdic compression (slow
                        conversion)
  -f, --force           overwrite previously generated _moh.epub or .mobi
                        files (only with -k or -e)
```
