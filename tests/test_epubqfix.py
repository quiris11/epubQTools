# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
import hashlib
import io
import os
import re
import shutil
import struct
import tempfile
import unittest
import zipfile
import zlib

from contextlib import redirect_stdout
from urllib.parse import quote

from lxml import etree

from lib.epubqcheck import best_cover_image_item, find_opf
from lib.epubqfix import (pack_epub, repair_epub_structure,
                          ClassStyles, add_page_list, check_font, convert_ttc_fonts,
                          convert_note_aside_css, convert_note_asides,
                          create_html_cover,
                          convert_note_asides_in_tree, NOTE_LIST_CSS,
                          fix_list_notes_in_tree,
                          remove_soft_hyphens_from_notes, noteref_targets,
                          prepend_note_list_css, note_aside_css,
                          note_aside_resets,
                          fill_empty_titles,
                          decode_b64_name, deobfuscate_font_data,
                          is_consistent_sfnt, recover_font_key, decrypt_font,
                          decrypt_unlisted_fonts,
                          IDPF_OBFUSCATION,
                          find_file_in_dir,
                          find_font_by_postscript_name, font_postscript_name,
                          fix_links_in_tree, remove_empty_toc_entries,
                          split_extra_cover_images,
                          image_data_end, insert_page_markers,
                          is_fundraising_page, is_purchase_info_page,
                          remove_purchase_info_pages,
                          is_hiding_style, is_support_page,
                          is_wolnelektury_book, most_common, resolve_href, remove_orphan_refining_metas,
                          move_metadata_namespaces,
                          remove_amzn_attributes,
                          remove_thin_spaces_after_spaces,
                          remove_url_line_breaks,
                          move_head_elements_from_body,
                          quote_invalid_url_chars, quote_url,
                          remove_trailing_hidden_div, strip_nav_aria_labels,
                          quote_urls, unquote_urls)

XHTML = ('<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Text</p>%s'
         '</body></html>')
NAME = 'NzkxNjY3MTk1NTMwMjg'


def png_chunk(chunk_type, data):
    return (struct.pack('>I', len(data)) + chunk_type + data +
            struct.pack('>I', zlib.crc32(chunk_type + data)))


class ImageDataEndTest(unittest.TestCase):
    IMAGES = {
        'jpeg': b'\xff\xd8\xff\xe0data\xff\xd9',
        'png': (b'\x89PNG\r\n\x1a\n' +
                png_chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 0, 0, 0,
                                               0)) +
                png_chunk(b'IDAT', zlib.compress(b'\0\0')) +
                png_chunk(b'IEND', b'')),
        'gif': (b'GIF89a\x01\x00\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01'
                b'\x00\x01\x00\x00\x02\x02D\x01\x00;'),
        'webp': b'RIFF' + struct.pack('<I', 8) + b'WEBPVP8 ',
    }

    def test_appended_text(self):
        for kind, data in self.IMAGES.items():
            with self.subTest(kind):
                self.assertEqual(image_data_end(data + b'\n' + NAME.encode()),
                                 len(data))

    def test_unknown_format(self):
        self.assertIsNone(image_data_end(b'<svg/>'))


class BestCoverImageItemTest(unittest.TestCase):
    def items(self, *attrs):
        return [etree.Element('item', **a) for a in attrs]

    def test_back_cover_listed_first_is_not_picked(self):
        images = self.items({'href': 'Images/backcover.jpg'},
                            {'href': 'Images/cover.jpg'})
        self.assertEqual(best_cover_image_item(images).get('href'),
                         'Images/cover.jpg')

    def test_cover_image_property_wins(self):
        images = self.items({'href': 'Images/cover.jpg'},
                            {'href': 'Images/front.jpg',
                             'properties': 'cover-image'})
        self.assertEqual(best_cover_image_item(images).get('href'),
                         'Images/front.jpg')

    def test_back_cover_is_last_resort(self):
        images = self.items({'href': 'Images/background.jpg'},
                            {'href': 'Images/backcover.jpg'})
        self.assertEqual(best_cover_image_item(images).get('href'),
                         'Images/backcover.jpg')
        self.assertIsNone(best_cover_image_item(images[:1]))


