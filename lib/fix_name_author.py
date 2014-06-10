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
# OPF = 'http://www.idpf.org/2007/opf'
# nsmap = {'opf': OPF}


def set_author(tree, author):
    crs = tree.xpath('//dc:creator', namespaces=DCNS)
    author = author.decode(SFENC)
    au_rev_l = author.split(', ')
    if len(au_rev_l) == 1:
        au_rev = author
    else:
        au_rev = au_rev_l[1] + ' ' + au_rev_l[0]
    newauthor = etree.Element(
        '{http://purl.org/dc/elements/1.1/}creator',
        attrib={'{http://www.idpf.org/2007/opf}file': author,
                '{http://www.idpf.org/2007/opf}role': 'aut'}
    )
    newauthor.text = au_rev
    if len(crs) == 1:
        crs[0].getparent().append(newauthor)
        crs[0].getparent().remove(crs[0])
    elif len(crs) == 0:
        try:
            dcmetadata = tree.xpath('//dc:metadata', namespaces=DCNS)[0]
        except IndexError:
            print('Metadata does not defined...')
            return 0
        dcmetadata.append(newauthor)
    else:
        print('Multiple dc:creator found. Updating the first tag...')
        crs[0].getparent().append(newauthor)
        crs[0].getparent().remove(crs[0])
    print(etree.tostring(newauthor))
    print(etree.tostring(tree, pretty_print=True))


def set_title(tree, title):
    ts = tree.xpath('//dc:title', namespaces=DCNS)
    newtitle = etree.Element('{http://purl.org/dc/elements/1.1/}creator')
    title = title.decode(SFENC)
    newtitle.text = title
    if len(ts) == 1:
        ts[0].getparent().append(newtitle)
        ts[0].getparent().remove(ts[0])
    elif len(ts) == 0:
        try:
            dcmetadata = tree.xpath('//dc:metadata', namespaces=DCNS)[0]
        except IndexError:
            print('Metadata does not defined...')
            return 0
        dcmetadata.append(newtitle)
    else:
        print('Multiple dc:creator found. Updating the first tag...')
        ts[0].getparent().append(newtitle)
        ts[0].getparent().remove(ts[0])
    print(etree.tostring(tree, pretty_print=True))


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
        set_author(opftree, author)
    if title:
        set_title(opftree, title)
    newfile = os.path.splitext(f)[0] + '_m.epub'
    pack_epub(os.path.join(root, newfile), tempdir)
    clean_temp(tempdir)
    print('FINISH work for: ' + f.decode(SFENC))
