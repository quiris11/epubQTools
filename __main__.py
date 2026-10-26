#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

import argparse
import atexit
import codecs
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import unicodedata

from datetime import datetime
from lib.epubqcheck import qcheck
from lib.epubqcheck import find_opf
from lib.epubqfix import qfix
from lib.epubqfix import problem_files
from lib.epubqfix import rename_files
from lib.fix_name_author import fix_name_author

__license__ = 'GNU Affero GPL v3'
__copyright__ = '2014, Robert Błaut listy@blaut.biz'
__appname__ = 'epubQTools'
numeric_version = (0, 9)
__version__ = '.'.join(map(str, numeric_version))
__author__ = 'Robert Błaut <listy@blaut.biz>'


if not hasattr(sys, 'frozen'):
    q_cwd = os.path.join(os.getcwd(), os.path.dirname(__file__))
    if q_cwd.endswith('.zip'):
        q_cwd = q_cwd[:q_cwd.rfind(os.sep)]
    else:
        q_cwd = os.path.join(q_cwd, os.pardir)
else:
    q_cwd = os.path.join(os.getcwd(), os.path.dirname(sys.executable))

# per-user folder with kindlegen and epubcheck zip
if sys.platform == 'win32':
    user_tools_dir = os.path.join(
        os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), __appname__)
else:
    user_tools_dir = os.path.join(
        os.environ.get('XDG_DATA_HOME') or
        os.path.join(os.path.expanduser('~'), '.local', 'share'), __appname__)


parser = argparse.ArgumentParser()
parser.add_argument('-V', '--version', action='version',
                    version="%(prog)s (version " + __version__ + ")")
directory_arg = parser.add_argument("directory",
                                    help="Directory with EPUB files stored")
parser.add_argument("--tools", nargs='?', metavar="DIR",
                    help="path to additional tools: kindlegen, "
                    "epubcheck zip (default: " + user_tools_dir + ")")
# -l without a value; an object, so any DIR (also '1') can be given
LOG_IN_BOOK_DIR = object()
parser.add_argument('-l', '--log', nargs='?', metavar='DIR',
                    const=LOG_IN_BOOK_DIR,
                    help='path to directory to write log file. If DIR is '
                    ' omitted write log to directory with epub files')
parser.add_argument('-i', '--individual', nargs='?', metavar='NR',
                    const='nonr',
                    help='individual file mode: without NR select files '
                    'in the console (or list them if not run in a terminal), '
                    'NR processes the files with the given numbers, e.g. '
                    '"3" or "1,3,5-7"')
parser.add_argument('--author', nargs='?', metavar='Surname, First Name',
                    const='no_author',
                    help='set new author name (only with -i)')
parser.add_argument('--title', nargs='?', metavar='Title',
                    const='no_title',
                    help='set new book title (only with -i')
parser.add_argument('--font-dir', nargs='?', metavar='DIR', default=None,
                    help='path to directory with user fonts stored')
parser.add_argument('--replace-font-family', nargs='?', metavar='old,new',
                    default=None,
                    help="pair of \"old_font_family,new_font_family\""
                    "(only with -e and with --font-dir)")
parser.add_argument("-a", "--alter", help="alternative output display",
                    action="store_true")
parser.add_argument("-n", "--rename", help="rename .epub files to "
                    "'author - title.epub'",
                    action="store_true")
parser.add_argument("-t", "--prepare-send-to-kindle", help="copy MOH files to "
                    "'title.epub' (Send to Kindle friendly)",
                    action="store_true")
parser.add_argument("-q", "--qcheck", help="validate files with qcheck "
                    "internal tool",
                    action="store_true")
parser.add_argument("-p", "--epubcheck", help="validate epub files with "
                    " EpubCheck 4 tool",
                    action="store_true")
parser.add_argument("-w", "--skip-font-mime",
                    help="do not report non-standard font media types "
                    "(only with -q)",
                    action="store_true")
parser.add_argument("-u", "--skip-css-warnings",
                    help="do not report CSS warnings, only CSS errors "
                    "(only with -q)",
                    action="store_true")
parser.add_argument("--list-fonts",
                    help="list all fonts in EPUB (only with -q)",
                    action="store_true")
parser.add_argument("-m", "--mod", help="validate only _moh.epub files "
                    "(works only with -q or -p)",
                    action="store_true")
parser.add_argument("-e", "--epub", help="fix and hyphenate original epub "
                    "files to _moh.epub files in 'MOH' subfolder",
                    action="store_true")