class FindOpfMimetypeTest(unittest.TestCase):
    def test_wrong_mime_type_is_reported(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('mimetype', 'application/zip')
            z.writestr('content.opf', '<package/>')
        out = io.StringIO()
        with zipfile.ZipFile(buf) as z, redirect_stdout(out):
            self.assertEqual(find_opf(z), ('', 'content.opf'))
        self.assertIn('incorrect MIME type: application/zip',
                      out.getvalue())


CONTAINER = (
    b'<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:'
    b'names:tc:opendocument:xmlns:container"><rootfiles><rootfile '
    b'full-path="OEBPS/content.opf" media-type="application/'
    b'oebps-package+xml"/></rootfiles></container>')


class RepairEpubStructureTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='eqt-test-')
        self.path = os.path.join(self.dir, 'book.epub')

    def tearDown(self):
        shutil.rmtree(self.dir)

    def make(self, mimetype_last=True, container=True):
        with zipfile.ZipFile(self.path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.comment = b'archive comment'
            if not mimetype_last:
                z.writestr('mimetype', 'application/epub+zip',
                           compress_type=zipfile.ZIP_STORED)
            z.writestr(zipfile.ZipInfo('OEBPS/empty/',
                                       (2001, 2, 3, 4, 5, 6)), b'')
            if container:
                z.writestr('META-INF/container.xml', CONTAINER)
            info = zipfile.ZipInfo('OEBPS/content.opf', (2002, 3, 4, 5, 6, 8))
            info.comment = b'entry comment'
            info.extra = struct.pack('<HHB', 0x5455, 1, 7)
            z.writestr(info, '<package/>', compress_type=zipfile.ZIP_DEFLATED)
            z.writestr('OEBPS/a.css', 'p {}',
                       compress_type=zipfile.ZIP_STORED)
            if mimetype_last:
                z.writestr('mimetype', 'application/epub+zip')

    def entries(self):
        with zipfile.ZipFile(self.path) as z:
            return z.comment, [
                (i.filename, i.date_time, i.compress_type, i.comment,
                 i.extra, i.external_attr, z.read(i))
                for i in z.infolist() if i.filename != 'mimetype']

    def test_mimetype_fixed_and_rest_kept(self):
        self.make()
        before = self.entries()
        self.assertEqual(repair_epub_structure(self.path, self.path),
                         ['mimetype file missing or not the first file '
                          'in the archive'])
        self.assertEqual(self.entries(), before)
        with zipfile.ZipFile(self.path) as z:
            first = z.infolist()[0]
            self.assertEqual(first.filename, 'mimetype')
            self.assertEqual(first.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(first.extra, b'')
            self.assertEqual(z.read(first), b'application/epub+zip')
            self.assertIsNone(z.testzip())

    def test_correct_file_not_rewritten(self):
        self.make(mimetype_last=False)
        mtime = os.stat(self.path).st_mtime_ns
        self.assertEqual(repair_epub_structure(self.path, self.path), [])
        self.assertEqual(os.stat(self.path).st_mtime_ns, mtime)

    def test_missing_container_rebuilt(self):
        self.make(mimetype_last=False, container=False)
        self.assertEqual(repair_epub_structure(self.path, self.path),
                         ['missing or broken META-INF/container.xml'])
        with zipfile.ZipFile(self.path) as z:
            self.assertIn(b'full-path="OEBPS/content.opf"',
                          z.read('META-INF/container.xml'))

    def test_no_opf(self):
        with zipfile.ZipFile(self.path, 'w') as z:
            z.writestr('a.txt', 'x')
        self.assertIsNone(repair_epub_structure(self.path, self.path))

    def test_failed_write_keeps_original(self):
        self.make()
        with open(self.path, 'rb') as f:
            original = f.read()
        src = os.path.join(self.dir, 'src')
        os.makedirs(src)
        with open(os.path.join(src, 'a.txt'), 'w') as f:
            f.write('x')
        real_write = zipfile.ZipFile.write

        def interrupted(*args, **kwargs):
            raise KeyboardInterrupt
        zipfile.ZipFile.write = interrupted
        try:
            with self.assertRaises(KeyboardInterrupt):
                pack_epub(self.path, src)
        finally:
            zipfile.ZipFile.write = real_write
        with open(self.path, 'rb') as f:
            self.assertEqual(f.read(), original)
        self.assertEqual(sorted(os.listdir(self.dir)), ['book.epub', 'src'])


class RemoveTrailingHiddenDivTest(unittest.TestCase):

    def remove(self, last, css=''):
        tree = etree.fromstring(XHTML % last)
        hidden_divs = {}
        hidden_classes = set()
        remove_trailing_hidden_div(tree, hidden_divs, hidden_classes,
                                   ClassStyles([css]))
        removed = len(tree[0]) == 1
        return removed, hidden_divs, hidden_classes

    def test_div_with_class(self):
        self.assertEqual(
            self.remove('<div class="my_class" style="font-size:1px '
                        '!important;">%s</div>' % NAME),
            (True, {NAME: 1}, {'my_class'}))

    def test_other_hiding_styles(self):
        for last in ('<div style="font-size:0; color:#fff">%s</div>',
                     '<p style="display: none">%s</p>',
                     '<span style="visibility:hidden">%s</span>'):
            with self.subTest(last):
                self.assertEqual(self.remove(last % NAME),
                                 (True, {NAME: 1}, set()))

    def test_hiding_class(self):
        css = '.hide { display: none }'
        self.assertEqual(
            self.remove('<p class="x hide">%s</p>' % NAME, css),
            (True, {NAME: 1}, {'x', 'hide'}))
        self.assertEqual(
            self.remove('<p class="x">%s</p>' % NAME, css),
            (False, {}, set()))
        self.assertEqual(
            self.remove('<p class="hide">Short</p>', css),
            (False, {}, set()))

    def test_class_styles(self):
        styles = ClassStyles(['.a { font-size: 0 } p.b { display: none }',
                              '.a.c { font-size: 1em } .d { display: none } '
                              '.d { display: block } .e { font-size: 0 '
                              '!important } @media print { .f { display: '
                              'none } } .g { visibility: hidden } '
                              'body .g { visibility: visible }'])
        for tag, classes, style, hiding in (
                ('div', ['a'], '', True),
                ('div', ['a', 'c'], '', False),          # specificity
                ('div', ['a'], 'font-size: 1em', False),  # inline style
                ('div', ['x'], 'font-size: 0', True),
                ('p', ['b'], '', True),
                ('div', ['b'], '', False),               # other type
                ('div', ['d'], '', False),               # later rule
                ('div', ['e'], 'font-size: 1em', True),  # !important
                ('div', ['e'], 'font-size: 1em !important', False),
                ('div', ['f'], '', False),               # @media
                ('div', ['g'], '', False),               # uncertain
                ('div', ['g'], 'display: none', True)):
            with self.subTest((tag, classes, style)):
                self.assertIs(styles.is_hiding(tag, classes, style), hiding)

    def test_short_text_is_not_a_class_name(self):
        self.assertEqual(
            self.remove('<div style="font-size:1px !important">x</div>'),
            (True, {'': 1}, set()))

    def test_not_removed(self):
        for last in ('<div style="font-size:1px">Normal text.</div>',
                     '<p style="display:none">Short</p>',
                     '<div style="font-size:12px">%s</div>' % NAME,
                     '<div style="font-size:1px !important">%s</div>tail'
                     % NAME):
            with self.subTest(last):
                self.assertEqual(self.remove(last), (False, {}, set()))


class RemoveThinSpacesAfterSpacesTest(unittest.TestCase):

    def remove(self, body):
        tree = etree.fromstring(
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>a '
            ' b</title></head><body>%s</body></html>' % body)
        n = remove_thin_spaces_after_spaces(tree)
        self.assertEqual(tree[0][0].text, 'a  b')  # <head> untouched
        return n, etree.tostring(tree[1], encoding='unicode')

    def test_removed_in_text_and_tail(self):
        n, body = self.remove('<p>Mój  syn <i>i  ja</i> '
                              ' tu.</p>')
        self.assertEqual(n, 3)
        self.assertIn('<p>Mój syn <i>i ja</i> tu.</p>', body)

    def test_other_thin_spaces_kept(self):
        n, body = self.remove('<p>1 000 a  b</p>')
        self.assertEqual(n, 0)
        self.assertIn('1 000 a  b', body)


class RemoveAmznAttributesTest(unittest.TestCase):
    def test_amzn_attributes_removed(self):
        tree = etree.fromstring(
            '<html xmlns="http://www.w3.org/1999/xhtml" amzn-src-id="1">'
            '<body amzn-src-id="2"><p id="p1" amzn-src-id="3">Text</p>'
            '<!-- note --></body></html>')
        self.assertEqual(remove_amzn_attributes(tree), 3)
        self.assertEqual(etree.tostring(tree, encoding='unicode'),
                         '<html xmlns="http://www.w3.org/1999/xhtml">'
                         '<body><p id="p1">Text</p><!-- note --></body>'
                         '</html>')


class QuoteUrlsTest(unittest.TestCase):
    def test_hrefs_round_trip_encoded(self):
        tree = etree.ElementTree(etree.fromstring(
            '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
            '<item id="a" href="Images/x_%5BConverted%5D1.png"/>'
            '<item id="b" href="Text/rozdzia\u0142%201.xhtml"/>'
            '<item id="c" href="Text/a%25b.xhtml"/>'
            '</manifest><guide>'
            '<reference href="Text/rozdzia\u0142%201.xhtml#p%5B1%5D"/>'
            '</guide></package>'))
        unquote_urls(tree)
        hrefs = [e.get('href') for e in tree.iter() if e.get('href')]
        self.assertEqual(hrefs[0], 'Images/x_[Converted]1.png')
        quote_urls(tree)
        hrefs = [e.get('href') for e in tree.iter() if e.get('href')]
        self.assertEqual(hrefs, [
            'Images/x_%5BConverted%5D1.png',
            'Text/rozdzia\u0142%201.xhtml',
            'Text/a%25b.xhtml',
            'Text/rozdzia\u0142%201.xhtml#p%5B1%5D'])


class FillEmptyTitlesTest(unittest.TestCase):
    HTML = ('<html xmlns="http://www.w3.org/1999/xhtml"><head>%s</head>'
            '<body><p>Text</p></body></html>')

    def test_empty_title_filled(self):
        for title in ('<title/>', '<title> </title>'):
            tree = etree.fromstring(self.HTML % title)
            self.assertTrue(fill_empty_titles(tree, 'Wdowa'))
            self.assertIn('<title>Wdowa</title>', etree.tostring(
                tree, encoding='unicode'))

    def test_title_kept(self):
        tree = etree.fromstring(self.HTML % '<title>Rozdział</title>')
        self.assertFalse(fill_empty_titles(tree, 'Wdowa'))
        self.assertIn('<title>Rozdział</title>', etree.tostring(
            tree, encoding='unicode'))


class RemoveUrlLineBreaksTest(unittest.TestCase):

    def test_line_breaks_removed(self):
        tree = etree.fromstring(XHTML % (
            '<a href="https://www.&#10;example.org/a&#9;b">x</a>'
            '<img src="a&#13;.png" alt=""/><a href="ok.html">y</a>'))
        self.assertEqual(remove_url_line_breaks(tree), 2)
        html = etree.tostring(tree, encoding='unicode')
        self.assertIn('href="https://www.example.org/ab"', html)
        self.assertIn('src="a.png"', html)
        self.assertIn('href="ok.html"', html)

    def test_url_from_link_text(self):
        # a hyphen doubled at the line break, the text has the right URL
        tree = etree.fromstring(XHTML % (
            '<a href="http://a.org/tips-&#10;-for/">http://a.org/tips-\u00adfor/'
            '</a><a href="http://b.org/x-&#10;-y">http://c.org/x-y</a>'
            '<a href="http://d.org/x-&#10;-y">d.org/x-y</a>'))
        self.assertEqual(remove_url_line_breaks(tree), 3)
        html = etree.tostring(tree, encoding='unicode')
        self.assertIn('href="http://a.org/tips-for/"', html)
        # other URL or no scheme in the text: only the line break removed
        self.assertIn('href="http://b.org/x--y"', html)
        self.assertIn('href="http://d.org/x--y"', html)


class QuoteInvalidUrlCharsTest(unittest.TestCase):

    def test_quote_url(self):
        for url, quoted in (
                ('http://a.org/130600_ imagejuifs.htm',
                 'http://a.org/130600_%20imagejuifs.htm'),
                (' ch 1.html#a b ', 'ch%201.html#a%20b'),
                ('a%20b%zz[1].html', 'a%20b%25zz%5B1%5D.html'),
                ('http://[::1]:80/x', 'http://[::1]:80/x'),
                ('rozdział.html#ł', 'rozdział.html#ł')):
            self.assertEqual(quote_url(url), quoted)

    def test_attributes_fixed(self):
        tree = etree.fromstring(XHTML % (
            '<a href="http://a.org/x y">x</a><img src="a b.png" alt=""/>'
            '<img src="data:image/png;base64, AAAA" alt=""/>'
            '<a href="ok.html">y</a>'))
        self.assertEqual(quote_invalid_url_chars(tree), 2)
        html = etree.tostring(tree, encoding='unicode')
        self.assertIn('href="http://a.org/x%20y"', html)
        self.assertIn('src="a%20b.png"', html)
        self.assertIn('src="data:image/png;base64, AAAA"', html)


class MoveHeadElementsFromBodyTest(unittest.TestCase):
    HTML = ('<html xmlns="http://www.w3.org/1999/xhtml"><head>%s</head>'
            '<body><p/>\n<title>Rozdzia\u0142 I\u00a0Ca\u0142y</title>\n'
            '<link href="a.css" rel="stylesheet" type="text/css"/>\n'
            '<meta content="DocBook" name="generator"/>\n'
            '<div><p>Text</p></div></body></html>')

    def test_moved_to_head(self):
        tree = etree.fromstring(self.HTML % '<title/>')
        self.assertEqual(move_head_elements_from_body(tree), 3)
        head, body = tree
        self.assertEqual(
            [etree.QName(e).localname for e in head],
            ['title', 'link', 'meta'])
        self.assertEqual(head[0].text, 'Rozdzia\u0142 I\u00a0Ca\u0142y')
        self.assertEqual(
            [etree.QName(e).localname for e in body], ['p', 'div'])
        self.assertEqual(body[0].tail, '\n')

    def test_title_and_duplicate_link_removed(self):
        tree = etree.fromstring(self.HTML % (
            '<title>Book</title><link href="a.css" rel="stylesheet"/>'))
        self.assertEqual(move_head_elements_from_body(tree), 3)
        head = tree[0]
        self.assertEqual(
            [etree.QName(e).localname for e in head],
            ['title', 'link', 'meta'])
        self.assertEqual(head[0].text, 'Book')

    def test_no_head(self):
        tree = etree.fromstring(XHTML % '<title>X</title>')
        self.assertEqual(move_head_elements_from_body(tree), 0)


class FixLinksTest(unittest.TestCase):
    HREFS = {'text/a.xhtml', 'text/b.xhtml', 'www.local.html'}
    IDS = {'text/a.xhtml': {'x'}, 'text/b.xhtml': {'y'}}

    def fix(self, body):
        tree = etree.fromstring(XHTML % body)
        n = fix_links_in_tree(tree, 'text/a.xhtml', self.HREFS,
                              self.IDS.get)
        return n, etree.tostring(tree, encoding='unicode')

    def test_www_gets_scheme(self):
        n, html = self.fix('<a href="www.example.org">www.ex\u00adample.org'
                           '</a><a href="../www.local.html">z</a>')
        self.assertEqual(n, 1)
        self.assertIn('href="http://www.example.org"', html)
        self.assertIn('href="../www.local.html"', html)

    def test_date_after_url_removed(self):
        n, html = self.fix('<a href="http://a.org/h.html (18.03.2012)">h</a>'
                           '<a href="http://a.org/x y">h</a>')
        self.assertEqual(n, 1)
        self.assertIn('href="http://a.org/h.html"', html)
        self.assertIn('href="http://a.org/x y"', html)

    def test_text_linked_to_itself_unwrapped(self):
        n, html = self.fix('<a href="War Stories">War Sto\u00adries</a>, '
                           '<a id="i" href="Other">Other</a>'
                           '<a href="Missing">text</a>')
        self.assertEqual(n, 2)
        self.assertIn('>War Sto\u00adries, <a id="i">Other</a>', html)
        self.assertIn('<a href="Missing">text</a>', html)

    def test_missing_fragment_removed(self):
        n, html = self.fix('<a href="b.xhtml#y">1</a><a href="b.xhtml#z">2</a>'
                           '<a href="#x">3</a><a href="#q">4</a>')
        self.assertEqual(n, 2)
        self.assertIn('<a href="b.xhtml#y">1</a><a href="b.xhtml">2</a>'
                      '<a href="#x">3</a><a>4</a>', html)


class RemoveEmptyTocEntriesTest(unittest.TestCase):
    OPF = ('<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
           '<manifest>'
           '<item id="ncx" href="toc.ncx" '
           'media-type="application/x-dtbncx+xml"/>'
           '<item id="nav" href="nav.xhtml" properties="nav" '
           'media-type="application/xhtml+xml"/>'
           '</manifest></package>')
    NAV = ('<html xmlns="http://www.w3.org/1999/xhtml" '
           'xmlns:epub="http://www.idpf.org/2007/ops"><body>'
           '<nav epub:type="toc"><ol>'
           '<li><a href="a.xhtml">A</a></li><li><a href="b.xhtml"/></li>'
           '<li><a href="c.xhtml"> </a><ol><li><a href="d.xhtml">D</a>'
           '</li></ol></li></ol></nav></body></html>')
    NCX = ('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" '
           'version="2005-1"><navMap>'
           '<navPoint id="a"><navLabel><text>A</text></navLabel>'
           '<content src="a.xhtml"/></navPoint>'
           '<navPoint id="b"><navLabel><text/></navLabel>'
           '<content src="b.xhtml"/></navPoint></navMap></ncx>')

    def test_empty_entries_removed(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in (('nav.xhtml', self.NAV),
                               ('toc.ncx', self.NCX)):
                with open(os.path.join(d, name), 'w') as f:
                    f.write(text)
            opftree = etree.fromstring(self.OPF).getroottree()
            self.assertEqual(remove_empty_toc_entries(opftree, d), 2)
            with open(os.path.join(d, 'nav.xhtml')) as f:
                nav = f.read()
            with open(os.path.join(d, 'toc.ncx')) as f:
                ncx = f.read()
        self.assertNotIn('b.xhtml', nav)
        # an entry with subentries stays
        self.assertIn('c.xhtml', nav)
        self.assertNotIn('b.xhtml', ncx)
        self.assertIn('a.xhtml', ncx)


class ConvertNoteAsidesTest(unittest.TestCase):
    NOTES = ('<aside id="n1" epub:type="rearnote"><p><span>1</span> One '
             '<a href="a.xhtml#r1">&#8617;</a></p></aside>\n'
             '<aside id="n2"><p>Two</p><p>Second paragraph</p></aside>'
             '<div id="page9"/>'
             '<aside id="n3" class="x"><p>Three</p></aside>'
             '<aside id="side">Sidebar</aside>')

    def convert(self, body, note_ids):
        tree = etree.fromstring(
            XHTML.replace('<html ', '<html xmlns:epub='
                          '"http://www.idpf.org/2007/ops" ') % body)
        n = convert_note_asides_in_tree(tree, note_ids)
        return n, etree.tostring(tree, encoding='unicode')

    def test_notes_converted_to_list_items(self):
        n, html = self.convert(self.NOTES, {'n2', 'n3'})
        self.assertEqual(n, (2, 1))
        # the back link moved to the number: the note stays an aside
        self.assertIn('<aside id="n1" epub:type="rearnote" class="eqt_note">'
                      '<p><a href="a.xhtml#r1"><span>1</span></a> One</p>'
                      '</aside>', html)
        # the single paragraph is replaced with the list item
        self.assertIn('<li id="n2"><p>Two</p><p>Second paragraph</p></li>',
                      html)
        self.assertIn('<li id="n3" class="x">Three</li>', html)
        # not a note
        self.assertIn('<aside id="side">Sidebar</aside>', html)

    def test_id_of_paragraph_kept(self):
        n, html = self.convert(
            '<aside epub:type="footnote"><p id="fn1">One</p></aside>'
            '<aside id="n2"><p id="fn2">Two</p></aside>', set())
        self.assertEqual(n, (1, 0))
        self.assertIn('<li epub:type="footnote" id="fn1">One</li>', html)
        # both ids kept, so the paragraph stays
        n, html = self.convert(
            '<aside id="n2"><p id="fn2">Two</p></aside>', {'n2'})
        self.assertIn('<li id="n2"><p id="fn2">Two</p></li>', html)

    def test_role_removed(self):
        n, html = self.convert(
            '<aside id="n1" role="doc-footnote"><p>One</p></aside>'
            '<aside id="n2" role="presentation"><p>Two</p></aside>',
            {'n1', 'n2'})
        self.assertIn('<li id="n1">One</li>', html)
        self.assertIn('<li id="n2" role="presentation">Two</li>', html)

    def test_back_link_moved_to_number(self):
        n, html = self.convert(
            '<aside id="n1"><p><span class="no">12.</span> One <i>x</i> '
            '<a href="a.xhtml#r1" role="doc-backlink">↩</a></p></aside>'
            '<aside id="n2"><p><sup>[2]</sup> Two</p><p>More '
            '<a href="a.xhtml#r2">↩</a> </p></aside>', {'n1', 'n2'})
        self.assertEqual(n, (0, 2))
        self.assertIn('<aside id="n1" class="eqt_note"><p>'
                      '<a href="a.xhtml#r1" role="doc-backlink">'
                      '<span class="no">12.</span></a> One <i>x</i></p>'
                      '</aside>', html)
        self.assertIn('<aside id="n2" class="eqt_note"><p>'
                      '<a href="a.xhtml#r2"><sup>[2]</sup></a> Two</p>'
                      '<p>More </p></aside>', html)

    def test_notes_with_back_link_at_start_kept(self):
        n, html = self.convert(
            '<aside id="n1" class="fn" role="doc-footnote" '
            'style="border-top: 1px solid; margin: 1em"><p>'
            '<a href="a.xhtml#r1">1</a> One</p></aside>'
            '<aside id="n2" style="page-break-before: always"><p><sup>'
            '<a href="#r2">2</a></sup> Two</p><p>More</p></aside>'
            '<aside id="n3"><a href="#r3">3.</a> Three</aside>',
            {'n1', 'n2', 'n3'})
        self.assertEqual(n, (0, 3))
        self.assertIn('<aside id="n1" class="fn eqt_note" role="doc-footnote" '
                      'style="margin: 1em"><p><a href="a.xhtml#r1">1</a> '
                      'One</p></aside>', html)
        self.assertIn('<aside id="n2" class="eqt_note"><p><sup>', html)
        self.assertIn('<aside id="n3" class="eqt_note"><a href="#r3">3.</a>',
                      html)
        # a second run does not add the class again
        tree = etree.fromstring(html)
        self.assertEqual(convert_note_asides_in_tree(tree, {'n1'}), (0, 1))
        self.assertIn('class="fn eqt_note"',
                      etree.tostring(tree, encoding='unicode'))

    def test_back_link_kept(self):
        for note in (
                # no number at the start
                '<p>One <a href="a.xhtml#r1">↩</a></p>',
                '<p>Text <span>1</span> <a href="a.xhtml#r1">↩</a></p>',
                # the number is already a link
                '<p><a href="a.xhtml#r1">1</a> One '
                '<a href="a.xhtml#r1">↩</a></p>',
                # text after the link, or a link to a web page
                '<p><span>1</span> <a href="a.xhtml#r1">↩</a> One</p>',
                '<p><span>1</span> See <a href="http://x.pl/#a">x</a></p>',
                '<p><span>1</span> See <a href="b.xhtml">b</a></p>'):
            n, html = self.convert('<aside id="n1">%s</aside>' % note,
                                   {'n1'})
            self.assertIn('<li id="n1">%s</li>' % note[3:-4], html)

    def test_noteref_targets_without_back_links(self):
        tree = etree.fromstring(
            XHTML.replace('<html ', '<html xmlns:epub='
                          '"http://www.idpf.org/2007/ops" ') % (
                '<a epub:type="noteref" href="fn.xhtml#n1">1</a>'
                '<a role="doc-noteref" href="#n2">2</a>'
                '<a epub:type="noteref" role="doc-backlink" href="#r1">1</a>'
                '<a epub:type="noteref backlink" href="#r2">2</a>'
                '<a epub:type="referrer" href="#r3">3</a>'))
        self.assertEqual(noteref_targets(tree, 'Text/a.xhtml'),
                         {('Text/fn.xhtml', 'n1'), ('Text/a.xhtml', 'n2')})

    def test_soft_hyphens_removed_from_notes(self):
        tree = etree.fromstring(XHTML % (
            '<p>Te\u00adkst<a href="#n1">1</a></p>'
            '<p><a id="n1" href="#r1">1</a> No\u00adta <i>dłu\u00adga</i>'
            ' i\u00adtail</p>'
            '<ol><li id="n2"><p>Dru\u00adga</p></li></ol>'
            '<section id="n3"><p>Roz\u00addział</p></section>'))
        self.assertEqual(
            remove_soft_hyphens_from_notes(tree, {'n1', 'n2', 'n3', 'x'}), 2)
        html = etree.tostring(tree, encoding='unicode')
        # the block of an inline target, not the text outside of the notes
        self.assertIn('<p><a id="n1" href="#r1">1</a> Nota <i>długa</i>'
                      ' itail</p>', html)
        self.assertIn('<li id="n2"><p>Druga</p></li>', html)
        self.assertIn('Te\u00adkst', html)
        self.assertIn('Roz\u00addział', html)

    def test_consecutive_notes_in_one_list(self):
        n, html = self.convert(
            self.NOTES.replace('<a href="a.xhtml#r1">&#8617;</a>', ''),
            {'n2', 'n3'})
        self.assertEqual(html.count('<ol class="eqt_notes"'), 2)
        self.assertRegex(html, r'<ol [^>]*>\n<li id="n1".*</li>\n'
                               r'<li id="n2".*</li>\n</ol><div id="page9"/>'
                               r'<ol [^>]*>\n<li id="n3"')

    def test_book_notes_found_by_noteref_links(self):
        opf = ('<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
               '<item href="text/a.xhtml" media-type="application/xhtml+xml"/>'
               '<item href="notes.xhtml" media-type="application/xhtml+xml"/>'
               '</manifest></package>')
        a = XHTML % ('<a xmlns:epub="http://www.idpf.org/2007/ops" '
                     'epub:type="noteref" href="../notes.xhtml#n1">1</a>'
                     '<a role="doc-noteref" href="../notes.xhtml#n2">2</a>')
        notes = XHTML % ('<aside id="n1"><p>One</p></aside>'
                         '<aside id="n2"><p>Two</p></aside>'
                         '<aside id="n3"><p>Three</p></aside>')
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'text'))
            for name, text in (('text/a.xhtml', a), ('notes.xhtml', notes)):
                with open(os.path.join(d, name), 'w') as f:
                    f.write(text)
            convert_note_asides(etree.fromstring(opf).getroottree(), d)
            with open(os.path.join(d, 'notes.xhtml')) as f:
                html = f.read()
        self.assertIn('<li id="n1">One</li>', html)
        self.assertIn('<li id="n2">Two</li>', html)
        self.assertIn('<aside id="n3"><p>Three</p></aside>', html)


class FixListNotesTest(unittest.TestCase):
    TEXT = ('<p>Text<sup id="r1"><a href="#n1" class="ref">1</a></sup> and'
            '<sup id="r2"><a href="#n2" class="ref">2</a></sup>.</p>')
    NOTES = ('<div class="footnotes"><ol>\n<li id="n1">\n<p>One. '
             '<a href="#r1" class="back">[back]</a></p>\n</li>\n'
             '<li id="n2"><p>Two <em>b</em>.</p><p>More. '
             '<a href="#r2">[back]</a></p></li></ol></div>')

    def fix(self, body):
        tree = etree.fromstring(XHTML % body)
        ids = fix_list_notes_in_tree(tree)
        return ids, etree.tostring(tree, encoding='unicode')

    def test_back_links_moved_to_numbers(self):
        ids, html = self.fix(self.TEXT + self.NOTES)
        self.assertEqual(ids, {'n1', 'n2'})
        self.assertIn('<ol style="list-style-type: none">', html)
        self.assertIn('<li id="n1">\n<p><a href="#r1" class="back">1.</a> '
                      'One.</p>\n</li>', html)
        self.assertIn('<li id="n2"><p><a href="#r2">2.</a> Two <em>b</em>.'
                      '</p><p>More.</p></li>', html)
        self.assertNotIn('[back]', html)
        # the text and a second run change nothing
        self.assertIn(self.TEXT, html)
        tree = etree.fromstring(html)
        self.assertEqual(fix_list_notes_in_tree(tree), set())
        self.assertEqual(etree.tostring(tree, encoding='unicode'), html)

    def test_notes_without_paragraphs_and_link_on_anchor(self):
        ids, html = self.fix(
            '<p>Text<a id="r1" href="#n1">[1]</a></p>'
            '<ol style="margin: 0;"><li id="n1">One <i>x</i> '
            '<a href="#r1">&#8617;</a></li></ol>')
        self.assertEqual(ids, {'n1'})
        self.assertIn('<ol style="margin: 0; list-style-type: none">'
                      '<li id="n1"><a href="#r1">1.</a> One <i>x</i></li>',
                      html)

    def assert_unchanged(self, body):
        ids, html = self.fix(body)
        self.assertEqual(ids, set())
        self.assertIn(body, html)

    def test_other_lists_unchanged(self):
        text = self.TEXT
        for body in (
                # one item is not a note: the whole list stays
                text + self.NOTES.replace('</ol>', '<li>Other</li></ol>'),
                # a list item without a back link
                text + '<ol><li id="n1">One</li><li id="n2">Two</li></ol>',
                # the back link is not at the end
                text + '<ol><li id="n1"><a href="#r1">[back]</a> One</li>'
                '<li id="n2">Two <a href="#r2">[back]</a></li></ol>',
                # the back link is a number (which side is the note?)
                text + '<ol><li id="n1">One <a href="#r1">1</a></li>'
                '<li id="n2">Two <a href="#r2">[2]</a></li></ol>',
                # the link in the text is not a number
                '<p><a id="r1" href="#n1">see the list</a></p>'
                '<ol><li id="n1">One <a href="#r1">[back]</a></li></ol>',
                # the link in the text points elsewhere
                '<p><a id="r1" href="#n2">1</a><a id="r2" href="#n2">2</a>'
                '</p><ol><li id="n1">One <a href="#r1">[back]</a></li>'
                '<li id="n2">Two <a href="#r2">[back]</a></li></ol>',
                # the back link points to a block with other links
                '<p id="r1"><a href="#n1">1</a> <a href="#x">2</a></p>'
                '<ol><li id="n1">One <a href="#r1">[back]</a></li></ol>',
                '<div id="r1"><a href="#n1">1</a></div>'
                '<ol><li id="n1">One <a href="#r1">[back]</a></li></ol>',
                # a link to another file
                '<p><a id="r1" href="#n1">1</a></p><ol><li id="n1">One '
                '<a href="a.xhtml#r1">[back]</a></li></ol>',
                # the number is already in the note
                '<p><a id="r1" href="#n1">1</a></p>'
                '<ol><li id="n1">1. One <a href="#r1">[back]</a></li></ol>',
                # not an ordered list
                '<p><a id="r1" href="#n1">1</a></p>'
                '<ul><li id="n1">One <a href="#r1">[back]</a></li></ul>',
                # paragraphs and divs are not changed
                '<p><a id="r1" href="#n1">1</a></p>'
                '<div><p id="n1">One <a href="#r1">[back]</a></p></div>',
                # a repeated id
                '<p><a id="r1" href="#n1">1</a><a id="r1" href="#n1">1</a>'
                '</p><ol><li id="n1">One <a href="#r1">[back]</a></li></ol>',
                # links between the items of the list itself
                '<ol><li id="n1">One <a id="r1" href="#n1">1</a> '
                '<a href="#r1">[back]</a></li></ol>'):
            with self.subTest(body=body):
                self.assert_unchanged(body)

    def test_book_list_notes_without_soft_hyphens(self):
        opf = ('<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
               '<item href="a.xhtml" media-type="application/xhtml+xml"/>'
               '<item href="s.css" media-type="text/css"/>'
               '</manifest></package>')
        body = ('<p>Te\u00adxt<sup id="r1"><a href="#n1">1</a></sup></p>'
                '<ol><li id="n1"><p>No\u00adte '
                '<a href="#r1">[back]</a></p></li></ol>')
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'a.xhtml'), 'w', encoding='utf-8') as f:
                f.write(XHTML % body)
            with open(os.path.join(d, 's.css'), 'w') as f:
                f.write('p {margin: 0}\n')
            with redirect_stdout(out):
                convert_note_asides(etree.fromstring(opf).getroottree(), d)
            with open(os.path.join(d, 'a.xhtml'), encoding='utf-8') as f:
                html = f.read()
            with open(os.path.join(d, 's.css')) as f:
                self.assertEqual(f.read(), 'p {margin: 0}\n')
        self.assertIn('<li id="n1"><p><a href="#r1">1.</a> Note</p></li>',
                      html)
        self.assertIn('Te\u00adxt', html)
        self.assertIn('* Moved back links of 1 notes in list items',
                      out.getvalue())


