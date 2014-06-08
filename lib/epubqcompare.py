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
parser.add_argument("directory", help="Directory with EPUB files stored")
parser.add_argument('-i', '--individual', nargs='?', metavar='NR',
                    const='nonr', help='individual file mode')
parser.add_argument("-l", '--list-item', nargs='?', metavar='NR', const='nonr',
                    help='number of file of original EPUB to compare')
parser.add_argument("-e", '--extension', nargs='?', default='',
                    help='(with -l only) list only files with given extension')
ar = parser.parse_args()


def epubqcompare():
    ind_file = ind_root = None
    if ar.individual == 'nonr':
        print('')
        print('**********************************************')
        print('*** Listing EPUB files for individual mode ***')
        print('**********************************************')
        print('')
        counter = 0
        for root, dirs, files in os.walk(ar.directory):
            for f in files:
                if f.endswith('.epub') and not f.endswith('_moh.epub'):
                    print(counter, os.path.join(root, f))
                    counter += 1
        return 0
    elif ar.individual != 'nonr' and ar.individual is not None:
        counter = 0
        for root, dirs, files in os.walk(ar.directory):
            for f in files:
                if f.endswith('.epub') and not f.endswith('_moh.epub'):
                    if counter == int(ar.individual):
                        ind_file = f
                        ind_root = root
                    counter += 1
    else:
        return 0
    epubf1 = zipfile.ZipFile(os.path.join(ind_root, ind_file))
    epubf2 = zipfile.ZipFile(os.path.join(
        ind_root, os.path.splitext(ind_file)[0] + '_moh.epub'))
    if ar.list_item == 'nonr':
        print('*** EPUB 1 ***')
        count = 0
        for n in epubf1.namelist():
            if not isinstance(n, unicode):
                n = n.decode('utf-8')
            if n.endswith(ar.extension):
                print(count, n)
            count += 1
        # print('*** EPUB 2 ***')
        # count2 = 0
        # for n in epubf2.namelist():
        #     if not isinstance(n, unicode):
        #         n = n.decode('utf-8')
        #     if n.endswith(ar.extension):
        #         print(count2, n)
        #     count2 += 1
    elif ar.list_item != 'nonr' and ar.list_item is not None:
        lines1 = epubf1.read(epubf1.namelist()[int(ar.list_item)]).split('\n')
        lines2 = epubf2.read(epubf1.namelist()[int(ar.list_item)]).split('\n')
        for line in difflib.unified_diff(lines1, lines2, fromfile='file1',
                                         tofile='file2', lineterm='', n=0):
            print(line)


if __name__ == '__main__':
    sys.exit(epubqcompare())
