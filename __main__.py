#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#



__license__ = 'GNU Affero GPL v3'
__copyright__ = '2014, Robert Błaut listy@blaut.biz'
__appname__ = 'epubQTools'
numeric_version = (0, 8)
__version__ = '.'.join(map(str, numeric_version))
__author__ = 'Robert Błaut <listy@blaut.biz>'

import argparse
import codecs
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from datetime import datetime
from lib.epubqcheck import qcheck
from lib.epubqcheck import find_opf
from lib.epubqfix import qfix
from lib.epubqfix import rename_files
from lib.fix_name_author import fix_name_author
from lib.azkfix import to_azk

SFENC = sys.getfilesystemencoding()

if sys.platform == "win32":
    from lib.win_utf8_console import fix_broken_win_console
    fix_broken_win_console()

if not hasattr(sys, 'frozen'):
    q_cwd = os.path.join(os.getcwd(), os.path.dirname(__file__))
    if q_cwd.endswith('.zip'):
        q_cwd = q_cwd[:q_cwd.rfind(os.sep)]
    else:
        q_cwd = os.path.join(q_cwd, os.pardir)
else:
    q_cwd = os.path.join(os.getcwd(), os.path.dirname(sys.executable))


parser = argparse.ArgumentParser()
parser.add_argument('-V', '--version', action='version',
                    version="%(prog)s (version " + __version__ + ")")
parser.add_argument("directory", help="Directory with EPUB files stored")
parser.add_argument("--tools", nargs='?',
                    default=q_cwd, metavar="DIR",
                    help="path to additional tools: kindlegen, "
                    "epubcheck zip")
parser.add_argument('-l', '--log', nargs='?', metavar='DIR', const='1',
                    help='path to directory to write log file. If DIR is '
                    ' omitted write log to directory with epub files')
parser.add_argument('-i', '--individual', nargs='?', metavar='NR',
                    const='nonr', help='individual file mode')
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
parser.add_argument("-q", "--qcheck", help="validate files with qcheck "
                    "internal tool",
                    action="store_true")
parser.add_argument("-p", "--epubcheck", help="validate epub files with "
                    " EpubCheck 4 tool",
                    action="store_true")
parser.add_argument("--list-fonts",
                    help="list all fonts in EPUB (only with -q)",
                    action="store_true")
parser.add_argument("-m", "--mod", help="validate only _moh.epub files "
                    "(works only with -q or -p)",
                    action="store_true")
parser.add_argument("-e", "--epub", help="fix and hyphenate original epub "
                    "files to _moh.epub files", action="store_true")
parser.add_argument("-s", "--skip-hyphenate",
                    help="do not hyphenate book (only with -e)",
                    action="store_true")
parser.add_argument("-r", "--skip-hyphenate-headers",
                    help="do not hyphenate headers like h1, h2, h3..."
                    "(only with -e)",
                    action="store_true")