class NoteListStylesTest(unittest.TestCase):
    OPF = ('<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
           '<item href="text/a.xhtml" media-type="application/xhtml+xml"/>'
           '<item href="text/b.xhtml" media-type="application/xhtml+xml"/>'
           '<item href="css/s.css" media-type="text/css"/>'
           '</manifest></package>')
    CSS = 'aside[id^="n"] {\n    padding: 0.8em 0;\n    border-bottom: 1px solid;}\n'

    def run_convert(self, a_head):
        a = ('<html xmlns="http://www.w3.org/1999/xhtml"><head>%s</head>'
             '<body><aside id="n1" xmlns:epub="http://www.idpf.org/2007/ops" '
             'epub:type="footnote"><p>One</p></aside></body></html>' % a_head)
        with tempfile.TemporaryDirectory() as d:
            for name, text in (('text/a.xhtml', a),
                               ('text/b.xhtml', XHTML % ''),
                               ('css/s.css', self.CSS)):
                os.makedirs(os.path.dirname(os.path.join(d, name)),
                            exist_ok=True)
                with open(os.path.join(d, name), 'w') as f:
                    f.write(text)
            opftree = etree.fromstring(self.OPF).getroottree()
            convert_note_asides(opftree, d)
            # a second run does not add the styles again
            convert_note_asides(opftree, d)
            with open(os.path.join(d, 'text/a.xhtml')) as f:
                html = f.read()
            with open(os.path.join(d, 'css/s.css')) as f:
                css = f.read()
        return html, css

    def test_styles_added_to_linked_css(self):
        html, css = self.run_convert(
            '<link href="../css/s.css" rel="stylesheet" type="text/css"/>'
            '<link href="../css/reset.css" rel="stylesheet" type="text/css"/>')
        self.assertIn('<ol class="eqt_notes">', html)
        self.assertNotIn('<style', html)
        # the list styles first, so the styles of the asides (without the
        # border) take precedence
        self.assertEqual(css, NOTE_LIST_CSS.lstrip('\n') + '\n' +
                         self.CSS.rstrip('\n') +
                         '\n\nol.eqt_notes > li[id^="n"] {\n'
                         '    padding: 0.8em 0;}\n')

    def test_styles_in_file_without_css(self):
        html, css = self.run_convert('<title>A</title>')
        self.assertNotIn('ol.eqt_notes {', css)
        self.assertEqual(html.count('ol.eqt_notes {'), 1)
        self.assertIn('<style type="text/css">', html)

    def test_styles_before_styles_of_file(self):
        html, css = self.run_convert(
            '<title>A</title><style>li { margin: 0; }</style>')
        self.assertLess(html.index('ol.eqt_notes {'),
                        html.index('li { margin: 0; }'))


