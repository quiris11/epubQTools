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
import zipfile
from contextlib import redirect_stdout

from lib.epubqcheck import qcheck

POLISH_TEXT = ('Zażółć gęślą jaźń, a potem źdźbło trawy ugięło się pod '
               'ciężarem rosy. ' * 20)
ENGLISH_TEXT = ('The quick brown fox jumps over the lazy dog and then '
                'runs away into the forest. ' * 20)

OPF = '''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0"
         unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Book</dc:title><dc:creator>Author</dc:creator>
    <dc:identifier id="id">x</dc:identifier>%(lang)s
  </metadata>
  <manifest>%(items)s</manifest>
  <spine toc="ncx">%(spine)s</spine>
  <guide/>
</package>'''

XHTML = '''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head>
<body>%s</body></html>'''


def opf(items, spine, lang='<dc:language>en</dc:language>'):
    return OPF % {
        'lang': lang,
        'items': ''.join(
            '<item id="%s" href="%s" media-type="%s"/>' % i for i in items),
        'spine': ''.join('<itemref idref="%s"/>' % i for i in spine)}


class QcheckTestCase(unittest.TestCase):
    """A small book b.epub checked by qcheck."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def check(self, lang, text, titles=None):
        with zipfile.ZipFile(os.path.join(self.dir, 'b.epub'), 'w') as z:
            z.writestr('mimetype', 'application/epub+zip')
            z.writestr('META-INF/container.xml', (
                '<?xml version="1.0"?><container version="1.0" xmlns="urn:'
                'oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                '<rootfile full-path="OEBPS/content.opf" media-type='
                '"application/oebps-package+xml"/></rootfiles></container>'))
            content = opf(
                [('c1', '../text/c1.xhtml', 'application/xhtml+xml')],
                ['c1'], lang)
            if titles is not None:
                content = content.replace('<dc:title>Book</dc:title>',
                                          titles)
            z.writestr('OEBPS/content.opf', content)
            z.writestr('text/c1.xhtml', XHTML % ('<p>%s</p>' % text))
        out = io.StringIO()
        with redirect_stdout(out):
            qcheck(self.dir, 'b.epub', True, False, False)
        return [x for x in out.getvalue().splitlines()
                if 'language' in x or 'dc:title' in x]


class QcheckLanguageTest(QcheckTestCase):

    def test_other_language_is_not_a_problem(self):
        for lang in ('en', 'de-DE', 'tr'):
            self.assertEqual(self.check(
                '<dc:language>%s</dc:language>' % lang, ENGLISH_TEXT), [])

    def test_polish(self):
        for lang in ('pl', 'pl-PL', 'pol'):
            self.assertEqual(self.check(
                '<dc:language>%s</dc:language>' % lang, POLISH_TEXT), [])

    def test_polish_text_with_other_language(self):
        self.assertEqual(
            self.check('<dc:language>en</dc:language>', POLISH_TEXT),
            ['b.epub: dc:language is "en", but the text looks Polish'])

    def test_no_language(self):
        for lang in ('', '<dc:language>und</dc:language>',
                     '<dc:language> </dc:language>'):
            self.assertEqual(self.check(lang, ENGLISH_TEXT),
                             ['b.epub: No dc:language defined'])


class QcheckTitlesTest(QcheckTestCase):

    def titles(self, titles):
        return self.check('<dc:language>en</dc:language>', ENGLISH_TEXT,
                          titles)

    def test_main_title_first(self):
        # EPUB 3 subtitle (e.g. books of d2d.pl)
        self.assertEqual(self.titles(
            '<dc:title id="t">Wyznawcy władzy</dc:title>'
            '<meta refines="#t" property="title-type">main</meta>'
            '<dc:title id="s">Religijny fundamentalizm</dc:title>'
            '<meta refines="#s" property="title-type">subtitle</meta>'), [])

    def test_subtitle_first(self):
        self.assertEqual(self.titles(
            '<dc:title id="s">Religijny fundamentalizm</dc:title>'
            '<meta refines="#s" property="title-type">subtitle</meta>'
            '<dc:title id="t">Wyznawcy władzy</dc:title>'
            '<meta refines="#t" property="title-type">main</meta>'),
            ['b.epub: Warning! Multiple dc:title (book title) elements '
             'defined in OPF file and the first one is not the main title '
             '(title-type "main")...'])

    def test_titles_not_marked(self):
        self.assertEqual(self.titles(
            '<dc:title>Wyznawcy władzy</dc:title>'
            '<dc:title>Religijny fundamentalizm</dc:title>'),
            ['b.epub: Warning! Multiple dc:title (book title) elements '
             'defined in OPF file and none is marked as the main title '
             '(title-type "main")...'])

    def test_one_title(self):
        self.assertEqual(self.titles('<dc:title>Book</dc:title>'), [])


if __name__ == '__main__':
    unittest.main()
