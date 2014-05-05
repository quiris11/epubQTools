epubQTools
==========

Tools for checking, correcting and hyphenating epub files

usage: epubQTools.zip [-h] [--echp [ECHP]] [--kgp [KGP]] [-n] [-q]
                                 [-p] [-m] [-e] [-r] [-c] [-t] [-k] [-d] [-f]
                                 directory

positional arguments:
  directory           Directory with EPUB files stored

optional arguments:
  -h, --help          show this help message and exit
  --echp [ECHP]       path too epubcheck-3.0.1 dir
  --kgp [KGP]         path too kindlegen file
  -n, --rename        rename .epub files to 'author - title.epub'
  -q, --qcheck        validate files with qcheck internal tool
  -p, --epubcheck     validate epub files with EpubCheck 3.0.1 tool
  -m, --mod           validate only _moh.epub files (only with -q or -v)
  -e, --epub          fix and hyphenate original epub files to _moh.epub files
  -r, --resetmargins  reset CSS margins for body, html and @page in _moh.epub
                      files (only with -e)
  -c, --findcover     force find cover (risky) (only with -e)
  -t, --replacefonts  replace font (experimental) (only with -e)
  -k, --kindlegen     convert _moh.epub files to .mobi with kindlegen
  -d, --huffdic       tell kindlegen to use huffdic compression (slow
                      conversion)
  -f, --force         overwrite previously generated _moh.epub or .mobi files
                      (only with -k or -e)