class NoteAsideStylesTest(unittest.TestCase):
    OPF = NoteListStylesTest.OPF
    CSS = ('aside {\n    margin: 1em 0;\n    border-bottom: 1px solid;}\n'
           'section > aside.fn { page-break-before: always }\n')
    NOTE = ('<aside id="n1" class="fn"><p><a href="b.xhtml#r1">1</a> One'
            '</p></aside>')

    def run_convert(self, a_head, css=None):
        a = ('<html xmlns="http://www.w3.org/1999/xhtml"><head>%s</head>'
             '<body>%s</body></html>' % (a_head, self.NOTE))
        b = XHTML % '<a role="doc-noteref" href="a.xhtml#n1">1</a>'
        with tempfile.TemporaryDirectory() as d:
            for name, text in (('text/a.xhtml', a), ('text/b.xhtml', b),
                               ('css/s.css', css or self.CSS)):
                os.makedirs(os.path.dirname(os.path.join(d, name)),
                            exist_ok=True)
                with open(os.path.join(d, name), 'w') as f:
                    f.write(text)
            opftree = etree.fromstring(self.OPF).getroottree()
            with redirect_stdout(io.StringIO()):
                convert_note_asides(opftree, d)
                # a second run does not add the styles again
                convert_note_asides(opftree, d)
            with open(os.path.join(d, 'text/a.xhtml')) as f:
                html = f.read()
            with open(os.path.join(d, 'css/s.css')) as f:
                css = f.read()
        return html, css

    def test_rule_added_to_linked_css(self):
        html, css = self.run_convert(
            '<link href="../css/s.css" rel="stylesheet" type="text/css"/>')
        self.assertIn('<aside id="n1" class="fn eqt_note">', html)
        self.assertEqual(css, self.CSS + '\naside.eqt_note {\n'
                         '    border: none !important;\n'
                         '    page-break-before: auto !important;}\n')

    def test_no_rule_without_borders_and_page_breaks(self):
        html, css = self.run_convert(
            '<link href="../css/s.css" rel="stylesheet" type="text/css"/>',
            'aside { margin: 1em; }\n')
        self.assertIn('class="fn eqt_note"', html)
        self.assertEqual(css, 'aside { margin: 1em; }\n')

    def test_rule_in_file_without_css(self):
        html, css = self.run_convert(
            '<style>.fn { border: 1px solid; }</style>')
        self.assertEqual(css, self.CSS)
        self.assertEqual(html.count('aside.eqt_note {'), 1)
        self.assertRegex(html, r'</style><style type="text/css">\n'
                               r'aside.eqt_note {\n'
                               r'    border: none !important;}\n</style>'
                               r'</head>')


