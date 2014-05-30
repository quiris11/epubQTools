#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

from __future__ import print_function
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

SFENC = sys.getfilesystemencoding()

if not hasattr(sys, 'frozen'):
    q_cwd = os.path.join(os.getcwd(), os.path.dirname(__file__))
    if q_cwd.endswith('.zip'):
        q_cwd = q_cwd[:q_cwd.rfind(os.sep)]
    else:
        q_cwd = os.path.join(q_cwd, os.pardir)
else:
    q_cwd = os.path.join(os.getcwd(), os.path.dirname(sys.executable))


parser = argparse.ArgumentParser()
parser.add_argument("directory", help="Directory with EPUB files stored")
parser.add_argument("--tools", nargs='?',
                    default=q_cwd, metavar="DIR",
                    help="path to additional tools: kindlegen, "
                    "epubcheck-3.0.1.zip")
parser.add_argument('-l', '--log', nargs='?', metavar='DIR', const='1',
                    help='path to directory to write log file. If DIR is '
                    ' omitted write log to directory with epub files')
parser.add_argument("-a", "--alter", help="alternative output display",
                    action="store_true")
parser.add_argument("-n", "--rename", help="rename .epub files to "
                    "'author - title.epub'",
                    action="store_true")
parser.add_argument("-q", "--qcheck", help="validate files with qcheck "
                    "internal tool",
                    action="store_true")
parser.add_argument("-p", "--epubcheck", help="validate epub files with "
                    " EpubCheck 3.0.1 tool",
                    action="store_true")
parser.add_argument("-m", "--mod", help="validate only _moh.epub files "
                    "(works only with -q or -p)",
                    action="store_true")
parser.add_argument("-e", "--epub", help="fix and hyphenate original epub "
                    "files to _moh.epub files", action="store_true")
parser.add_argument("--skip-hyphenate",
                    help="do not hyphenate book  (only with -e)",
                    action="store_true")
