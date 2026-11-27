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

from lib.beautify_book import rename_file
from lib.epubqfix import (OPFNS, XHTMLNS, find_xhtml_files, fix_html_toc,
                          fix_toc_landmark)
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
             chapters=('c1.xhtml', 'c2.xhtml', 'c3.xhtml', 'c4.xhtml'),
             guide_toc=None):
        """Write the files (paths relative to the OPF folder) and return
        the OPF tree with the TOC fixed (guide_toc: the href of the TOC
        in the guide of the book before the fix)."""
        hrefs = list(chapters) + list(pages)
        items = [('i%d' % n, h, 'application/xhtml+xml')
                 for n, h in enumerate(hrefs)]
        items += [('ncx', ncx_href, 'application/x-dtbncx+xml'),
                  ('css', '../styles/s.css' if opf_dir else 'styles/s.css',
                   'text/css')]
        ids = dict((h, 'i%d' % n) for n, h in enumerate(hrefs))
        tree = etree.fromstring(opf(items, [ids[h] for h in spine]).encode())
        if guide_toc is not None:
            guide = etree.SubElement(tree, '{%s}guide' % OPFNS['opf'])
            etree.SubElement(guide, '{%s}reference' % OPFNS['opf'],
                             type='toc', title='Spis treści', href=guide_toc)
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

    def test_hidden_nav_in_guide_is_replaced(self):
        # an EPUB 3 nav document outside the spine given as the TOC in the
        # guide is never seen by the reader turning the pages
        pages = {'nav.xhtml': '<h1>Spis treści</h1>' + self.links(
            'c1.xhtml', 'c2.xhtml', 'c3.xhtml', 'c4.xhtml')}
        tree, root = self.book(pages, ['c1.xhtml', 'c2.xhtml', 'c3.xhtml',
                                       'c4.xhtml'], guide_toc='nav.xhtml')
        self.assertEqual(self.toc_ref(tree), ['epubQTools-toc.xhtml'])
        self.assertTrue(os.path.exists(
            os.path.join(root, 'epubQTools-toc.xhtml')))
        self.assertIn('epubQTools-toc', tree.xpath(
            '//opf:spine/opf:itemref/@idref', namespaces=OPFNS))

    def test_guide_toc_to_missing_file_is_replaced(self):
        tree, root = self.book({}, ['c1.xhtml', 'c2.xhtml', 'c3.xhtml',
                                    'c4.xhtml'], guide_toc='gone.xhtml#t')
        self.assertEqual(self.toc_ref(tree), ['epubQTools-toc.xhtml'])

    def test_guide_toc_page_of_book_is_kept(self):
        pages = {'text/spis.xhtml': '<h1>Contents</h1>'}
        tree, root = self.book(pages, ['text/spis.xhtml', 'c1.xhtml'],
                               guide_toc='text/./spis.xhtml#top')
        self.assertEqual(self.toc_ref(tree), ['text/./spis.xhtml#top'])
        self.assertFalse(os.path.exists(
            os.path.join(root, 'epubQTools-toc.xhtml')))

    def test_spis_tresci_in_hidden_nav_only(self):
        pages = {'nav.xhtml': '<h1>Spis treści</h1>'}
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