class NoteAsideResetsTest(unittest.TestCase):
    def test_properties_of_aside_rules(self):
        css = ('/* x */ aside { border-bottom: 1px solid; margin: 0 }\n'
               'section aside.fn, h1 { Page-Break-Before: always }\n'
               'div > .x:first-child { break-inside: avoid }\n'
               'aside p { border: 1px solid; page-break-after: always }\n'
               'p.x span, .xy { border: 1px solid; break-after: page }\n'
               '@media screen { aside { page-break-inside: avoid } }\n')
        self.assertEqual(note_aside_resets(css, {'x'}),
                         {'border', 'page-break-before', 'break-inside',
                          'page-break-inside'})
        self.assertEqual(note_aside_resets('p { border: 0 }', {'x'}), set())

    def test_rule(self):
        self.assertEqual(note_aside_css({'break-after', 'border'}),
                         '\naside.eqt_note {\n    border: none !important;'
                         '\n    break-after: auto !important;}\n')


class PrependNoteListCssTest(unittest.TestCase):
    def test_before_rules(self):
        css = '/* notes */\naside { margin: 1em; }\n'
        self.assertEqual(prepend_note_list_css(css),
                         NOTE_LIST_CSS.lstrip('\n') + '\n' + css)

    def test_after_charset_and_imports(self):
        css = ('\ufeff@charset "utf-8";\n@import url("a.css");\n'
               '/* notes */\naside { margin: 1em; }\n')
        result = prepend_note_list_css(css)
        self.assertTrue(result.startswith(
            '\ufeff@charset "utf-8";\n@import url("a.css");\n'
            'ol.eqt_notes {'))
        self.assertLess(result.index('ol.eqt_notes > li {'),
                        result.index('/* notes */'))

    def test_book_styles_take_precedence(self):
        # an aside without a class: its rule has the same specificity as
        # the default style of the list items, so it must come after it
        css, n = convert_note_aside_css(
            'aside { margin: 1em; }\naside > p { text-indent: 1em; }\n')
        css = prepend_note_list_css(css)
        self.assertLess(css.index('{ margin: 1.2em 0; text-indent: 0; }'),
                        css.index('ol.eqt_notes > li {\n    margin: 1em;'))
        self.assertLess(css.index('{ margin: 1.2em 0; text-indent: 0; }'),
                        css.index('ol.eqt_notes > li {\n    text-indent: 1em;'))


class ConvertNoteAsideCssTest(unittest.TestCase):
    CSS = ('/* notes */\naside[id^="endnote-"] {\n    margin: 1.2em 0;\n'
           '    border-bottom: 1px solid;\n    line-height: 1.6;}\n\n'
           'aside[id^="endnote-"] p {\n    text-indent: 0;\n    margin: 0;\n'
           '    padding: 0;\n    font-size: 0.95em;\n'
           '    font-family: "CustomSerif", serif;}\n\n'
           'p, .aside {\n    margin: 0;}\n')

    def test_note_rules_added(self):
        css, n = convert_note_aside_css(self.CSS)
        self.assertEqual(n, 2)
        # the rules of asides stay, the notes get them without the border
        self.assertIn(self.CSS[:self.CSS.index('aside[id^="endnote-"] p')],
                      css)
        self.assertIn('line-height: 1.6;}\n\n'
                      'ol.eqt_notes > li[id^="endnote-"] {\n'
                      '    margin: 1.2em 0;\n    line-height: 1.6;}', css)
        self.assertIn('\n\nol.eqt_notes > li[id^="endnote-"] p {\n'
                      '    text-indent: 0;\n    margin: 0;\n'
                      '    padding: 0;\n', css)
        # text properties of the unwrapped <p> go to the list item
        self.assertIn('\n\nol.eqt_notes > li[id^="endnote-"] {\n'
                      '    text-indent: 0;\n    font-size: 0.95em;\n'
                      '    font-family: "CustomSerif", serif;}', css)
        self.assertIn('p, .aside {\n    margin: 0;}', css)
        self.assertNotIn('li[id^="endnote-"] {\n    border', css)

    def test_selectors_after_paragraph(self):
        css, n = convert_note_aside_css(
            'section > aside.note p span, aside p.x, nav a {color: red; '
            'border-left: 1px solid}')
        self.assertEqual(n, 1)
        self.assertEqual(
            css, 'section > aside.note p span, aside p.x, nav a {color: red; '
            'border-left: 1px solid}\n\n'
            'section > ol.eqt_notes > li.note p span, '
            'section > ol.eqt_notes > li.note span, '
            'ol.eqt_notes > li p.x {\n    color: red;}')

    def test_page_breaks_removed(self):
        css, n = convert_note_aside_css(
            'aside.fn {margin: 1em 0; page-break-after: always; '
            'break-inside: avoid; Page-Break-Before: auto}')
        self.assertEqual(n, 1)
        self.assertTrue(css.endswith(
            '\n\nol.eqt_notes > li.fn {\n    margin: 1em 0;}'))


class HelpersTest(unittest.TestCase):

    def test_is_hiding_style(self):
        for style in ('font-size: 1PX !important', 'font-size:0',
                      'font-size:.5pt', 'display:none',
                      'color: white; visibility: hidden'):
            with self.subTest(style):
                self.assertTrue(is_hiding_style(style))
        for style in ('', 'font-size:', 'font-size:2px', 'font-size:1em',
                      'display:block'):
            with self.subTest(style):
                self.assertFalse(is_hiding_style(style))

    def test_decode_b64_name(self):
        self.assertEqual(decode_b64_name(NAME), '79166719553028')
        self.assertIsNone(decode_b64_name('my_class'))

    def test_most_common_tie_takes_first(self):
        self.assertEqual(most_common(['serif', 'a', 'a', 'serif']), 'serif')
        self.assertEqual(most_common(['a', 'serif', 'serif', 'a']), 'a')
        self.assertEqual(most_common(['a', 'b', 'b']), 'b')


if __name__ == '__main__':
    unittest.main()


class StripNavAriaLabelsTest(unittest.TestCase):

    def test_removed_from_nav_only(self):
        raw = ('<nav epub:type="toc" id="toc" role="doc-toc" '
               'aria-labelledby="toc-heading">\r\n'
               '<h1 id="toc-heading">Spis</h1>\r\n'
               '<a href="a.xhtml" aria-label="A">A</a></nav>\r\n'
               "<nav epub:type='landmarks' aria-label='Punkty' hidden=''>")
        self.assertEqual(strip_nav_aria_labels(raw), (
            '<nav epub:type="toc" id="toc" role="doc-toc">\r\n'
            '<h1 id="toc-heading">Spis</h1>\r\n'
            '<a href="a.xhtml" aria-label="A">A</a></nav>\r\n'
            "<nav epub:type='landmarks' hidden=''>", 2))

    def test_unchanged(self):
        raw = '<navx aria-label="x"><nav id="toc">'
        self.assertEqual(strip_nav_aria_labels(raw), (raw, 0))