parser.add_argument("-s", "--skip-hyphenate",
                    help="do not hyphenate book (only with -e)",
                    action="store_true")
parser.add_argument("-r", "--skip-hyphenate-headers",
                    help="do not hyphenate headers like h1, h2, h3..."
                    "(only with -e)",
                    action="store_true")
parser.add_argument("--skip-page-list",
                    help="do not add a list of approximate pages to books "
                    "without one (only with -e)",
                    action="store_true")
parser.add_argument("-c", "--skip-reset-css",
                    help='skip linking a full reset CSS file to every xthml '
                    'file; if the book is hyphenated, a CSS with '
                    '"hyphens: manual" only is linked instead (only with -e)',
                    action="store_false")
parser.add_argument("--skip-justify", help='skip replacing '
                    '"text-align: left" '
                    'with "text-align: justify" in all CSS files '
                    '(only with -e)',
                    action="store_false")
parser.add_argument("--left", help='replace "text-align: justify" '
                    'with "text-align: left" in all CSS files (experimental) '
                    '(only with -e)',
                    action="store_true")
parser.add_argument("--replace-font-files",
                    help="replace font files (only with -e)",
                    action="store_true")
parser.add_argument("--remove-colors",
                    help="remove all color definitions from CSS files "
                    "(only with -e)",
                    action="store_true")
parser.add_argument("--remove-fonts",
                    help="remove all embedded font files "
                    "(only with -e)",
                    action="store_true")
parser.add_argument("-k", "--kindlegen", help="convert _moh.epub files to"
                    " .mobi with kindlegen", action="store_true")
parser.add_argument("-d", "--huffdic", help="tell kindlegen to use huffdic "
                    "compression (slow conversion) (only with -k)",
                    action="store_true")
parser.add_argument("-f", "--force",
                    help="overwrite previously generated _moh.epub or "
                    " .mobi files (only with -k or -e)",
                    action="store_true")
parser.add_argument("--fix-missing-container",
                    help="Fix missing META-INF/container.xml file "
                    "in original EPUB file (only with -e)",
                    action="store_true")
parser.add_argument('--book-margin', nargs='?', metavar='NUMBER',
                    help='Add left and right book margin to reset CSS file '
                    '(only with -e)')


def is_number_list(text):
    """'3' or '1,3,5-7' (the value of -i)."""
    return re.fullmatch(r'\d+(-\d+)?(,\d+(-\d+)?)*', text) is not None


def parse_number_list(text, count):
    """'1,3,5-7' -> [1, 3, 5, 6, 7] (sorted, without repeats); None if the
    text is not a number list or a number is not below count."""
    if not is_number_list(text):
        return None
    numbers = set()
    for part in text.split(','):
        first, _, last = part.partition('-')
        numbers.update(range(int(first), int(last or first) + 1))
    if not numbers or max(numbers) >= count:
        return None
    return sorted(numbers)


def individual_without_number(argv):
    """'-i books' means -i without a number followed by the directory (with
    nargs='?' argparse would take 'books' as the number)."""
    argv = list(argv)
    for n, a in enumerate(argv[:-1]):
        if a == '--':
            break
        nxt = argv[n + 1]
        if (a in ('-i', '--individual') and not is_number_list(nxt) and
                not nxt.startswith('-') and nxt != 'nonr'):
            argv.insert(n + 1, 'nonr')
            break
    return argv


def parse_arguments(argv):
    """Parse argv. '-l books' and '--tools books' without another directory
    mean the option without a value followed by the directory (the value of
    the option given last is taken)."""
    argv = individual_without_number(argv)
    directory_arg.nargs = '?'
    try:
        args = parser.parse_args(argv)
    finally:
        directory_arg.nargs = None
    if args.directory is None:
        # position of the last -l/--log and --tools in argv
        last = {}
        for n, a in enumerate(argv):
            if a == '--':
                break
            if a.startswith('--tools'):
                last['tools'] = n
            elif a.startswith(('--log', '-l')):
                last['log'] = n
        for dest in sorted(('log', 'tools'), key=lambda d: last.get(d, -1),
                           reverse=True):
            value = getattr(args, dest)
            if value is not None and value is not LOG_IN_BOOK_DIR:
                args.directory = value
                setattr(args, dest,
                        LOG_IN_BOOK_DIR if dest == 'log' else None)
                break
        else:
            parser.error('the following arguments are required: directory')
    return args


args = parse_arguments(sys.argv[1:])
if not args.tools:
    # the old default (next to the program) still works if the per-user
    # folder was not created
    args.tools = user_tools_dir if os.path.isdir(user_tools_dir) else q_cwd