parser.add_argument("--skip-reset-css",
                    help='skip linking a reset CSS file to every xthml file'
                    ' (only with -e)',
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
parser.add_argument("-x", "--myk-fix",
                    help="fix for MYK conversion oddity (experimental) "
                    "(only with -e)",
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
parser.add_argument("-z", "--azk", help="convert _moh.mobi files to"
                    " .azk with azkcreator", action="store_true")
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
args = parser.parse_args()
uni_dir = args.directory


class Logger(object):
    def __init__(self, filename='eQT-default.log'):
        self.terminal = sys.stdout
        self.log = codecs.open(filename, 'w', 'utf-8')

    def write(self, message):
        self.terminal.write(message)
        if sys.platform == 'win32':
            message = message.replace('\n', '\r\n')
        self.log.write(message)


def main():
    if args.alter and not args.qcheck:
        print('* WARNING! -a was ignored because it works only with -q.')
    if args.huffdic and not args.kindlegen:
        print('* WARNING! -d was ignored because it works only with -k.')
    if args.force and not (args.epub or args.kindlegen or args.azk):
        print('* WARNING! -f was ignored because it works only with -e or -k.')
    if args.mod and not (args.qcheck or args.epubcheck):
        print('* WARNING! -m was ignored because it works only with -q or -p.')
    if not args.skip_reset_css and not args.epub:
        print('* WARNING! --skip-reset-css was ignored because it works only '
              'with -e.')
    if args.skip_hyphenate and not args.epub:
        print('* WARNING! --skip-hyphenate was ignored because it works only '
              'with -e.')
    if args.replace_font_files and not args.epub:
        print('* WARNING! -t was ignored because it works only with -e.')
    if not args.skip_justify and not args.epub:
        print('* WARNING! --skip-justify was ignored because it works only '
              'with -e.')
    if args.left and not args.epub:
        print('* WARNING! --left was ignored because it works only with -e.')
    if args.log == '1':
        st = datetime.now().strftime('%Y%m%d%H%M%S')
        sys.stdout = Logger(os.path.join(uni_dir, 'eQT-' + st +
                                         '.log'))
    elif args.log != '1' and args.log is not None:
        st = datetime.now().strftime('%Y%m%d%H%M%S')
        sys.stdout = Logger(os.path.join(args.log, 'eQT-' + st +
                                         '.log'))
    ind_file = ind_root = None
    if args.individual == 'nonr':
        print('')
        print('**********************************************')
        print('*** Listing EPUB files for individual mode ***')
        print('**********************************************')
        print('')
        counter = 0
        for root, dirs, files in os.walk(uni_dir):
            for f in files:
                if f.lower().endswith('.epub') and not f.lower().endswith(
                        '_moh.epub'):
                    print(counter, os.path.join(root, f))
                    counter += 1
        return 0
    elif args.individual != 'nonr' and args.individual is not None:
        counter = 0
        for root, dirs, files in os.walk(uni_dir):
            for f in files:
                if f.lower().endswith('.epub') and not f.lower().endswith(
                        '_moh.epub'):
                    if counter == int(args.individual):
                        ind_file = f
                        ind_root = root
                    counter += 1
    if (
            (args.author or args.title) and args.individual != 'nonr' and
            args.individual is not None
    ):
        print('')
        print('******************************************')
        print('*** Processing author or book title... ***')
        print('******************************************')
        print('')
        fix_name_author(ind_root, ind_file, args.author, args.title)

    if args.rename:
        print('')
        print('******************************************')
        print('*** Renaming EPUBs to "author - title" ***')
        print('******************************************')
        print('')
        counter = 0
        if ind_file:
            counter += 1
            fdec = ind_file
            epbzf = zipfile.ZipFile(os.path.join(ind_root, ind_file))
            opf_root, opf_path = find_opf(epbzf)
            rename_files(opf_path, ind_root, epbzf, ind_file, fdec)
        else:
            for root, dirs, files in os.walk(uni_dir):
                for f in files:
                    fdec = f
                    if f.lower().endswith('.epub') and not f.lower().endswith(
                            '_moh.epub'):
                        counter += 1
                        try:
                            epbzf = zipfile.ZipFile(os.path.join(root, f))
                        except zipfile.BadZipfile as e:
                            print('! CRITICAL! Problem with file "%s": %s' % (
                                f, str(e).decode(SFENC)))
                        opf_root, opf_path = find_opf(epbzf)
                        rename_files(opf_path, root, epbzf, f, fdec)
        if counter == 0:
            print('* NO epub files for renaming found!')

    if args.mod and ind_file:
        ind_file_m = os.path.splitext(ind_file)[0] + '_moh.epub'
    else:
        ind_file_m = ind_file

    if args.qcheck:
        print('')
        print('******************************************')
        print('*** Checking with internal qcheck tool ***')
        print('******************************************')
        if args.mod:
            fe = '_moh.epub'
            nfe = '_org.epub'
        else:
            fe = '.epub'
            nfe = '_moh.epub'
        counter = 0
        if ind_file:
            counter += 1
            qcheck(ind_root, ind_file_m, args.alter, args.mod, args.list_fonts)
        else:
            for root, dirs, files in os.walk(uni_dir):
                for f in files:
                    if f.lower().endswith(fe) and not f.lower().endswith(nfe):
                        counter += 1
                        qcheck(root, f, args.alter, args.mod, args.list_fonts)
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
                '%s' % epubchecker_path.encode(SFENC),
                '%s' % os.path.join(root, f).encode(SFENC)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            jpout, jperr = jp.communicate()
            if jperr:
                print(f + ': PROBLEMS FOUND...')
                print('*** Details... ***')
                print(jperr.decode(SFENC))
            else:
                print(f + ': OK!')
                print('')

        for e in os.listdir(os.path.join(args.tools)):
            if e.startswith('epubcheck-4.'):
                epubcheckstr = os.path.splitext(e)[0]
                break
            else:
                epubcheckstr = ''
        epubcheckjar = 'epubcheck.jar'

        print('')
        print('***********************************************')
        print('*** Checking with ' + epubcheckstr + ' tool ***')
        print('***********************************************')
        try:
            subprocess.Popen(
                ['java', '-version'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except:
            sys.exit('Java is NOT installed. Giving up...')
        try:
            echpzipfile = zipfile.ZipFile(os.path.join(args.tools,
                                          epubcheckstr + '.zip'))
        except:
            sys.exit(epubcheckstr + 'EpubCheck 4.x ZIP file not found '
                     'in directory: "' + args.tools + '" Giving up...')
        echp_temp = tempfile.mkdtemp(suffix='', prefix='quiris-tmp-')
        echpzipfile.extractall(echp_temp)
        if args.mod:
            fe = '_moh.epub'
            nfe = '_org.epub'
        else:
            fe = '.epub'
            nfe = '_moh.epub'
        counter = 0

        if ind_file:
            counter += 1
            if os.path.exists(os.path.join(ind_root, ind_file_m)):
                epubchecker(echp_temp, ind_root, ind_file_m, epubcheckstr,
                            epubcheckjar)
            else:
                print('File "%s" not found...' % ind_file_m)
        else:
            for root, dirs, files in os.walk(uni_dir):
                for f in files:
                    if f.lower().endswith(fe) and not f.lower().endswith(nfe):
                        counter += 1
                        epubchecker(echp_temp, root, f, epubcheckstr,
                                    epubcheckjar)
        for p in os.listdir(os.path.join(echp_temp, os.pardir)):
            if 'quiris-tmp-' in p:
                if os.path.isdir(os.path.join(echp_temp, os.pardir, p)):
                    shutil.rmtree(os.path.join(echp_temp, os.pardir, p))
        if counter == 0:
            print('')
            print('* NO epub files for checking found!')

    if args.epub:
        print('')
        print('******************************************')
        print('*** Fixing with internal qfix tool...  ***')
        print('******************************************')
        counter = 0
        if ind_file:
            counter += 1
            qfix(ind_root, ind_file, args.force, args.replace_font_files,
                 args.skip_reset_css, args.tools, args.skip_hyphenate,
                 args.skip_justify, args.left, args.myk_fix,
                 args.remove_colors, args.remove_fonts, args.font_dir,
                 args.fix_missing_container, args.book_margin,
                 args.skip_hyphenate_headers, args.replace_font_family)
        else:
            for root, dirs, files in os.walk(uni_dir):
                for f in files:
                    if (f.lower().endswith('.epub') and
                            not f.lower().endswith('_moh.epub') and
                            not f.lower().endswith('_org.epub')):
                        counter += 1
                        qfix(root, f, args.force, args.replace_font_files,
                             args.skip_reset_css, args.tools,
                             args.skip_hyphenate, args.skip_justify, args.left,
                             args.myk_fix, args.remove_colors,
                             args.remove_fonts, args.font_dir,
                             args.fix_missing_container,
                             args.book_margin, args.skip_hyphenate_headers,
                             args.replace_font_family)
        if counter == 0:
            print('')
            print('* NO epub files for fixing found!')

    if args.kindlegen:
        print('')
        print('******************************************')
        print('*** Converting with kindlegen tool...  ***')
        print('******************************************')

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
                    os.path.join(args.tools, kgapp).encode(SFENC),
                    '-dont_append_source',
                    compression,
                    os.path.join(root, f).encode(SFENC)
                ], stdout=subprocess.PIPE).communicate()[0]
            except OSError:
                try:
                    proc = subprocess.Popen([
                        os.path.join(kgapp).encode(SFENC),
                        '-dont_append_source',
                        compression,
                        os.path.join(root, f).encode(SFENC)
                    ], stdout=subprocess.PIPE).communicate()[0]
                except:
                    sys.exit('ERROR! Kindlegen not found in directory: "' +
                             args.tools + '" Giving up...')
            for ln in proc.splitlines():
                if 'Warning' in ln and 'W14029' not in ln:
                    print(' ', ln)
                if 'Error' in ln:
                    print(' ', ln)
                    error_found = True
                if ('I1052' in ln):
                    cover_html_found = True
            if not cover_html_found and not error_found:
                print('')
                print('* WARNING: Probably duplicated covers generated '
                      'in file: ' + newmobifile)

        compression = '-c2' if args.huffdic else '-c1'
        counter = 0
        cover_html_found = error_found = False
        if ind_file:
            counter += 1
            to_mobi(ind_root, os.path.splitext(ind_file)[0] + '_moh.epub',
                    cover_html_found, error_found)
        else:
            for root, dirs, files in os.walk(uni_dir):
                for f in files:
                    cover_html_found = error_found = False
                    if f.lower().endswith('_moh.epub'):
                        counter += 1
                        to_mobi(root, f, cover_html_found, error_found)
        if counter == 0:
            print('')
            print('* NO *_moh.epub files for converting found!')

    if args.azk:
        print('')
        print('***********************************************')
        print('*** Converting MOBI with AZKcreator tool... ***')
        print('***********************************************')

        counter = 0
        if ind_file:
            counter += 1
            to_azk(ind_root, os.path.splitext(ind_file)[0] + '_moh.mobi',
                   args.force)
        else:
            for root, dirs, files in os.walk(uni_dir):
                for f in files:
                    if f.lower().endswith('_moh.mobi'):
                        counter += 1
                        to_azk(root, f, args.force)
        if counter == 0:
            print('')
            print('* NO *_moh.mobi files for converting found!')

    if len(sys.argv) == 2:
        parser.print_help()
        print("* * *")
        print("* At least one of above optional arguments is required.")
        print("* * *")
    return 0

if __name__ == '__main__':
    sys.exit(main())