class FindFileInDirTest(unittest.TestCase):

    def test_case_insensitive(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'sub'))
            path = os.path.join(d, 'sub', 'texgyreschola-bold.otf')
            open(path, 'w').close()
            self.assertEqual(
                find_file_in_dir('TeXGyreSchola-Bold.otf', d, True), path)
            self.assertIsNone(
                find_file_in_dir('TeXGyreSchola-Bold.otf', d, False))
            self.assertIsNone(find_file_in_dir('Other.otf', d, True))

    def test_exact_match_first(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ('font.otf', 'Font.otf'):
                open(os.path.join(d, name), 'w').close()
            self.assertEqual(find_file_in_dir('Font.otf', d, False),
                             os.path.join(d, 'Font.otf'))



def ttf_with_postscript_name(ps_name):
    """Minimal TTF: offset table, one table record and a name table."""
    string = ps_name.encode('utf-16-be')
    name = (struct.pack('>HHH', 0, 1, 18) +
            struct.pack('>HHHHHH', 3, 1, 0x409, 6, len(string), 0) + string)
    return (b'\x00\x01\x00\x00' + struct.pack('>HHHH', 1, 16, 0, 0) +
            struct.pack('>4sIII', b'name', 0, 28, len(name)) + name)


class CheckFontTest(unittest.TestCase):

    def test_signatures(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'font')
            for signature, expected in ((b'\x00\x01\x00\x00', True),
                                        (b'OTTO', True), (b'ttcf', True),
                                        (b'\x12\x34\x56\x78', False)):
                with open(path, 'wb') as f:
                    f.write(signature + b'\x00' * 8)
                self.assertEqual(check_font(path), (expected, signature))

class DeobfuscateFontDataTest(unittest.TestCase):

    KEY = bytes(range(1, 21))
    FONT = b'OTTO' + bytes(range(256)) * 20

    def obfuscate(self, data, crypt_len=1040):
        return (bytes(b ^ self.KEY[i % 20]
                      for i, b in enumerate(data[:crypt_len])) +
                data[crypt_len:])

    def test_plain_obfuscation(self):
        self.assertEqual(deobfuscate_font_data(
            self.obfuscate(self.FONT), self.KEY, 1040), self.FONT)

    def test_compressed_before_obfuscation(self):
        deflater = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
        packed = deflater.compress(self.FONT) + deflater.flush()
        self.assertEqual(deobfuscate_font_data(
            self.obfuscate(packed), self.KEY, 1040), self.FONT)

    def test_unobfuscated_font_is_kept(self):
        self.assertEqual(
            deobfuscate_font_data(self.FONT, self.KEY, 1040), self.FONT)

    def test_wrong_key_returns_xored_data(self):
        data = self.obfuscate(self.FONT)
        result = deobfuscate_font_data(data, bytes(20), 1040)
        self.assertEqual(result, data)


def build_sfnt(version=b'OTTO', tags=('BASE', 'CFF ', 'GPOS', 'GSUB', 'OS/2',
                                      'cmap', 'head', 'hhea', 'hmtx', 'maxp',
                                      'name', 'post')):
    """A structurally correct font (table directory, checksums) with
    meaningless tables."""
    n = len(tags)
    entry_selector = n.bit_length() - 1
    search_range = 16 << entry_selector
    header = version + struct.pack('>HHHH', n, search_range, entry_selector,
                                   n * 16 - search_range)
    directory, body, offset = b'', b'', 12 + 16 * n
    for i, tag in enumerate(tags):
        table = bytes((i * 37 + j * 11) % 251 for j in range(150 + 7 * i))
        padded = table + b'\0' * (-len(table) % 4)
        checksum = sum(struct.unpack('>%dI' % (len(padded) // 4),
                                     padded)) & 0xffffffff
        if tag == 'head':
            checksum ^= 0x5a5a5a5a  # outdated, as left by font subsetters
        directory += struct.pack('>4sIII', tag.encode('ascii'), checksum,
                                 offset, len(table))
        body += padded
        offset += len(padded)
    return header + directory + body


class RecoverFontKeyTest(unittest.TestCase):

    IDPF_KEY = hashlib.sha1(b'urn:uuid:original').digest()
    ADOBE_KEY = bytes(range(101, 117))

    def obfuscate(self, data, key, crypt_len):
        return (bytes(b ^ key[i % len(key)]
                      for i, b in enumerate(data[:crypt_len])) +
                data[crypt_len:])

    def test_built_font_is_consistent(self):
        font = build_sfnt()
        self.assertTrue(is_consistent_sfnt(font))
        self.assertFalse(is_consistent_sfnt(font[:-4]))
        broken = bytearray(font)
        broken[-10] ^= 1
        self.assertFalse(is_consistent_sfnt(bytes(broken)))

    def test_idpf_key_of_opentype_font(self):
        font = build_sfnt()
        raw = self.obfuscate(font, self.IDPF_KEY, 1040)
        key = recover_font_key(raw, 20, 1040)
        self.assertEqual(key, self.IDPF_KEY)
        self.assertEqual(deobfuscate_font_data(raw, key, 1040), font)

    def test_idpf_key_of_truetype_font(self):
        font = build_sfnt(b'\x00\x01\x00\x00',
                          ('DSIG', 'GDEF', 'OS/2', 'cmap', 'cvt ', 'fpgm',
                           'glyf', 'head', 'hhea', 'hmtx', 'loca', 'maxp',
                           'name', 'post', 'prep'))
        raw = self.obfuscate(font, self.IDPF_KEY, 1040)
        self.assertEqual(recover_font_key(raw, 20, 1040), self.IDPF_KEY)

    def test_adobe_key(self):
        font = build_sfnt()
        raw = self.obfuscate(font, self.ADOBE_KEY, 1024)
        self.assertEqual(recover_font_key(raw, 16, 1024), self.ADOBE_KEY)

    def test_compressed_font_is_not_recovered(self):
        deflater = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
        packed = deflater.compress(build_sfnt() * 4) + deflater.flush()
        raw = self.obfuscate(packed, self.IDPF_KEY, 1040)
        self.assertIsNone(recover_font_key(raw, 20, 1040))

    def test_damaged_font_is_not_recovered(self):
        font = bytearray(build_sfnt())
        font[-10] ^= 1
        raw = self.obfuscate(bytes(font), self.IDPF_KEY, 1040)
        self.assertIsNone(recover_font_key(raw, 20, 1040))

    def test_decrypt_font_falls_back_to_recovered_key(self):
        font = build_sfnt()
        wrong_key = hashlib.sha1(b'urn:uuid:replaced').digest()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'Font.otf')
            with open(path, 'wb') as f:
                f.write(self.obfuscate(font, self.IDPF_KEY, 1040))
            out = io.StringIO()
            with redirect_stdout(out):
                decrypt_font(path, [(wrong_key, IDPF_OBFUSCATION)], d)
            with open(path, 'rb') as f:
                self.assertEqual(f.read(), font)
        self.assertIn('OK! Decrypted with the key recovered from the font.',
                      out.getvalue())

    def unlisted(self, font_data, uid='urn:uuid:original'):
        opftree = etree.fromstring(
            '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
            'unique-identifier="id"><metadata '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:identifier id="id">%s</dc:identifier></metadata><manifest>'
            '<item id="f" href="font/Font.ttf" media-type="font/ttf"/>'
            '</manifest></package>' % uid).getroottree()
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'font'))
            path = os.path.join(d, 'font', 'Font.ttf')
            with open(path, 'wb') as f:
                f.write(font_data)
            out = io.StringIO()
            with redirect_stdout(out):
                decrypt_unlisted_fonts(opftree, d, d)
            with open(path, 'rb') as f:
                return f.read(), out.getvalue()

    def test_unlisted_obfuscated_font_is_decrypted(self):
        font = build_sfnt()
        data, out = self.unlisted(self.obfuscate(font, self.IDPF_KEY, 1040))
        self.assertEqual(data, font)
        self.assertIn('not listed in encryption.xml', out)
        self.assertIn('OK! Decrypted.', out)

    def test_unlisted_adobe_font_with_other_key_is_decrypted(self):
        font = build_sfnt()
        data, out = self.unlisted(self.obfuscate(font, self.ADOBE_KEY, 1024))
        self.assertEqual(data, font)
        self.assertIn('recovered from the font', out)

    def test_unlisted_garbage_is_reported(self):
        garbage = bytes(range(7, 250)) * 9
        data, out = self.unlisted(garbage, uid='no-uuid')
        self.assertEqual(data, garbage)
        self.assertIn('FAILED! Substitute NOT found.', out)

    def test_plain_and_woff_fonts_are_left_alone(self):
        for font in (build_sfnt(), b'wOFF' + bytes(500)):
            data, out = self.unlisted(font)
            self.assertEqual(data, font)
            self.assertEqual(out, '')

    def test_decrypt_font_prefers_standard_key(self):
        font = build_sfnt()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'Font.otf')
            with open(path, 'wb') as f:
                f.write(self.obfuscate(font, self.IDPF_KEY, 1040))
            out = io.StringIO()
            with redirect_stdout(out):
                decrypt_font(path, [(self.IDPF_KEY, IDPF_OBFUSCATION)], d)
            with open(path, 'rb') as f:
                self.assertEqual(f.read(), font)
        self.assertIn('OK! Decrypted.', out.getvalue())
        self.assertNotIn('recovered', out.getvalue())


class FindFontByPostscriptNameTest(unittest.TestCase):

    def test_postscript_name(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'cambriai.ttf')
            with open(path, 'wb') as f:
                f.write(ttf_with_postscript_name('Cambria-Italic'))
            self.assertEqual(font_postscript_name(path), 'Cambria-Italic')
            self.assertEqual(find_font_by_postscript_name(
                'Cambria-Italic.ttf', d, False), path)
            self.assertIsNone(find_font_by_postscript_name(
                'Cambria-Bold.ttf', d, False))

    def test_not_a_font(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'broken.ttf')
            with open(path, 'wb') as f:
                f.write(b'\x00\x01\x00\x00\x00\x05')
            self.assertIsNone(font_postscript_name(path))


def ttc_with_postscript_names(*ps_names):
    """TTC collection of minimal fonts (see ttf_with_postscript_name)."""
    fonts = [ttf_with_postscript_name(n) for n in ps_names]
    offset = 12 + 4 * len(fonts)
    offsets = []
    data = b''
    for font in fonts:
        offsets.append(offset + len(data))
        name_offset = struct.unpack('>I', font[20:24])[0]
        data += (font[:20] + struct.pack('>I', offsets[-1] + name_offset) +
                 font[24:])
    return (b'ttcf' + struct.pack('>II', 0x10000, len(fonts)) +
            struct.pack('>%dI' % len(fonts), *offsets) + data)


class ConvertTtcFontsTest(unittest.TestCase):
    OPF = ('<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
           '<item id="f" href="font/Foo.ttc" media-type="font/collection"/>'
           '<item id="c" href="style.css" media-type="text/css"/>'
           '</manifest></package>')

    def test_convert(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'font'))
            with open(os.path.join(d, 'font', 'Foo.ttc'), 'wb') as f:
                f.write(ttc_with_postscript_names('Foo-Math', 'Foo'))
            with open(os.path.join(d, 'style.css'), 'w') as f:
                f.write('@font-face { src: url("font/Foo.ttc"); }')
            opftree = etree.ElementTree(etree.fromstring(self.OPF))
            convert_ttc_fonts(opftree, d)
            item = opftree.getroot()[0][0]
            self.assertEqual(item.get('href'), 'font/Foo.ttf')
            self.assertEqual(item.get('media-type'), 'application/font-sfnt')
            self.assertFalse(os.path.exists(os.path.join(d, 'font',
                                                         'Foo.ttc')))
            path = os.path.join(d, 'font', 'Foo.ttf')
            self.assertEqual(check_font(path)[0], True)
            self.assertEqual(font_postscript_name(path), 'Foo')
            with open(os.path.join(d, 'style.css')) as f:
                self.assertEqual(f.read(),
                                 '@font-face { src: url("font/Foo.ttf"); }')

class CreateHtmlCoverTest(unittest.TestCase):
    OPF = ('<package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
           '<metadata><meta name="cover" content="ci"/></metadata><manifest>'
           '<item id="ci" href="Images/c.jpg" media-type="image/jpeg"/>'
           '<item id="t1" href="Text/a.xhtml" '
           'media-type="application/xhtml+xml"/>'
           '<item id="t2" href="Text/b.xhtml" '
           'media-type="application/xhtml+xml"/>'
           '</manifest><spine><itemref idref="t1"/><itemref idref="t2"/>'
           '</spine>%s</package>')
    NS = {'opf': 'http://www.idpf.org/2007/opf',
          'x': 'http://www.w3.org/1999/xhtml'}

    def create(self, guide='', existing=()):
        opf = etree.fromstring(self.OPF % guide)
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'Text'))
            for name in existing:
                open(os.path.join(d, 'Text', name), 'w').close()
            with redirect_stdout(io.StringIO()):
                href = create_html_cover(opf, d, 'Images/c.jpg')
            page = etree.parse(os.path.join(d, *href.split('/')))
        return opf, href, page

    def test_cover_page_created(self):
        opf, href, page = self.create('<guide><reference type="toc" '
                                      'href="Text/a.xhtml"/></guide>')
        self.assertEqual(href, 'Text/cover.xhtml')
        self.assertEqual(page.xpath('//x:img/@src', namespaces=self.NS),
                         ['../Images/c.jpg'])
        item = opf.xpath('//opf:item[@href="Text/cover.xhtml"]',
                         namespaces=self.NS)[0]
        self.assertEqual(item.get('media-type'), 'application/xhtml+xml')
        self.assertEqual(
            opf.xpath('//opf:itemref/@idref', namespaces=self.NS),
            [item.get('id'), 't1', 't2'])
        self.assertEqual(opf.xpath('//opf:reference[@type="cover"]/@href',
                                   namespaces=self.NS), ['Text/cover.xhtml'])
        self.assertEqual(len(opf.xpath('//opf:guide', namespaces=self.NS)),
                         1)

    def test_guide_created(self):
        opf = self.create()[0]
        self.assertEqual(opf.xpath('//opf:guide/opf:reference/@href',
                                   namespaces=self.NS), ['Text/cover.xhtml'])

    def test_existing_file_not_overwritten(self):
        self.assertEqual(self.create(existing=['cover.xhtml'])[1],
                         'Text/cover2.xhtml')