uni_dir = args.directory
tmpSend2KindDir = 'TS2K'
mohDir = 'MOH'
moh_dir = os.path.join(uni_dir, mohDir)


class ColorStream(object):
    """Colors whole output lines in a terminal according to the message
    convention (see README): red - errors, yellow - warnings, green - success.
    Lines are buffered until the end of line, so a line printed in parts
    (e.g. '... decryption of font file "x"... ' + 'FAILED!') gets one color."""
    RED, YELLOW, GREEN, RESET = '\033[31m', '\033[33m', '\033[32m', '\033[0m'
    HEADER = '\033[1;36m'          # bold cyan

    def __init__(self, stream):
        self.stream = stream
        self.buf = ''
        self.qcheck_mode = False

    def color(self, line):
        s = line.strip()
        if s.startswith('=== '):
            return self.HEADER
        if (('WARNING!' in s or s.startswith('WARNING(')) and
                'CRITICAL!' not in s and 'ERROR!' not in s and
                'FAILED' not in s):
            return self.YELLOW
        if (s.startswith('!') or 'CRITICAL!' in s or 'ERROR!' in s or
                'with PROBLEMS' in s or 'PROBLEMS FOUND' in s or
                s.endswith(('FAILED!', 'NOT FIXED')) or 'FAILED! ' in s or
                s.startswith(('Traceback', 'ERROR(', 'FATAL('))):
            return self.RED
        if (s.startswith('FINISH ') or s.endswith(': OK!') or
                s.endswith(('OK! Decrypted.', 'OK! Replaced.', 'FIXED'))):
            return self.GREEN
        # internal check (-q): every other line is a finding, except info
        if (self.qcheck_mode and s and not s.startswith('START ') and
                'Info: ' not in s and 'Font info for ' not in s):
            return self.YELLOW
        return None

    def write(self, message):
        self.buf += message
        while '\n' in self.buf:
            line, self.buf = self.buf.split('\n', 1)
            c = self.color(line)
            self.stream.write((c + line + self.RESET if c and line.strip()
                               else line) + '\n')
        self.stream.flush()

    def flush(self):
        if self.buf:
            c = self.color(self.buf)
            self.stream.write(c + self.buf + self.RESET if c else self.buf)
            self.buf = ''
        self.stream.flush()


if (sys.stdout.isatty() and 'NO_COLOR' not in os.environ and
        os.environ.get('TERM') != 'dumb'):
    if sys.platform == 'win32':
        os.system('')               # enables ANSI colors in Windows console
    color_stream = sys.stdout = ColorStream(sys.stdout)
    atexit.register(sys.stdout.flush)
else:
    color_stream = None


def print_header(title):
    """Section header: one line of fixed width (ASCII, safe in any console)."""
    print(('=== ' + title + ' ').ljust(72, '='))


class Logger(object):
    def __init__(self, filename='eQT-default.log'):
        self.terminal = sys.stdout
        self.log = codecs.open(filename, 'w', 'utf-8')

    def write(self, message):
        self.terminal.write(message)
        if sys.platform == 'win32':
            message = message.replace('\n', '\r\n')
        self.log.write(message)
    
    def flush(self):
        pass 


def moh_dir_for(root):
    """Folder for the _moh files of the books in root: the same subfolder
    path inside 'MOH' (books with the same file name in different subfolders
    don't overwrite each other's results)."""
    return os.path.normpath(os.path.join(moh_dir,
                                         os.path.relpath(root, uni_dir)))


def skip_output_dirs(root, dirs, skip=(mohDir, tmpSend2KindDir)):
    """Don't let os.walk descend into the tool's own output folders."""
    if root == uni_dir:
        dirs[:] = [d for d in dirs if d not in skip]


def find_original_files():
    """(root, file) of the original EPUB files (not in the output folders),
    sorted alphabetically: files from the given directory first, then
    subfolders. -i NR numbers files in this order."""
    found = []
    for root, dirs, files in os.walk(uni_dir):
        skip_output_dirs(root, dirs)
        for f in files:
            if f.lower().endswith('.epub') and not f.lower().endswith(
                    '_moh.epub'):
                found.append((root, f))
    return sorted(found, key=files_sort_key(uni_dir))


# Polish alphabet order: "ą" after "a", "ł" after "l", "ż" after "ź" etc.
PL_ALPHABET = 'aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż'
PL_ORDER = {c: i for i, c in enumerate(PL_ALPHABET)}


