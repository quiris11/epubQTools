# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from lxml import etree

from lib.epubqfix import OPFNS, XHTMLNS, find_xhtml_files, fix_html_toc
from tests.test_epubqcheck import XHTML, opf

NCX = '''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head/><docTitle><text>Book</text></docTitle><navMap>%s</navMap></ncx>'''

NAV_POINT = ('<navPoint id="n%d" playOrder="%d"><navLabel><text>Chapter %d'
             '</text></navLabel><content src="%s"/></navPoint>')


class FixHtmlTocTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, path, text):
        path = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)

    def book(self, pages, spine, ncx_href='toc.ncx', opf_dir='',
             chapters=('c1.xhtml', 'c2.xhtml', 'c3.xhtml', 'c4.xhtml')):
        """Write the files (paths relative to the OPF folder) and return
        the OPF tree with the TOC fixed."""
        hrefs = list(chapters) + list(pages)
        items = [('i%d' % n, h, 'application/xhtml+xml')
                 for n, h in enumerate(hrefs)]
        items += [('ncx', ncx_href, 'application/x-dtbncx+xml'),
                  ('css', '../styles/s.css' if opf_dir else 'styles/s.css',
                   'text/css')]
        ids = dict((h, 'i%d' % n) for n, h in enumerate(hrefs))
        tree = etree.fromstring(opf(items, [ids[h] for h in spine]).encode())
        root = os.path.join(self.dir, opf_dir)
        os.makedirs(root, exist_ok=True)
        ncx_dir = os.path.dirname(os.path.normpath(
            os.path.join(root, ncx_href)))
        self.write(
            os.path.join(ncx_dir, os.path.basename(ncx_href)),
            NCX % ''.join(
                NAV_POINT % (n, n, n, os.path.relpath(
                    os.path.join(root, c), ncx_dir).replace(os.sep, '/'))
                for n, c in enumerate(chapters, 1)))
        for c in chapters:
            self.write(os.path.join(root, c), XHTML % '<p>text</p>')
        for path, body in pages.items():
            self.write(os.path.join(root, path), XHTML % body)
        files, paths = find_xhtml_files(root, tree)
        with redirect_stdout(io.StringIO()):
            return fix_html_toc(tree, root, files, paths), root

    @staticmethod
    def toc_ref(tree):
        return tree.xpath('//opf:reference[@type="toc"]/@href',
                          namespaces=OPFNS)

    def links(self, *chapters):
        return ''.join('<p><a href="%s">%s</a></p>' % (c, c)
                       for c in chapters)

    def test_toc_found_by_links(self):
        pages = {'toc.xhtml': '<h1>Table of Contents</h1>' + self.links(
            'c1.xhtml', 'c2.xhtml#a', 'c3.xhtml', 'c4.xhtml')}
        tree, root = self.book(pages, ['toc.xhtml', 'c1.xhtml', 'c2.xhtml',
                                       'c3.xhtml', 'c4.xhtml'])
        self.assertEqual(self.toc_ref(tree), ['toc.xhtml'])
        self.assertFalse(os.path.exists(
            os.path.join(root, 'epubQTools-toc.xhtml')))

    def test_spis_tresci_still_found(self):
        pages = {'spis.xhtml': '<h1>Spis treści</h1>'}
        tree, root = self.book(pages, ['spis.xhtml', 'c1.xhtml'])
        self.assertEqual(self.toc_ref(tree), ['spis.xhtml'])

    def test_page_outside_spine_is_not_toc(self):
        # e.g. a hidden EPUB 3 nav document
        pages = {'nav.xhtml': self.links(
            'c1.xhtml', 'c2.xhtml', 'c3.xhtml', 'c4.xhtml')}
        tree, root = self.book(pages, ['c1.xhtml', 'c2.xhtml', 'c3.xhtml',
                                       'c4.xhtml'])
        self.assertEqual(self.toc_ref(tree), ['epubQTools-toc.xhtml'])

    def test_notes_page_is_not_toc(self):
        # a page of notes links back to the chapters many times
        pages = {'notes.xhtml': self.links(*[
            'c%d.xhtml#r%d' % (n % 4 + 1, n) for n in range(40)])}
        tree, root = self.book(pages, ['c1.xhtml', 'c2.xhtml', 'c3.xhtml',
                                       'c4.xhtml', 'notes.xhtml'])
        self.assertEqual(self.toc_ref(tree), ['epubQTools-toc.xhtml'])

    def test_few_chapters_only(self):
        pages = {'p.xhtml': self.links('c1.xhtml', 'c2.xhtml')}
        tree, root = self.book(pages, ['p.xhtml', 'c1.xhtml', 'c2.xhtml'],
                               chapters=('c1.xhtml', 'c2.xhtml'))
        self.assertEqual(self.toc_ref(tree), ['epubQTools-toc.xhtml'])

    def test_new_toc_next_to_texts_in_other_folder(self):
        # OEBPS/content.opf, toc.ncx and text/ in the root folder (as in
        # the calibre Quick Start Guides in German, French and Italian)
        chapters = ('../text/c1.xhtml', '../text/c2.xhtml')
        tree, root = self.book({}, chapters, ncx_href='../toc.ncx',
                               opf_dir='OEBPS', chapters=chapters)
        self.assertEqual(self.toc_ref(tree), ['../text/epubQTools-toc.xhtml'])
        self.assertIn('../text/epubQTools-toc.xhtml', tree.xpath(
            '//opf:item/@href', namespaces=OPFNS))
        toc = etree.parse(os.path.join(self.dir, 'text',
                                       'epubQTools-toc.xhtml'))
        self.assertEqual(
            toc.xpath('//xhtml:a/@href', namespaces=XHTMLNS),
            ['c1.xhtml', 'c2.xhtml'])
        self.assertEqual(
            toc.xpath('//xhtml:link/@href', namespaces=XHTMLNS),
            ['../styles/s.css'])

    def test_new_toc_with_texts_in_several_folders(self):
        chapters = ('../a/c1.xhtml', '../b/c2.xhtml')
        tree, root = self.book({}, chapters, ncx_href='../toc.ncx',
                               opf_dir='OEBPS', chapters=chapters)
        self.assertEqual(self.toc_ref(tree), ['epubQTools-toc.xhtml'])
        toc = etree.parse(os.path.join(root, 'epubQTools-toc.xhtml'))
        self.assertEqual(
            toc.xpath('//xhtml:a/@href', namespaces=XHTMLNS),
            ['../a/c1.xhtml', '../b/c2.xhtml'])

    def test_new_toc_texts_next_to_opf(self):
        tree, root = self.book({}, ['c1.xhtml', 'c2.xhtml'],
                               chapters=('c1.xhtml', 'c2.xhtml'))
        self.assertEqual(self.toc_ref(tree), ['epubQTools-toc.xhtml'])
        toc = etree.parse(os.path.join(root, 'epubQTools-toc.xhtml'))
        self.assertEqual(
            toc.xpath('//xhtml:link/@href', namespaces=XHTMLNS),
            ['./styles/s.css'])


if __name__ == '__main__':
    unittest.main()
