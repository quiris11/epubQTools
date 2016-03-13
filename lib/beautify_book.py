#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

from __future__ import print_function
import os
import sys
from lxml import etree
from urllib import unquote

SFENC = sys.getfilesystemencoding()
OPFNS = {'opf': 'http://www.idpf.org/2007/opf'}
XHTMLNS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
NCXNS = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}


def fix_body_id_links(opftree, epub_dir, ncxtree):

    def get_body_id_list(opftree, epub_dir):
        # build list with body tags with id attributes
        xhtml_items = etree.XPath(
            '//opf:item[@media-type="application/xhtml+xml"]',
            namespaces=OPFNS
        )(opftree)
        body_id_list = []
        for i in xhtml_items:
            xhtml_url = i.get('href')
            xhtree = etree.parse(os.path.join(epub_dir, xhtml_url),
                                 parser=etree.XMLParser(recover=False))
            try:
                body_id = etree.XPath('//xhtml:body[@id]',
                                      namespaces=XHTMLNS)(xhtree)[0]
            except IndexError:
                body_id = None
            if body_id is not None:
                body_id_list.append(os.path.basename(
                    xhtml_url
                ) + '#' + body_id.get('id'))
        return body_id_list

    body_id_list = get_body_id_list(opftree, epub_dir)
    contents = etree.XPath('//ncx:content', namespaces=NCXNS)(ncxtree)
    content_src_list = []
    for c in contents:
        content_src_list.append(c.get('src'))
    for c in contents:
        if (c.get('src').split('/')[-1] in body_id_list and
                c.get('src').split('#')[0] not in content_src_list):
            print("* Fixing body_id link: " + c.get('src'))
            c.set('src', c.get('src').split('#')[0])


def rename_files(opftree, ncxtree, epub_dir, old_name_path, new_name_path):

    def fix_references_in_xhtml(opftree, epub_dir, old_name_path,
                                new_name_path):
        xhtml_items = etree.XPath(
            '//opf:item[@media-type="application/xhtml+xml"]',
            namespaces=OPFNS
        )(opftree)

        for i in xhtml_items:
            xhtml_url = i.get('href')
            xhtree = etree.parse(os.path.join(epub_dir, xhtml_url),
                                 parser=etree.XMLParser(recover=False))
            urls = etree.XPath('//xhtml:*[@href or @src]',
                               namespaces=XHTMLNS)(xhtree)
            exclude_urls = ('http://', 'https://', 'mailto:',
                            'tel:', 'data:', '#')
            xhtml_dir = os.path.dirname(os.path.join(epub_dir, xhtml_url))
            diff_path = os.path.relpath(
                os.path.dirname(os.path.join(epub_dir, old_name_path)),
                os.path.dirname(os.path.join(epub_dir, new_name_path))
            )
            for u in urls:
                if u.get('src'):
                    url = u.get('src')
                elif u.get('href'):
                    url = u.get('href')
                if url.lower().startswith(exclude_urls):
                    continue
                url = unquote(url)
                if '#' in url:
                    frag_url = '#' + url.split('#')[1]
                    url = url.split('#')[0]
                else:
                    frag_url = ''
                if os.path.basename(
                    xhtml_url
                ) == os.path.basename(new_name_path):
                    if u.get('src'):
                        u.set('src', os.path.join(
                            diff_path, u.get('src')
                        ) + frag_url)
                    elif u.get('href'):
                        u.set('href', os.path.join(
                            diff_path, u.get('href')
                        ) + frag_url)
                if os.path.basename(url) == os.path.basename(old_name_path):
                    if u.get('src'):
                        u.set('src', os.path.relpath(
                            os.path.join(epub_dir, new_name_path), xhtml_dir
                        ) + frag_url)
                    elif u.get('href'):
                        u.set('href', os.path.relpath(
                            os.path.join(epub_dir, new_name_path), xhtml_dir
                        ) + frag_url)
            write_file_changes_back(xhtree, os.path.join(epub_dir, xhtml_url))

    def update_opf(opftree, old_name_path, new_name_path):
        items = etree.XPath('//opf:item[@href]', namespaces=OPFNS)(opftree)
        for i in items:
            if i.get('href') == new_name_path:
                # if new_name_path exists unable to continue
                return opftree, False
        for i in items:
            if i.get('href') == old_name_path:
                i.set('href', new_name_path)
                break
        references = etree.XPath('//opf:reference[@href]',
                                 namespaces=OPFNS)(opftree)
        for r in references:
            if r.get('href') == old_name_path:
                r.set('href', new_name_path)
        return opftree, True

    def update_ncx(ncxtree, old_name_path, new_name_path):
        contents = etree.XPath('//ncx:content', namespaces=NCXNS)(ncxtree)
        for c in contents:
            if c.get('src') == old_name_path:
                c.set('src', new_name_path)

    opftree, is_updated = update_opf(opftree, old_name_path, new_name_path)
    if is_updated:
        os.rename(os.path.join(epub_dir, old_name_path),
                  os.path.join(epub_dir, new_name_path))
        ncxtree = update_ncx(ncxtree, old_name_path, new_name_path)
        fix_references_in_xhtml(opftree, epub_dir, old_name_path,
                                new_name_path)
    return opftree, ncxtree