class TocLandmarkTest(unittest.TestCase):
    """Send to Kindle takes the "Go to - Table of Contents" of an EPUB 3
    book from the "toc" landmark of the navigation document."""

    NAV = ('<?xml version="1.0" encoding="utf-8"?>'
           '<html xmlns="http://www.w3.org/1999/xhtml" '
           'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>t</title>'
           '</head><body><nav epub:type="toc"><ol><li>'
           '<a href="text/c1.xhtml">C1</a></li></ol></nav>%s</body></html>')

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def landmarks(self, nav_extra, guide_toc='text/toc.xhtml',
                  nav=True, lang='pl'):
        """Write a book (nav.xhtml next to the OPF, the pages in text/),
        fix the landmark and return the hrefs and texts of the "toc"
        landmarks."""
        items = [('c1', 'text/c1.xhtml', 'application/xhtml+xml'),
                 ('toc', 'text/toc.xhtml', 'application/xhtml+xml'),
                 ('nav', 'nav.xhtml', 'application/xhtml+xml')]
        tree = etree.fromstring(opf(
            items, ['c1', 'toc'],
            '<dc:language>%s</dc:language>' % lang).encode())
        if nav:
            tree.xpath('//opf:item[@id="nav"]', namespaces=OPFNS)[0].set(
                'properties', 'nav')
        guide = tree.xpath('//opf:guide', namespaces=OPFNS)[0]
        etree.SubElement(guide, '{%s}reference' % OPFNS['opf'],
                         type='toc', title='TOC', href=guide_toc)
        os.makedirs(os.path.join(self.dir, 'text'))
        for href in ('text/c1.xhtml', 'text/toc.xhtml'):
            with open(os.path.join(self.dir, href), 'w',
                      encoding='utf-8') as f:
                f.write(XHTML % '<p>text</p>')
        path = os.path.join(self.dir, 'nav.xhtml')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.NAV % nav_extra)
        with redirect_stdout(io.StringIO()):
            fix_toc_landmark(tree, self.dir, lang)
        navtree = etree.parse(path)
        ns = dict(XHTMLNS, epub='http://www.idpf.org/2007/ops')
        self.assertEqual(len(navtree.xpath(
            '//xhtml:nav[@epub:type="landmarks"]', namespaces=ns)),
            1 if nav else 0)
        return [(a.get('href'), a.text) for a in navtree.xpath(
            '//xhtml:nav[@epub:type="landmarks"]//xhtml:a[@epub:type="toc"]',
            namespaces=ns)]

    def test_added_to_landmarks_without_toc(self):
        # as in the books made for this library: cover, title page, body
        self.assertEqual(self.landmarks(
            '<nav epub:type="landmarks" hidden="hidden"><ol><li>'
            '<a epub:type="cover" href="text/c1.xhtml">Cover</a></li></ol>'
            '</nav>'), [('text/toc.xhtml', 'Spis treści')])

    def test_new_landmarks(self):
        self.assertEqual(self.landmarks('', lang='en'),
                         [('text/toc.xhtml', 'Contents')])

    def test_landmark_to_hidden_nav_is_replaced(self):
        self.assertEqual(self.landmarks(
            '<nav epub:type="landmarks"><ol><li><a epub:type="toc" '
            'href="nav.xhtml#toc">Spis</a></li></ol></nav>'),
            [('text/toc.xhtml', 'Spis')])

    def test_landmark_to_page_of_book_is_kept(self):
        self.assertEqual(self.landmarks(
            '<nav epub:type="landmarks"><ol><li><a epub:type="toc" '
            'href="text/c1.xhtml#spis">Spis</a></li></ol></nav>'),
            [('text/c1.xhtml#spis', 'Spis')])

    def test_guide_toc_with_fragment(self):
        self.assertEqual(self.landmarks('', guide_toc='text/toc.xhtml#t'),
                         [('text/toc.xhtml#t', 'Spis treści')])

    def test_epub2_book_without_nav(self):
        self.assertEqual(self.landmarks('', nav=False), [])


class RenameFileNcxTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def rename(self, ncx_href, srcs, old, new):
        opftree = etree.fromstring(opf(
            [('t', old, 'application/xhtml+xml'),
             ('ncx', ncx_href, 'application/x-dtbncx+xml')], ['t']).encode())
        root = os.path.join(self.dir, 'OEBPS')
        os.makedirs(root)
        os.makedirs(os.path.dirname(os.path.normpath(
            os.path.join(root, old))), exist_ok=True)
        with open(os.path.join(root, old), 'w', encoding='utf-8') as f:
            f.write(XHTML % '<p>title</p>')
        ncxtree = etree.fromstring((NCX % ''.join(
            NAV_POINT % (n, n, n, src)
            for n, src in enumerate(srcs, 1))).encode()).getroottree()
        with redirect_stdout(io.StringIO()):
            rename_file(opftree, ncxtree, root, old, new)
        self.assertTrue(os.path.isfile(os.path.join(root, new)))
        return ncxtree.xpath('//ncx:content/@src', namespaces={
            'ncx': 'http://www.daisy.org/z3986/2005/ncx/'})

    def test_ncx_in_other_folder(self):
        # OEBPS/content.opf, toc.ncx and text/ in the root folder
        self.assertEqual(
            self.rename('../toc.ncx',
                        ['text/titlepage.xhtml', 'text/titlepage.xhtml#a',
                         'text/other.xhtml'],
                        '../text/titlepage.xhtml', '../text/cover.html'),
            ['text/cover.html', 'text/cover.html#a', 'text/other.xhtml'])

    def test_ncx_next_to_opf(self):
        self.assertEqual(
            self.rename('toc.ncx', ['text/titlepage.xhtml', 'other.xhtml'],
                        'text/titlepage.xhtml', 'text/cover.html'),
            ['text/cover.html', 'other.xhtml'])


if __name__ == '__main__':
    unittest.main()
