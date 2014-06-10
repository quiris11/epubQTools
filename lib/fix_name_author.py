#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

from __future__ import print_function
import zipfile
import os
import sys
from lxml import etree
from lib.epubqfix import pack_epub
from lib.epubqfix import unpack_epub
from lib.epubqfix import clean_temp
from lib.epubqfix import find_roots

SFENC = sys.getfilesystemencoding()
OPFNS = {'opf': 'http://www.idpf.org/2007/opf'}
DCNS = {'dc': 'http://purl.org/dc/elements/1.1/'}


def set_author(tree):
    crs = tree.xpath('//dc:creator', namespaces=DCNS)
    for c in crs:
        print(etree.tostring(c))


def set_title(tree):
    ts = tree.xpath('//dc:title', namespaces=DCNS)
    for t in ts:
        print(etree.tostring(t))


def fix_name_author(root, f, author, title):
    print('')
    print('START work for: ' + f.decode(SFENC))
    try:
        tempdir = unpack_epub(os.path.join(root, f))
    except zipfile.BadZipfile:
        print('Unable to process corrupted file...')
        return 0
    opfd, opff = find_roots(tempdir)
    opff_abs = os.path.join(tempdir, opff)
    parser = etree.XMLParser(remove_blank_text=True)
    opftree = etree.parse(opff_abs, parser)
    if author:
        set_author(opftree)
    if title:
        set_title(opftree)
    newfile = os.path.splitext(f)[0] + '_m.epub'
    pack_epub(os.path.join(root, newfile), tempdir)
    clean_temp(tempdir)
    print('FINISH work for: ' + f.decode(SFENC))