def most_common(lst):
    return max(set(lst), key=lst.count)


def write_file_changes_back(tree, file_path):
    with open(file_path, 'w') as file:
        file.write(etree.tostring(tree.getroot(), pretty_print=True,
                   standalone=False, xml_declaration=True, encoding='utf-8'))


def rename_calibre_cover(opftree, ncxtree, epub_dir):
        for r in etree.XPath('//opf:reference[@type="cover"]',
                             namespaces=OPFNS)(opftree):
            if os.path.basename(r.get('href')) == 'titlepage.xhtml':
                print("* Renaming calibre cover file to 'cover.html'...")
                xhtml_items = etree.XPath(
                    '//opf:item[@media-type="application/xhtml+xml"]',
                    namespaces=OPFNS
                )(opftree)
                xhtml_dirs = []
                for i in xhtml_items:
                    xhtml_dirs.append(os.path.dirname(i.get('href')))
                most_xthml_dir = most_common(xhtml_dirs)
                if most_xthml_dir != '':
                    pass
                rename_files(opftree, ncxtree, epub_dir,
                             r.get('href'), os.path.join(most_xthml_dir,
                                                         'cover.html'))


def beautify_book(root, f):
    from lib.epubqfix import pack_epub
    from lib.epubqfix import unpack_epub
    from lib.epubqfix import clean_temp
    from lib.epubqfix import find_roots
    f = f.replace('.epub', '_moh.epub')
    print('START beautify for: ' + f.decode(SFENC))
    tempdir = unpack_epub(os.path.join(root, f))
    opf_dir, opf_file, is_fixed = find_roots(tempdir)
    epub_dir = os.path.join(tempdir, opf_dir)
    opf_path = os.path.join(tempdir, opf_file)
    parser = etree.XMLParser(remove_blank_text=True)
    opftree = etree.parse(opf_path, parser)
    ncxfile = etree.XPath(
        '//opf:item[@media-type="application/x-dtbncx+xml"]',
        namespaces=OPFNS
    )(opftree)[0].get('href')
    ncx_path = os.path.join(epub_dir, ncxfile)
    ncxtree = etree.parse(ncx_path, parser)

    rename_calibre_cover(opftree, ncxtree, epub_dir)
    fix_body_id_links(opftree, epub_dir, ncxtree)

    write_file_changes_back(opftree, opf_path)
    write_file_changes_back(ncxtree, ncx_path)
    pack_epub(os.path.join(root, f), tempdir)
    clean_temp(tempdir)
    print('FINISH beautify for: ' + f.decode(SFENC))