class SplitExtraCoverImagesTest(unittest.TestCase):
    OPF = ('<package xmlns="http://www.idpf.org/2007/opf"><metadata>'
           '<meta name="cover" content="ci"/></metadata><manifest>'
           '<item id="ci" href="images/cover_image.jpg"/></manifest>'
           '</package>')

    def imgs(self, html):
        tree = etree.fromstring(XHTML % html)
        return tree, tree.xpath('//x:img', namespaces={
            'x': 'http://www.w3.org/1999/xhtml'})

    def test_extra_image_moved(self):
        tree, imgs = self.imgs(
            '<div><div class="img"><img src="images/cover_image.jpg"/></div>'
            '<div class="img"><img src="images/cover.jpg"/></div></div>')
        docs = split_extra_cover_images(imgs, etree.fromstring(self.OPF))
        self.assertEqual([i.get('src') for i in imgs],
                         ['images/cover_image.jpg'])
        self.assertNotIn(b'cover.jpg', etree.tostring(tree))
        self.assertEqual(len(docs), 1)
        body = docs[0].find('{http://www.w3.org/1999/xhtml}body')
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0].get('class'), 'img')
        self.assertEqual(body[0][0].get('src'), 'images/cover.jpg')

    def test_meta_cover_not_in_html(self):
        tree, imgs = self.imgs('<img src="a.jpg"/><img src="b.jpg"/>')
        self.assertIsNone(split_extra_cover_images(
            imgs, etree.fromstring(self.OPF)))
        self.assertEqual(len(imgs), 2)


class RemoveOrphanRefiningMetasTest(unittest.TestCase):
    def test_removes_only_orphans(self):
        opf = etree.fromstring(
            '<package xmlns="http://www.idpf.org/2007/opf" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" version="3.0">'
            '<metadata><dc:creator id="c">A</dc:creator>'
            '<dc:identifier id="i">978</dc:identifier>'
            '<meta property="identifier-type">22</meta>'
            '<meta property="role">bkd</meta>'
            '<meta property="role" refines="#i">aut</meta>'
            '<meta property="role" refines="#x">aut</meta>'
            '<meta property="role" refines="#c">aut</meta>'
            '<meta property="identifier-type" refines="#i">15</meta>'
            '<meta property="file-as">B</meta>'
            '</metadata></package>')
        remove_orphan_refining_metas(opf)
        metas = opf.findall('.//{http://www.idpf.org/2007/opf}meta')
        self.assertEqual([(m.get('property'), m.get('refines'))
                          for m in metas],
                         [('role', '#c'), ('identifier-type', '#i'),
                          ('file-as', None)])

    def test_restores_contributor(self):
        opf = etree.fromstring(
            '<package xmlns="http://www.idpf.org/2007/opf" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" version="3.0">'
            '<metadata><dc:creator id="contrib1">A</dc:creator>'
            '<meta property="identifier-type">22</meta>'
            '<meta property="file-as">Kowalski, Jan</meta>'
            '<meta property="role">bkd</meta>'
            '</metadata></package>')
        remove_orphan_refining_metas(opf)
        self.assertEqual(
            [(etree.QName(e).localname, e.get('id'), e.get('property'),
              e.get('refines'), e.get('scheme'), e.text)
             for e in opf[0]],
            [('creator', 'contrib1', None, None, None, 'A'),
             ('contributor', 'contrib2', None, None, None, 'Jan Kowalski'),
             ('meta', None, 'file-as', '#contrib2', None, 'Kowalski, Jan'),
             ('meta', None, 'role', '#contrib2', 'marc:relators', 'bkd')])


class MoveMetadataNamespacesTest(unittest.TestCase):
    def run_move(self, opf):
        tree = etree.fromstring(opf)
        with redirect_stdout(io.StringIO()):
            move_metadata_namespaces(tree)
        return etree.tostring(tree).decode()

    def test_sigil_declarations(self):
        out = self.run_move(
            '<package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
            '<metadata>'
            '<dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">T</dc:title>'
            '<dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:opf="http://www.idpf.org/2007/opf" opf:role="aut">A'
            '</dc:creator>'
            '<dc:language xmlns:dc="http://purl.org/dc/elements/1.1/">pl'
            '</dc:language><meta name="cover" content="c"/>'
            '</metadata><manifest/></package>')
        self.assertEqual(out.count('xmlns:dc='), 1)
        self.assertEqual(out.count('xmlns:opf='), 1)
        self.assertIn('<metadata xmlns:dc=', out)
        self.assertIn('<dc:language>pl</dc:language>', out)
        self.assertIn('<dc:creator opf:role="aut">A</dc:creator>', out)

    def test_declared_on_package(self):
        out = self.run_move(
            '<package xmlns="http://www.idpf.org/2007/opf" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">'
            '<metadata><dc:title>T</dc:title>'
            '<dc:language xmlns:dc="http://purl.org/dc/elements/1.1/">pl'
            '</dc:language></metadata></package>')
        self.assertEqual(out.count('xmlns:dc='), 1)
        self.assertIn('<metadata><dc:title>T</dc:title>'
                      '<dc:language>pl</dc:language>', out)

    def test_other_namespaces_kept(self):
        opf = ('<package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
               '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" '
               'xmlns:opf="http://www.idpf.org/2007/opf" '
               'xmlns:dcterms="http://purl.org/dc/terms/" '
               'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
               '<dc:date xsi:type="dcterms:W3CDTF">2020</dc:date>'
               '</metadata></package>')
        self.assertEqual(self.run_move(opf),
                         etree.tostring(etree.fromstring(opf)).decode())


class WolneLekturyFundraisingTest(unittest.TestCase):
    OPF = ('<package xmlns="http://www.idpf.org/2007/opf"><metadata '
           'xmlns:dc="http://purl.org/dc/elements/1.1/">%s</metadata>'
           '</package>')
    PAGE = ('<html xmlns="http://www.w3.org/1999/xhtml"><body>'
            '<div id="book-text">%s</div></body></html>')

    def test_is_wolnelektury_book(self):
        for meta, expected in (
            ('<dc:publisher>Fundacja Wolne Lektury</dc:publisher>', True),
            ('<dc:identifier>https://wolnelektury.pl/katalog/lektura/x/'
             '</dc:identifier>', True),
            ('<dc:publisher>Other</dc:publisher>', False),
        ):
            with self.subTest(meta):
                tree = etree.fromstring(self.OPF % meta).getroottree()
                self.assertEqual(is_wolnelektury_book(tree), expected)

    def test_is_fundraising_page(self):
        for content, expected in (
            ('<div class="fundraising"><div><p>Wesprzyj <a href="x">nas</a>'
             '</p></div></div>', True),
            ('<div class="fundraising"><p>Wesprzyj</p></div><p>Text</p>',
             False),
            ('<p>Text</p>', False),
        ):
            with self.subTest(content):
                tree = etree.fromstring(self.PAGE % content).getroottree()
                self.assertEqual(is_fundraising_page(tree), expected)

    def test_is_support_page(self):
        for content, expected in (
            ('<p><img src="jedenprocent.png" alt="Logo 1%"/></p>', True),
            ('<p><img src="../img/jedenprocent.png"/></p>', True),
            ('<h2>Wesprzyj Wolne Lektury!</h2><img src="logo.png"/>',
             False),
        ):
            with self.subTest(content):
                tree = etree.fromstring(self.PAGE % content).getroottree()
                self.assertEqual(is_support_page(tree), expected)

    def test_resolve_href(self):
        self.assertEqual(resolve_href('text/nav.xhtml', '../a%20b.xhtml#x'),
                         'a b.xhtml')
        self.assertEqual(resolve_href('nav.xhtml', 'support.xhtml'),
                         'support.xhtml')
        # a TOC outside the OPF directory: with the OPF directory the
        # path gets the manifest form, independent of the current directory
        self.assertEqual(resolve_href('../Misc/toc.ncx', '../OEBPS/a.xhtml',
                                      '/book/OEBPS'), 'a.xhtml')
        self.assertEqual(resolve_href('../nav.xhtml', 'OEBPS/a.xhtml#x',
                                      'book/OEBPS'), 'a.xhtml')
        self.assertEqual(resolve_href('../nav.xhtml', 'Other/a.xhtml',
                                      'book/OEBPS'), '../Other/a.xhtml')


class PurchaseInfoPageTest(unittest.TestCase):
    PAGE = ('<html xmlns="http://www.w3.org/1999/xhtml"><head><title>wm'
            '</title></head><body>%s</body></html>')
    TABLE = ('<table><tr><td>zakupiono w sklepie:</td><td>Sklep</td></tr>'
             '<tr><td>identyfikator transakcji:</td><td>1628971198459280'
             '</td></tr><tr><td>e-mail nabywcy:</td><td>a@b.pl</td></tr>'
             '<tr><td>znak wodny:</td><td><img alt="X" '
             'src="../Images/logo.png" /></td></tr></table>')
    OPF = ('<package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
           '<metadata><meta name="cover" content="cover-image"/></metadata>'
           '<manifest>'
           '<item id="ncx" href="toc.ncx" '
           'media-type="application/x-dtbncx+xml"/>'
           '<item id="cover-image" href="Images/cover.jpg" '
           'media-type="image/jpeg"/>'
           '<item id="logo" href="Images/logo.png" media-type="image/png"/>'
           '<item id="pic" href="Images/pic.jpg" media-type="image/jpeg"/>'
           '<item id="wm" href="Text/wm.xhtml" '
           'media-type="application/xhtml+xml"/>'
           '<item id="ch" href="Text/ch.xhtml" '
           'media-type="application/xhtml+xml"/>'
           '</manifest><spine toc="ncx"><itemref idref="wm"/>'
           '<itemref idref="ch"/></spine><guide><reference type="other" '
           'title="Info" href="Text/wm.xhtml"/></guide></package>')
    NCX = ('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" '
           'version="2005-1"><navMap>'
           '<navPoint id="a"><navLabel><text>Info</text></navLabel>'
           '<content src="Text/wm.xhtml"/></navPoint>'
           '<navPoint id="b"><navLabel><text>Ch</text></navLabel>'
           '<content src="Text/ch.xhtml"/></navPoint></navMap></ncx>')

    def test_is_purchase_info_page(self):
        for content, expected in (
            (self.TABLE, True),
            ('<p>Text</p>' + self.TABLE, False),
            (self.TABLE.replace('znak wodny:', 'logo:'), False),
            ('<h1>Znak wodny</h1><p>identyfikator transakcji:</p>', False),
        ):
            with self.subTest(content):
                tree = etree.fromstring(self.PAGE % content).getroottree()
                self.assertEqual(is_purchase_info_page(tree), expected)

    def test_page_removed_with_its_image(self):
        # the cover is shown on the page too, pic.jpg is used elsewhere,
        # "logo.png" in an alt text is not a reference
        page = self.PAGE % (self.TABLE.replace(
            '</table>', '<tr><td><img src="../Images/cover.jpg"/>'
            '<img src="../Images/pic.jpg"/></td></tr></table>'))
        chapter = self.PAGE % ('<p><img src="../Images/pic.jpg" '
                               'alt="logo.png"/></p>')
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'Text'))
            os.makedirs(os.path.join(d, 'Images'))
            for name, text in (('Text/wm.xhtml', page),
                               ('Text/ch.xhtml', chapter),
                               ('toc.ncx', self.NCX),
                               ('Images/cover.jpg', ''),
                               ('Images/logo.png', ''),
                               ('Images/pic.jpg', '')):
                with open(os.path.join(d, name), 'w') as f:
                    f.write(text)
            opftree = etree.fromstring(self.OPF).getroottree()
            out = io.StringIO()
            with redirect_stdout(out):
                remove_purchase_info_pages(opftree, d)
            files = sorted(os.listdir(os.path.join(d, 'Text')) +
                           os.listdir(os.path.join(d, 'Images')))
            with open(os.path.join(d, 'toc.ncx')) as f:
                ncx = f.read()
        self.assertEqual(files, ['ch.xhtml', 'cover.jpg', 'pic.jpg'])
        opf = etree.tostring(opftree, encoding='unicode')
        self.assertNotIn('wm.xhtml', opf)
        self.assertNotIn('logo.png', opf)
        self.assertIn('cover.jpg', opf)
        self.assertNotIn('wm.xhtml', ncx)
        self.assertIn('ch.xhtml', ncx)
        self.assertEqual(out.getvalue(), '* Needless info page removed: '
                         'Text/wm.xhtml (with Images/logo.png)\n')


