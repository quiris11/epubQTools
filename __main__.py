#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

import argparse
import codecs
import sys
import subprocess
import os
import subprocess
import zipfile
import shutil
import tempfile

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
parser.add_argument("-s", "--skiphyphenate",
                    help="do not hyphenate book  (only with -e)",
                    action="store_true")
parser.add_argument("-r", "--resetmargins", help="reset CSS margins for "
                    "body, html and @page in _moh.epub files (only with -e)",
                    action="store_true")
parser.add_argument("-c", "--findcover", help="force find cover (risky) "
                    "(only with -e)",
                    action="store_true")
parser.add_argument("-t", "--replacefonts", help="replace font (experimental) "
                    "(only with -e)",
                    action="store_true")
parser.add_argument("-k", "--kindlegen", help="convert _moh.epub files to"
                    " .mobi with kindlegen", action="store_true")
parser.add_argument("-d", "--huffdic", help="tell kindlegen to use huffdic "
                    "compression (slow conversion)", action="store_true")
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
        for root, dirs, files in os.walk(args.directory):
            for f in files:
                fdec = f.decode(SFENC)
                if f.endswith('.epub') and not f.endswith('_moh.epub'):
                    epbzf = zipfile.ZipFile(os.path.join(root, f))
                    opf_root, opf_path = find_opf(epbzf)
                    rename_files(opf_path, root, epbzf, f, fdec)

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
            java = subprocess.Popen(
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
        for root, dirs, files in os.walk(args.directory):
            for f in files:
                if f.endswith(fe) and not f.endswith(nfe):
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

    if args.epub:
        print('')
        print('******************************************')
        print('*** Fixing with internal qfix tool...  ***')
        print('******************************************')
        qfix(args.directory, args.force, args.replacefonts, args.resetmargins,
             args.findcover, args.tools, args.skiphyphenate)

    if args.kindlegen:
        print('')
        print('******************************************')
        print('*** Converting with kindlegen tool...  ***')
        print('******************************************')
        compression = '-c2' if args.huffdic else '-c1'
        for root, dirs, files in os.walk(args.directory):
            for _file in files:
                cover_html_found = error_found = False
                if _file.endswith('_moh.epub'):
                    newmobifile = os.path.splitext(_file)[0] + '.mobi'
                    if not args.force:
                        if os.path.isfile(os.path.join(root, newmobifile)):
                            print(
                                'Skipping previously generated _moh file: ' +
                                newmobifile.decode(sys.getfilesystemencoding())
                            )
                            continue
                    print('')
                    print('Kindlegen: Converting file: ' +
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
                        sys.exit('kindlegen not found in directory: "' +
                                 args.tools + '" Giving up...')
                    for ln in proc.splitlines():
                        if 'Warning' in ln:
                            print(ln)
                        if 'Error' in ln:
                            print(ln)
                            error_found = True
                        if ('I1052' in ln):
                            cover_html_found = True
                    if not cover_html_found and not error_found:
                        print('')
                        print(
                            'WARNING: Probably duplicated covers '
                            'generated in file: ' +
                            newmobifile.decode(sys.getfilesystemencoding())
                        )

    if len(sys.argv) == 2:
        parser.print_help()
        print("* * *")
        print("* At least one of above optional arguments is required.")
        print("* * *")
    return 0

if __name__ == '__main__':
    sys.exit(main())