def pl_sort_key(text):
    """Case-insensitive sort key in Polish alphabet order. Non-letters go
    before letters, other accented letters right after their base letter."""
    key = []
    for c in text.casefold():
        base = unicodedata.normalize('NFD', c)[0]
        if c in PL_ORDER:
            key.append((1, PL_ORDER[c], 0))
        elif base in PL_ORDER:
            key.append((1, PL_ORDER[base], ord(c)))
        else:
            key.append((0, ord(c), 0))
    return key, text


def files_sort_key(base_dir):
    """Sort key of (root, file) in Polish alphabet order: files from
    base_dir first, then subfolders."""
    def key(found):
        rel_dir = os.path.relpath(found[0], base_dir)
        parts = [] if rel_dir == os.curdir else rel_dir.split(os.sep)
        return ([pl_sort_key(p) for p in parts],
                pl_sort_key(os.path.splitext(found[1])[0]))
    return key


def number_list(numbers):
    """[1, 3, 5, 6, 7] -> '1,3,5-7' (the reverse of parse_number_list)."""
    parts = []
    for n in numbers:
        if parts and parts[-1][1] == n - 1:
            parts[-1][1] = n
        else:
            parts.append([n, n])
    return ','.join(str(a) if a == b else '%d-%d' % (a, b) for a, b in parts)


def select_files(files):
    """Checklist of files in the console: returns the numbers of the
    selected files ([] if cancelled)."""
    import curses

    lines = []                      # (text, file number or None)
    last_dir = None
    for nr, (root, f) in enumerate(files):
        rel_dir = os.path.relpath(root, uni_dir)
        if rel_dir != last_dir and rel_dir != os.curdir:
            if lines:
                lines.append(('', None))
            lines.append(('[' + rel_dir + ']', None))
        last_dir = rel_dir
        lines.append((f, nr))
    file_lines = [n for n, (_, nr) in enumerate(lines) if nr is not None]
    help_text = ('Up/Down: move  Space: select  a: all  Enter: process  '
                 'q: cancel')

    def run(scr):
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        selected = set()
        cur = top = 0               # cur: index in file_lines
        while True:
            height, width = scr.getmaxyx()
            view = max(height - 3, 1)
            line = file_lines[cur]
            if line < top:
                # show the subfolder header above the first file in it
                top = line - 1 if line and lines[line - 1][1] is None \
                    else line
            elif line >= top + view:
                top = line - view + 1
            scr.erase()
            title = '%d of %d file(s) selected in: %s' % (
                len(selected), len(files), os.path.abspath(uni_dir))
            scr.addnstr(0, 0, title, width - 1, curses.A_BOLD)
            for row, (text, nr) in enumerate(lines[top:top + view]):
                if nr is None:
                    scr.addnstr(row + 1, 0, text, width - 1, curses.A_BOLD)
                    continue
                text = '%s %*d  %s' % ('[x]' if nr in selected else '[ ]',
                                       len(str(len(files) - 1)), nr, text)
                attr = curses.A_REVERSE if top + row == line else 0
                scr.addnstr(row + 1, 0, text, width - 1, attr)
            scr.addnstr(height - 1, 0, help_text, width - 1, curses.A_DIM)
            scr.refresh()
            key = scr.getch()
            if key in (curses.KEY_UP, ord('k')):
                cur = max(cur - 1, 0)
            elif key in (curses.KEY_DOWN, ord('j')):
                cur = min(cur + 1, len(file_lines) - 1)
            elif key == curses.KEY_PPAGE:
                cur = max(cur - view, 0)
            elif key == curses.KEY_NPAGE:
                cur = min(cur + view, len(file_lines) - 1)
            elif key == curses.KEY_HOME:
                cur = 0
            elif key == curses.KEY_END:
                cur = len(file_lines) - 1
            elif key == ord(' '):
                selected ^= {lines[line][1]}
                cur = min(cur + 1, len(file_lines) - 1)
            elif key in (ord('a'), ord('A')):
                selected = (set() if len(selected) == len(files)
                            else set(range(len(files))))
            elif key in (curses.KEY_ENTER, 10, 13):
                # Enter without a selection processes the current file
                return sorted(selected) or [lines[line][1]]
            elif key in (ord('q'), ord('Q')):
                return []

    sys.stdout.flush()
    return curses.wrapper(run)


