# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
import os
import struct
import tempfile
import unittest
import zlib

from urllib.parse import quote

from lxml import etree

from lib.epubqcheck import best_cover_image_item
from lib.epubqfix import (ClassStyles, add_page_list, check_font, convert_ttc_fonts,
                          convert_note_aside_css, convert_note_asides,
                          convert_note_asides_in_tree,
                          fill_empty_titles,
                          decode_b64_name, find_file_in_dir,
                          find_font_by_postscript_name, font_postscript_name,
                          fix_links_in_tree, remove_empty_toc_entries,
                          split_extra_cover_images,
                          image_data_end, insert_page_markers,
                          is_fundraising_page,
                          is_hiding_style, is_support_page,
                          is_wolnelektury_book, most_common, resolve_href, remove_orphan_refining_metas,
                          remove_thin_spaces_after_spaces,
                          remove_url_line_breaks,
                          remove_trailing_hidden_div, strip_nav_aria_labels)

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
        self.assertEqual(n, 3)
        self.assertNotIn('<aside id="n', html)
        # the single paragraph is replaced with the list item
        self.assertIn('<li id="n1" epub:type="rearnote"><span>1</span> One '
                      '<a href="a.xhtml#r1">\u21a9</a></li>', html)
        self.assertIn('<li id="n2"><p>Two</p><p>Second paragraph</p></li>',
                      html)
        self.assertIn('<li id="n3" class="x">Three</li>', html)
        # not a note
        self.assertIn('<aside id="side">Sidebar</aside>', html)

    def test_id_of_paragraph_kept(self):
        n, html = self.convert(
            '<aside epub:type="footnote"><p id="fn1">One</p></aside>'
            '<aside id="n2"><p id="fn2">Two</p></aside>', set())
        self.assertEqual(n, 1)
        self.assertIn('<li epub:type="footnote" id="fn1">One</li>', html)
        # both ids kept, so the paragraph stays
        n, html = self.convert(
            '<aside id="n2"><p id="fn2">Two</p></aside>', {'n2'})
        self.assertIn('<li id="n2"><p id="fn2">Two</p></li>', html)

    def test_consecutive_notes_in_one_list(self):
        n, html = self.convert(self.NOTES, {'n2', 'n3'})
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


class ConvertNoteAsideCssTest(unittest.TestCase):
    CSS = ('/* notes */\naside[id^="endnote-"] {\n    margin: 1.2em 0;\n'
           '    line-height: 1.6;}\n\n'
           'aside[id^="endnote-"] p {\n    text-indent: 0;\n    margin: 0;\n'
           '    padding: 0;\n    font-size: 0.95em;\n'
           '    font-family: "CustomSerif", serif;}\n\n'
           'p, .aside {\n    margin: 0;}\n')

    def test_note_selectors_added(self):
        css, n = convert_note_aside_css(self.CSS)
        self.assertEqual(n, 2)
        self.assertIn('/* notes */\naside[id^="endnote-"], '
                      'ol.eqt_notes > li[id^="endnote-"] {\n    margin: 1.2em 0;',
                      css)
        self.assertIn('aside[id^="endnote-"] p, '
                      'ol.eqt_notes > li[id^="endnote-"] p {', css)
        # text properties of the unwrapped <p> go to the list item
        self.assertIn('\n\nol.eqt_notes > li[id^="endnote-"] {\n'
                      '    text-indent: 0;\n    font-size: 0.95em;\n'
                      '    font-family: "CustomSerif", serif;}', css)
        self.assertIn('p, .aside {\n    margin: 0;}', css)

    def test_selectors_after_paragraph(self):
        css, n = convert_note_aside_css(
            'section > aside.note p span, aside p.x, nav a {color: red}')
        self.assertEqual(n, 1)
        self.assertEqual(
            css, 'section > aside.note p span, aside p.x, nav a, '
            'section > ol.eqt_notes > li.note p span, '
            'section > ol.eqt_notes > li.note span, '
            'ol.eqt_notes > li p.x {color: red}')


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

    def test_existing_page_list(self):
        ncx = self.run_add("<span epub:type='pagebreak' id='p1'/>" +
                           '<p>Line</p>' * 40, 'c1.xhtml')
        self.assertNotIn('pageList', ncx)
