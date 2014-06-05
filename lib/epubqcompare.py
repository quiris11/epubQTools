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
parser.add_argument("-l", "--list-files", help="list all files inside EPUB",
                    action="store_true")
ar = parser.parse_args()


def epubqcompare(file, lisfiles):
    epubf1 = zipfile.ZipFile(os.path.join(os.getcwd(), file))
    epubf2 = zipfile.ZipFile(os.path.join(
        os.getcwd(), os.path.splitext(file)[0] + '_moh.epub'))
    if lisfiles:
        print('*** File 2 ***')
        for n in epubf1.namelist():
            if not isinstance(n, unicode):
                n = n.decode('utf-8')
            print(n)
        print('*** File 2 ***')
        for n in epubf2.namelist():
            if not isinstance(n, unicode):
                n = n.decode('utf-8')
            print(n)
    # for line in difflib.unified_diff(lines1, lines2, fromfile='file1',
    #                                  tofile='file2', lineterm=''):
    #     print(line)


if __name__ == '__main__':
    sys.exit(epubqcompare(ar.file, ar.list_files))
