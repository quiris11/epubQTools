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

from lxml import etree

from lib.epubqfix import (ClassStyles, check_font, convert_ttc_fonts,
                          decode_b64_name, find_file_in_dir,
                          find_font_by_postscript_name, font_postscript_name,
                          split_extra_cover_images,
                          image_data_end, is_hiding_style,
                          most_common, remove_thin_spaces_after_spaces,
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
