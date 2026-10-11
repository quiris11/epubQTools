# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
import struct
import unittest
import zlib

from lxml import etree

from lib.epubqfix import (decode_b64_name, image_data_end, is_hiding_style,
                          most_common, remove_trailing_hidden_div)

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

    def remove(self, last, hiding_classes=frozenset()):
        tree = etree.fromstring(XHTML % last)
        hidden_divs = {}
        hidden_classes = set()
        remove_trailing_hidden_div(tree, hidden_divs, hidden_classes,
                                   hiding_classes)
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
        self.assertEqual(
            self.remove('<p class="x hide">%s</p>' % NAME, {'hide'}),
            (True, {NAME: 1}, {'x', 'hide'}))
        self.assertEqual(
            self.remove('<p class="x">%s</p>' % NAME, {'hide'}),
            (False, {}, set()))
        self.assertEqual(
            self.remove('<p class="hide">Short</p>', {'hide'}),
            (False, {}, set()))

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