parser.add_argument("--skip-reset-css",
                    help='skip linking a CSS file to every xthml file with '
                    'content: "'
                    '@page { margin: 5pt } '
                    'body, body.calibre { margin: 5pt; padding: 0 }"'
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
parser.add_argument("--replace-fonts",
                    help="replace font (experimental) (only with -e)",
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
args = parser.parse_args()


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
    try:
        os.getcwd().decode('ascii')
    except UnicodeDecodeError:
        sys.exit('ERROR! Current working directory "%s" contains non-ascii '
                 'marks. '
                 'The application is not reliable in this case. Giving up...'
                 % os.getcwd().decode(SFENC))
    print('')
    if args.alter and not args.qcheck:
        print('* WARNING! -a was ignored because it works only with -q.')
    if args.huffdic and not args.kindlegen:
        print('* WARNING! -d was ignored because it works only with -k.')
    if args.force and not (args.epub or args.kindlegen):
        print('* WARNING! -f was ignored because it works only with -e or -k.')
    if args.mod and not (args.qcheck or args.epubcheck):
        print('* WARNING! -m was ignored because it works only with -q or -p.')
    if not args.skip_reset_css and not args.epub:
        print('* WARNING! --skip-reset-css was ignored because it works only '
              'with -e.')
    if args.skip_hyphenate and not args.epub:
        print('* WARNING! --skip-hyphenate was ignored because it works only '
              'with -e.')
    if args.replace_fonts and not args.epub:
        print('* WARNING! -t was ignored because it works only with -e.')
    if not args.skip_justify and not args.epub:
        print('* WARNING! --skip-justify was ignored because it works only '
              'with -e.')
    if args.left and not args.epub:
        print('* WARNING! --left was ignored because it works only with -e.')
    if args.log == '1':
        st = datetime.now().strftime('%Y%m%d%H%M%S')
        sys.stdout = Logger(os.path.join(args.directory, 'eQT-' + st +
                                         '.log'))
    elif args.log != '1' and args.log is not None:
        st = datetime.now().strftime('%Y%m%d%H%M%S')
        sys.stdout = Logger(os.path.join(args.log, 'eQT-' + st +
                                         '.log'))
    if args.rename:
        print('')
        print('******************************************')
        print('*** Renaming EPUBs to "author - title" ***')
        print('******************************************')
        print('')
        counter = 0
        for root, dirs, files in os.walk(args.directory):
            for f in files:
                fdec = f.decode(SFENC)
                if f.endswith('.epub') and not f.endswith('_moh.epub'):
                    counter += 1
                    epbzf = zipfile.ZipFile(os.path.join(root, f))
                    opf_root, opf_path = find_opf(epbzf)
                    rename_files(opf_path, root, epbzf, f, fdec)
        if counter == 0:
            print('* NO epub files for renaming found!')

    if args.qcheck:
        print('')
        print('******************************************')
        print('*** Checking with internal qcheck tool ***')
        print('******************************************')
        qcheck(args.directory, args.mod, args.alter)

    if args.epubcheck:
        print('')
        print('******************************************')
        print('*** Checking with ePubCheck 3.0.1 tool ***')
        print('******************************************')
        try:
            subprocess.Popen(
                ['java', '-version'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except:
            sys.exit('Java is NOT installed. Giving up...')
        try:
            echpzipfile = zipfile.ZipFile(os.path.join(args.tools,
                                          'epubcheck-3.0.1.zip'))
        except:
            sys.exit('epubcheck-3.0.1.zip not found in directory: "' +
                     args.tools + '" Giving up...')
        echp_temp = tempfile.mkdtemp(suffix='', prefix='quiris-tmp-')
        echpzipfile.extractall(echp_temp)
        if args.mod:
            fe = '_moh.epub'
            nfe = '_org.epub'
        else:
            fe = '.epub'
            nfe = '_moh.epub'
        counter = 0
        for root, dirs, files in os.walk(args.directory):
            for f in files:
                if f.endswith(fe) and not f.endswith(nfe):
                    counter += 1
                    epubchecker_path = os.path.join(
                        echp_temp,
                        'epubcheck-3.0.1', 'epubcheck-3.0.1.jar'
                    )
                    jp = subprocess.Popen([
                        'java', '-jar', '%s' % epubchecker_path,
                        '%s' % str(os.path.join(root, f))
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    jpout, jperr = jp.communicate()
                    if jperr:
                        print(f.decode(sys.getfilesystemencoding()) +
                              ': PROBLEMS FOUND...')
                        print('*** Details... ***')
                        print(jperr)
                    else:
                        print(f.decode(sys.getfilesystemencoding()) +
                              ': OK!')
                        print('')
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
        qfix(args.directory, args.force, args.replace_fonts,
             args.skip_reset_css, args.tools, args.skip_hyphenate,
             args.skip_justify, args.left)

    if args.kindlegen:
        print('')
        print('******************************************')
        print('*** Converting with kindlegen tool...  ***')
        print('******************************************')
        compression = '-c2' if args.huffdic else '-c1'
        counter = 0
        for root, dirs, files in os.walk(args.directory):
            for _file in files:
                cover_html_found = error_found = False
                if _file.endswith('_moh.epub'):
                    counter += 1
                    newmobifile = os.path.splitext(_file)[0] + '.mobi'
                    if not args.force:
                        if os.path.isfile(os.path.join(root, newmobifile)):
                            print(
                                '* Skipping previously generated _moh file: ' +
                                newmobifile.decode(sys.getfilesystemencoding())
                            )
                            continue
                    print('')
                    print('* Kindlegen: Converting file: ' +
                          _file.decode(sys.getfilesystemencoding()))
                    if sys.platform == 'win32':
                        kgapp = 'kindlegen.exe'
                    else:
                        kgapp = 'kindlegen'
                    try:
                        proc = subprocess.Popen([
                            os.path.join(args.tools, kgapp),
                            '-dont_append_source',
                            compression,
                            os.path.join(root, _file)
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
                        print(
                            '* WARNING: Probably duplicated covers '
                            'generated in file: ' +
                            newmobifile.decode(sys.getfilesystemencoding())
                        )
        if counter == 0:
            print('')
            print('* NO *_moh.epub files for converting found!')
    if len(sys.argv) == 2:
        parser.print_help()
        print("* * *")
        print("* At least one of above optional arguments is required.")
        print("* * *")
    return 0

if __name__ == '__main__':
    sys.exit(main())