def ask_for_files(files):
    """Numbers of the files to process, typed in (when curses is not
    available, e.g. on Windows without the windows-curses package)."""
    list_files(files)
    while True:
        try:
            text = input('File numbers to process (e.g. 1,3,5-7), '
                         'Enter to cancel: ').replace(' ', '')
        except EOFError:
            return []
        if not text:
            return []
        numbers = parse_number_list(text, len(files))
        if numbers is not None:
            return numbers
        print('! ERROR! Wrong file numbers: "%s"' % text)


def list_files(files):
    print('Directory: ' + os.path.abspath(uni_dir))
    print('')
    width = len(str(len(files) - 1))
    last_dir = None
    for nr, (root, f) in enumerate(files):
        rel_dir = os.path.relpath(root, uni_dir)
        if rel_dir != last_dir and rel_dir != os.curdir:
            print('')
            print('[' + rel_dir + ']')
        last_dir = rel_dir
        print('  %*d  %s' % (width, nr, f))
    print('')


def find_moh_files():
    """(root, file) of the _moh.epub files made by -e, only from 'MOH'. Old
    results are skipped with a warning: next to the originals, and in the
    flat 'MOH' of older versions (the original is in another subfolder)."""
    originals = {}                  # lowercase name without .epub -> dirs
    outside = []
    for root, dirs, files in os.walk(uni_dir):
        skip_output_dirs(root, dirs)
        for f in files:
            fl = f.lower()
            if fl.endswith('_moh.epub'):
                outside.append(os.path.join(root, f))
            elif fl.endswith('.epub') and not fl.endswith('_org.epub'):
                originals.setdefault(fl[:-len('.epub')], set()).add(
                    os.path.normpath(root))
    found = []
    stale = []
    for root, dirs, files in os.walk(moh_dir):
        org_root = os.path.normpath(
            os.path.join(uni_dir, os.path.relpath(root, moh_dir)))
        for f in files:
            fl = f.lower()
            if not fl.endswith('_moh.epub'):
                continue
            org_dirs = originals.get(fl[:-len('_moh.epub')])
            if org_dirs and org_root not in org_dirs:
                stale.append(os.path.join(root, f))
            else:
                found.append((root, f))
    for paths, where in ((outside, 'outside the "%s" folder' % mohDir),
                         (stale, 'in the "%s" folder with the original in '
                          'another subfolder' % mohDir)):
        if paths:
            print('! WARNING! Skipped %d old _moh.epub file(s) %s (move or '
                  'delete them):' % (len(paths), where))
            for p in sorted(paths):
                print('  - ' + p)
    return sorted(found, key=files_sort_key(moh_dir))


def _stage_moh_epub(src_path, dest_dir, stats):
    """
    Copy one '..._moh.epub' file into the (already-created) staging folder,
    stripping the '_moh' marker from the name. A file left there by an
    earlier run is overwritten.
    """
    fname = os.path.basename(src_path)

    # maxsplit=1 so a title that itself contains " - " isn't truncated
    parts = fname.split(' - ', 1)
    if len(parts) < 2:
        print(f'! ERROR! "{fname}" does not match the '
              f'"Author - Title_moh.epub" pattern, skipping.')
        stats['missing'] += 1
        return

    # Composed (NFC) letters: names on macOS are often decomposed (NFD) and
    # Send to Kindle keeps them so, showing "ś" as "s" + combining accent.
    new_name = unicodedata.normalize('NFC', parts[1])
    if new_name.lower().endswith('_moh.epub'):
        new_name = new_name[:-len('_moh.epub')] + '.epub'

    dest_path = os.path.join(dest_dir, new_name)
    if new_name in stats['staged']:
        # Another source file already produced this same name in this run.
        # Don't overwrite it -- find a free "Title (2).epub" style name.
        base, ext = os.path.splitext(new_name)
        n = 2
        while f'{base} ({n}){ext}' in stats['staged']:
            n += 1
        new_name = f'{base} ({n}){ext}'
        dest_path = os.path.join(dest_dir, new_name)
        print(f'! WARNING! Duplicate result name, saving this one as '
              f'"{new_name}" instead.')
        stats['renamed'] += 1

    try:
        print(f'* Copy and rename: "{fname}" to: "{new_name}"')
        # APFS ignores normalization when matching names, so overwriting an
        # old NFD copy would keep its NFD name. Remove it first.
        if os.path.exists(dest_path):
            os.remove(dest_path)
        shutil.copy2(src_path, dest_path)
        stats['copied'] += 1
        stats['staged'].add(new_name)
    except FileNotFoundError:
        print(f'! ERROR! "{fname}" not found or already renamed.')
        stats['missing'] += 1