class InsertPageMarkersTest(unittest.TestCase):
    BODY = '<html><head><title>T</title></head><body>%s</body></html>'

    def test_short_paragraphs(self):
        # 29 one-line paragraphs fill a page, the 30th starts page 2
        raw = self.BODY % ''.join('<p>Line %d</p>' % i for i in range(31))
        new, pages = insert_page_markers(raw, 1)
        self.assertEqual(pages, [2])
        self.assertIn('<p><span id="eqt_page_2"></span>Line 29</p>', new)

    def test_long_paragraph(self):
        # the marker goes before the first word of the 30th line,
        # soft hyphens are not counted
        word = 'abc\u00addefg'
        raw = self.BODY % ('<p>%s</p>' % ' '.join([word] * 300))
        new, pages = insert_page_markers(raw, 0)
        self.assertEqual(pages, [1])
        before = new[:new.index('<span')]
        # line 30 starts at char 29 * 68 = 1972, inside the 247th word
        self.assertEqual(before.count(word), 247)
        self.assertTrue(before.endswith(' '))

    def test_head_and_style_skipped(self):
        raw = ('<html><head><title>%s</title></head><body><style>%s</style>'
               '<p>Text</p></body></html>' % ('x ' * 3000, 'y ' * 3000))
        self.assertEqual(insert_page_markers(raw, 0), (raw, []))

    def test_style_inside_svg(self):
        # </style> inside <svg> doesn't end skipping the SVG
        raw = self.BODY % ('<svg><style>a {}</style><text>%s</text></svg>'
                           '<p>Text</p>' % ('x ' * 3000))
        self.assertEqual(insert_page_markers(raw, 0), (raw, []))

    def test_gt_in_attribute(self):
        raw = self.BODY % ('<p title="a > b">%s</p>' % ('y ' * 3000))
        new, pages = insert_page_markers(raw, 0)
        self.assertIn('<p title="a > b">y', new)
        self.assertNotIn('<span', new[:new.index('>y')])

    def test_no_marker_in_nav(self):
        # empty spans are invalid in nav, the marker waits until after it
        raw = self.BODY % ('<nav><ol>%s</ol></nav><p>After</p>' %
                           ''.join('<li><a href="a.xhtml">Item %d</a></li>'
                                   % i for i in range(31)))
        new, pages = insert_page_markers(raw, 0)
        self.assertEqual(pages, [1])
        self.assertIn('</nav><p><span id="eqt_page_1"></span>After</p>', new)


class AddPageListTest(unittest.TestCase):
    OPF = ('<package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
           '<manifest>'
           '<item id="ncx" href="toc.ncx" '
           'media-type="application/x-dtbncx+xml"/>'
           '<item id="c1" href="Text/rozdzia%C5%82.xhtml" '
           'media-type="application/xhtml+xml"/>'
           '</manifest><spine toc="ncx"><itemref idref="c1"/></spine>'
           '</package>')
    NCX = ('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           '<head/><docTitle><text>T</text></docTitle><navMap>'
           '<navPoint id="n1" playOrder="1"><navLabel><text>1</text>'
           '</navLabel><content src="Text/rozdzia%C5%82.xhtml"/></navPoint>'
           '<navPoint id="n2" playOrder="2"><navLabel><text>2</text>'
           '</navLabel><content src="Text/rozdzia%C5%82.xhtml#s2"/>'
           '</navPoint></navMap></ncx>')
    BODY = ('<html xmlns="http://www.w3.org/1999/xhtml"><head><title>T'
            '</title></head><body>%s</body></html>')

    def run_add(self, body, name='rozdział.xhtml'):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'Text'))
            with open(os.path.join(d, 'toc.ncx'), 'w') as f:
                f.write(self.NCX)
            with open(os.path.join(d, 'Text', name), 'w',
                      encoding='utf-8') as f:
                f.write(self.BODY % body)
            opftree = etree.ElementTree(etree.fromstring(
                self.OPF.replace('rozdzia%C5%82.xhtml', quote(name))))
            add_page_list(opftree, d)
            with open(os.path.join(d, 'toc.ncx'), encoding='utf-8') as f:
                return f.read()

    def test_encoded_href(self):
        # the second chapter starts on page 2 (after 40 lines)
        ncx = self.run_add(
            '<p data-id="s2">Start</p>' + '<p>Line</p>' * 40 +
            '<h1 id=\'s2\'>Two</h1>' + '<p>Line</p>' * 10)
        self.assertIn('<content src="Text/rozdzia%C5%82.xhtml"/>', ncx)
        self.assertIn('src="Text/rozdzia%C5%82.xhtml#eqt_page_2"', ncx)
        ncxtree = etree.fromstring(ncx.encode('utf-8'))
        orders = {e.get('id'): e.get('playOrder') for e in
                  ncxtree.iter('{*}navPoint', '{*}pageTarget')}
        self.assertEqual(orders, {'n1': '1', 'pageTarget-1': '1',
                                  'pageTarget-2': '2', 'n2': '3'})

    def test_nav_page_list_hidden_with_css(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'Text'))
            with open(os.path.join(d, 'toc.ncx'), 'w') as f:
                f.write(self.NCX)
            with open(os.path.join(d, 'Text', 'c1.xhtml'), 'w') as f:
                f.write(self.BODY % ('<p>Line</p>' * 40))
            with open(os.path.join(d, 'Text', 'nav.xhtml'), 'w') as f:
                f.write(self.BODY % '<nav><ol><li><a href="c1.xhtml">1'
                        '</a></li></ol></nav>')
            opftree = etree.ElementTree(etree.fromstring(
                self.OPF.replace('rozdzia%C5%82.xhtml', 'c1.xhtml').replace(
                    '</manifest>', '<item id="nav" href="Text/nav.xhtml" '
                    'media-type="application/xhtml+xml" properties="nav"/>'
                    '</manifest>')))
            add_page_list(opftree, d)
            with open(os.path.join(d, 'Text', 'nav.xhtml')) as f:
                nav = f.read()
        self.assertRegex(nav, r'<nav [^>]*hidden="hidden"[^>]*'
                         r'style="display:none"[^>]*:type="page-list"')

    def test_toc_outside_opf_dir(self):
        # NCX and nav outside the OPF directory (../Misc/toc.ncx,
        # ../nav.xhtml): the links don't depend on the current directory
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d, \
                tempfile.TemporaryDirectory() as other:
            root = os.path.join(d, 'OEBPS')
            for sub in ('OEBPS', 'Misc'):
                os.mkdir(os.path.join(d, sub))
            with open(os.path.join(d, 'Misc', 'toc.ncx'), 'w') as f:
                f.write(self.NCX.replace('src="Text/rozdzia%C5%82.xhtml',
                                         'src="../OEBPS/c1.xhtml'))
            with open(os.path.join(root, 'c1.xhtml'), 'w') as f:
                f.write(self.BODY % ('<p>Line</p>' * 40))
            with open(os.path.join(d, 'nav.xhtml'), 'w') as f:
                f.write(self.BODY % '<nav><ol><li><a href="OEBPS/c1.xhtml">'
                        '1</a></li></ol></nav>')
            opftree = etree.ElementTree(etree.fromstring(
                self.OPF.replace('href="toc.ncx"', 'href="../Misc/toc.ncx"')
                .replace('Text/rozdzia%C5%82.xhtml', 'c1.xhtml').replace(
                    '</manifest>', '<item id="nav" href="../nav.xhtml" '
                    'media-type="application/xhtml+xml" properties="nav"/>'
                    '</manifest>')))
            os.chdir(other)
            try:
                add_page_list(opftree, root)
            finally:
                os.chdir(cwd)
            with open(os.path.join(d, 'Misc', 'toc.ncx')) as f:
                ncx = f.read()
            with open(os.path.join(d, 'nav.xhtml')) as f:
                nav = f.read()
        self.assertIn('pageList', ncx)
        srcs = re.findall(r'<pageTarget\b.*?<content src="([^"]*)"', ncx,
                          re.S)
        self.assertTrue(srcs)
        for src in srcs:
            self.assertRegex(src, r'^\.\./OEBPS/c1\.xhtml(#eqt_page_\d+)?$')
        self.assertRegex(nav, r'(?s)page-list.*<a href="OEBPS/c1\.xhtml">1'
                         r'</a>')
        # the navPoints and pageTargets of the same place share playOrder
        ncxtree = etree.fromstring(ncx.encode('utf-8'))
        orders = {e.get('id'): e.get('playOrder') for e in
                  ncxtree.iter('{*}navPoint', '{*}pageTarget')}
        self.assertEqual(orders['n1'], orders['pageTarget-1'])

    def test_existing_page_list(self):
        ncx = self.run_add("<span epub:type='pagebreak' id='p1'/>" +
                           '<p>Line</p>' * 40, 'c1.xhtml')
        self.assertNotIn('pageList', ncx)
