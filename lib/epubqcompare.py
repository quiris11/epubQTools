#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

from __future__ import print_function
import argparse
import zipfile
import os
import sys
import difflib


parser = argparse.ArgumentParser()
parser.add_argument("file", help="original EPUB file (without _moh)")
parser.add_argument("nr", nargs='?', default='0',
                    help='nr of file to compare from --list-files')
parser.add_argument("-l", "--list-files", help="list all files inside EPUB",
                    action="store_true")
parser.add_argument("-e", '--extension', nargs='?', default='',
                    help='list only files with given extension')
ar = parser.parse_args()


def epubqcompare(file, nr, lisfiles, ext):
    epubf1 = zipfile.ZipFile(os.path.join(os.getcwd(), file))
    epubf2 = zipfile.ZipFile(os.path.join(
        os.getcwd(), os.path.splitext(file)[0] + '_moh.epub'))
    if lisfiles:
        print('*** File 1 ***')
        count = 0
        for n in epubf1.namelist():
            if not isinstance(n, unicode):
                n = n.decode('utf-8')
            if n.endswith(ext):
                print(count, n)
            count += 1
        print('*** File 2 ***')
        count2 = 0
        for n in epubf2.namelist():
            if not isinstance(n, unicode):
                n = n.decode('utf-8')
            if n.endswith(ext):
                print(count2, n)
            count2 += 1
    else:
        lines1 = epubf1.read(epubf1.namelist()[int(nr)]).split('\n')
        lines2 = epubf2.read(epubf1.namelist()[int(nr)]).split('\n')
        for line in difflib.unified_diff(lines1, lines2, fromfile='file1',
                                         tofile='file2', lineterm='', n=0):
            print(line)


if __name__ == '__main__':
    sys.exit(epubqcompare(ar.file, ar.nr, ar.list_files, ar.extension))