def main():
    if args.alter and not args.qcheck:
        print('! WARNING! -a was ignored because it works only with -q.')
    if args.huffdic and not args.kindlegen:
        print('! WARNING! -d was ignored because it works only with -k.')
    if args.force and not (args.epub or args.kindlegen):
        print('! WARNING! -f was ignored because it works only with -e or -k.')
    if args.skip_css_warnings and not args.qcheck:
        print('! WARNING! -u was ignored because it works only with -q.')
    if args.skip_font_mime and not args.qcheck:
        print('! WARNING! -w was ignored because it works only with -q.')
    if args.mod and not (args.qcheck or args.epubcheck):
        print('! WARNING! -m was ignored because it works only with -q or -p.')
    if not args.skip_reset_css and not args.epub:
        print('! WARNING! --skip-reset-css was ignored because it works only '
              'with -e.')
    if args.skip_hyphenate and not args.epub:
        print('! WARNING! --skip-hyphenate was ignored because it works only '
              'with -e.')
    if args.skip_page_list and not args.epub:
        print('! WARNING! --skip-page-list was ignored because it works only '
              'with -e.')
    if args.replace_font_files and not args.epub:
        print('! WARNING! --replace-font-files was ignored because it works '
              'only with -e.')
    if not args.skip_justify and not args.epub:
        print('! WARNING! --skip-justify was ignored because it works only '
              'with -e.')
    if args.left and not args.epub:
        print('! WARNING! --left was ignored because it works only with -e.')
    if args.log is LOG_IN_BOOK_DIR:
        st = datetime.now().strftime('%Y%m%d%H%M%S')
        sys.stdout = Logger(os.path.join(uni_dir, 'eQT-' + st + '.log'))
    elif args.log is not None:
        st = datetime.now().strftime('%Y%m%d%H%M%S')
        sys.stdout = Logger(os.path.join(args.log, 'eQT-' + st + '.log'))
    ind_files = []                  # (root, file) selected with -i
    if args.individual == 'nonr':
        files = find_original_files()
        if not files:
            print('* NO epub files found!')
            return 0
        if sys.stdin.isatty() and sys.__stdout__.isatty():
            try:
                numbers = select_files(files)
            except ImportError:
                numbers = ask_for_files(files)
            if not numbers:
                print('* No files selected.')
                return 0
            ind_files = [files[n] for n in numbers]
            print('')
            print_header('Selected EPUB files')
            print('')
            for n in numbers:
                print('  %d  %s' % (n, os.path.normpath(os.path.join(
                    os.path.relpath(files[n][0], uni_dir), files[n][1]))))
            print('')
            print('* The same files: -i ' + number_list(numbers))
        else:
            print('')
            print_header('Listing EPUB files for individual mode')
            print('')
            list_files(files)
            print('%d file(s). Process them with: -i NR (e.g. 3 or 1,3,5-7)'
                  % len(files))
            return 0
    elif args.individual is not None:
        files = find_original_files()
        numbers = parse_number_list(args.individual, len(files))
        if numbers is None:
            # without this the code below falls back to processing ALL files
            print('! ERROR! File number "%s" not found. Use -i without '
                  'a number to select or list files.' % args.individual)
            return 1
        ind_files = [files[n] for n in numbers]
    if (args.author or args.title) and ind_files:
        if len(ind_files) > 1:
            print('! ERROR! --author and --title work only with one file.')
            return 1
        print('')
        print_header('Processing author or book title')
        print('')
        fix_name_author(ind_files[0][0], ind_files[0][1], args.author,
                        args.title)

    if args.rename:
        print('')
        print_header('Renaming EPUBs to "author - title"')
        print('')
        counter = 0
        if ind_files:
            for ind_root, ind_file in ind_files:
                counter += 1
                epbzf = zipfile.ZipFile(os.path.join(ind_root, ind_file))
                opf_root, opf_path = find_opf(epbzf)
                rename_files(opf_path, ind_root, epbzf, ind_file, ind_file)
        else:
            for root, f in find_original_files():
                counter += 1
                try:
                    epbzf = zipfile.ZipFile(os.path.join(root, f))
                except zipfile.BadZipfile as e:
                    print('! CRITICAL! Problem with file "%s": %s' % (f, e))
                    continue
                opf_root, opf_path = find_opf(epbzf)
                rename_files(opf_path, root, epbzf, f, f)
        if counter == 0:
            print('* NO epub files for renaming found!')

    if args.mod:
        ind_files_m = [(moh_dir_for(r), os.path.splitext(f)[0] + '_moh.epub')
                       for r, f in ind_files]
    else:
        ind_files_m = ind_files

    if args.qcheck:
        print('')
        print_header('Checking with internal qcheck tool')
        if color_stream:
            color_stream.qcheck_mode = True
        counter = 0
        if ind_files:
            for root, f in ind_files_m:
                counter += 1
                qcheck(root, f, args.alter, args.mod, args.list_fonts,
                       args.skip_font_mime, args.skip_css_warnings)
        else:
            for root, f in (find_moh_files() if args.mod else
                            find_original_files()):
                counter += 1
                qcheck(root, f, args.alter, args.mod, args.list_fonts,
                       args.skip_font_mime, args.skip_css_warnings)
        if color_stream:
            sys.stdout.flush()
            color_stream.qcheck_mode = False
        if counter == 0:
            print('')
            print('* NO epub files for checking found!')

    if args.epubcheck:

        def epubchecker(echp_temp, root, f, epubcheckstr, epubcheckjar):
            epubchecker_path = os.path.join(
                echp_temp,
                epubcheckstr, epubcheckjar
            )
            jp = subprocess.Popen([
                'java', '-Djava.awt.headless=true', '-jar',
                '%s' % epubchecker_path,
                '%s' % os.path.join(root, f)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True)
            jpout, jperr = jp.communicate()
            # INFO messages (e.g. RSC-004 for obfuscated fonts) are not
            # problems
            if any(line.strip() and not line.startswith('INFO(')
                   for line in jperr.splitlines()):
                print(f + ': PROBLEMS FOUND...')
                print('Details:')
                print(jperr)
            else:
                print(f + ': OK!')
                print('')

        def version_key(name):
            return [int(x) if x.isdigit() else 0
                    for x in name[len('epubcheck-'):-len('.zip')].split('.')]

        # only ZIP files (an unpacked 'epubcheck-5.x.y' folder may be next
        # to it); the newest version wins
        try:
            tools_files = os.listdir(args.tools)
        except FileNotFoundError:
            tools_files = []
        zips = sorted((e for e in tools_files
                       if e.startswith('epubcheck-5.') and
                       e.lower().endswith('.zip') and
                       os.path.isfile(os.path.join(args.tools, e))),
                      key=version_key)
        epubcheckstr = os.path.splitext(zips[-1])[0] if zips else ''
        epubcheckjar = 'epubcheck.jar'

        print('')
        print_header('Checking with ' + (epubcheckstr or 'EpubCheck') +
                     ' tool')
        try:
            subprocess.Popen(
                ['java', '-version'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except FileNotFoundError:
            sys.exit('! CRITICAL! Java is NOT installed. Giving up...')
        try:
            echpzipfile = zipfile.ZipFile(os.path.join(args.tools,
                                          epubcheckstr + '.zip'))
        except FileNotFoundError:
            sys.exit('! CRITICAL! EpubCheck 5.x ZIP file not found '
                     'in directory: "' + os.path.normpath(args.tools) +
                     '" Giving up...')
        echp_temp = tempfile.mkdtemp(suffix='', prefix='quiris-tmp-')
        echpzipfile.extractall(echp_temp)
        counter = 0

        if ind_files:
            for root, f in ind_files_m:
                counter += 1
                if os.path.exists(os.path.join(root, f)):
                    epubchecker(echp_temp, root, f, epubcheckstr,
                                epubcheckjar)
                else:
                    print('File "%s" not found...' % f)
        else:
            for root, f in (find_moh_files() if args.mod else
                            find_original_files()):
                counter += 1
                epubchecker(echp_temp, root, f, epubcheckstr, epubcheckjar)
        shutil.rmtree(echp_temp, ignore_errors=True)
        if counter == 0:
            print('')
            print('* NO epub files for checking found!')

    if args.epub:
        print('')
        print_header('Fixing with internal qfix tool')
        counter = 0
        # In individual mode only the selected books are processed, so keep
        # the files already staged in TS2K for the other books.
        if not ind_files:
            shutil.rmtree(os.path.join(uni_dir, tmpSend2KindDir),
                          ignore_errors=True)
        if ind_files:
            for ind_root, ind_file in ind_files:
                counter += 1
                qfix(ind_root, ind_file, moh_dir_for(ind_root), args.force,
                     args.replace_font_files,
                     args.skip_reset_css, args.tools, args.skip_hyphenate,
                     args.skip_justify, args.left,
                     args.remove_colors, args.remove_fonts, args.font_dir,
                     args.fix_missing_container, args.book_margin,
                     args.skip_hyphenate_headers, args.replace_font_family,
                     args.skip_page_list)
        else:
            for root, f in find_original_files():
                if f.lower().endswith('_org.epub'):
                    continue
                counter += 1
                qfix(root, f, moh_dir_for(root), args.force,
                     args.replace_font_files,
                     args.skip_reset_css, args.tools,
                     args.skip_hyphenate, args.skip_justify, args.left,
                     args.remove_colors,
                     args.remove_fonts, args.font_dir,
                     args.fix_missing_container,
                     args.book_margin, args.skip_hyphenate_headers,
                     args.replace_font_family, args.skip_page_list)
        if counter == 0:
            print('')
            print('* NO epub files for fixing found!')
        elif problem_files:
            print('')
            print('* Files finished with PROBLEMS (%d of %d):'
                  % (len(problem_files), counter))
            for pf in problem_files:
                print('  - ' + pf)

    if args.kindlegen:
        print('')
        print_header('Converting with kindlegen tool')

        def to_mobi(root, f, cover_html_found, error_found):
            newmobifile = os.path.splitext(f)[0] + '.mobi'
            if not args.force:
                if os.path.isfile(os.path.join(root, newmobifile)):
                    print('* Skipping previously generated _moh file: ' +
                          newmobifile)
                    return 0
            print('')
            print('* Kindlegen: Converting file: ' + f)
            if sys.platform == 'win32':
                kgapp = 'kindlegen.exe'
            else:
                kgapp = 'kindlegen'
            try:
                proc = subprocess.Popen([
                    os.path.join(args.tools, kgapp),
                    '-dont_append_source',
                    compression,
                    os.path.join(root, f)
                ], stdout=subprocess.PIPE).communicate()[0]
            except OSError:
                try:
                    proc = subprocess.Popen([
                        os.path.join(kgapp),
                        '-dont_append_source',
                        compression,
                        os.path.join(root, f)
                    ], stdout=subprocess.PIPE).communicate()[0]
                except FileNotFoundError:
                    sys.exit('! CRITICAL! Kindlegen not found in directory: "' +
                             args.tools + '" Giving up...')
            for ln in str(proc, 'utf-8').splitlines():
                if 'Warning' in ln and 'W14029' not in ln:
                    print(' ', ln)
                if 'Error' in ln:
                    print(' ', ln)
                    error_found = True
                if ('I1052' in ln):
                    cover_html_found = True
            if not cover_html_found and not error_found:
                print('')
                print('! WARNING! Probably duplicated covers generated '
                      'in file: ' + newmobifile)

        compression = '-c2' if args.huffdic else '-c1'
        counter = 0
        cover_html_found = error_found = False
        if ind_files:
            for ind_root, ind_file in ind_files:
                counter += 1
                to_mobi(moh_dir_for(ind_root),
                        os.path.splitext(ind_file)[0] + '_moh.epub',
                        cover_html_found, error_found)
        else:
            for root, f in find_moh_files():
                counter += 1
                to_mobi(root, f, False, False)
        if counter == 0:
            print('')
            print('* NO *_moh.epub files for converting found!')

    if args.prepare_send_to_kindle:
        print('')
        print_header('Copy and rename "MOH" EPUBs for upload via '
                     'Send to Kindle')
        print('')

        dest_dir = os.path.join(uni_dir, tmpSend2KindDir)

        # Start from a clean staging folder, except in individual mode: there
        # only the selected books are staged, overwriting their old copies
        # and keeping the files of the other books.
        if not ind_files:
            shutil.rmtree(dest_dir, ignore_errors=True)
        os.makedirs(dest_dir, exist_ok=True)

        stats = {'copied': 0, 'missing': 0, 'renamed': 0, 'staged': set()}

        if ind_files:
            moh_files = [(moh_dir_for(r), os.path.splitext(f)[0] + '_moh.epub')
                         for r, f in ind_files]
        else:
            moh_files = find_moh_files()
        for root, f in moh_files:
            _stage_moh_epub(os.path.join(root, f), dest_dir, stats)

        if stats['copied'] == 0 and stats['missing'] == 0:
            print('* NO MOH files for copy and rename found!')
        else:
            print(f'* Done: {stats["copied"]} file(s) copied '
                  f'({stats["renamed"]} renamed to avoid a naming clash), '
                  f'{stats["missing"]} skipped due to errors.')

    if len(sys.argv) == 2:
        parser.print_help()
        print("* * *")
        print("* At least one of above optional arguments is required.")
        print("* * *")
    return 0


if __name__ == '__main__':
    sys.exit(main())
