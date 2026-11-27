# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
import io
import json
import os
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest import mock

from lxml import etree

from lib import hyphenation
from lib.epubqfix import (hyphenate_and_fix_conjunctions, qfix, HYPHEN_MARK,
                          fix_various_opf_problems)
from lib.hyphenation import (dictionary_name, hyphenator_for, language_parts,
                             looks_polish, primary_language, WORD_RE)

LOCALES = {'de': 'hyph_de_DE.dic', 'de_AT': 'hyph_de_AT.dic',
           'en_AU': 'hyph_en_GB.dic', 'en_GB': 'hyph_en_GB.dic',
           'en_US': 'hyph_en_US.dic', 'pl_PL': 'hyph_pl_PL.dic',
           'pt_BR': 'hyph_pt_BR.dic', 'pt_PT': 'hyph_pt_PT.dic',
           'sr_CS': 'hyph_sr.dic', 'sr_Latn_RS': 'hyph_sr-Latn.dic',
           'sr_RS': 'hyph_sr.dic', 'sv_SE': 'hyph_sv.dic'}
POLISH_TEXT = ('Zażółć gęślą jaźń. Pchnąć w tę łódź jeża lub ośm skrzyń '
               'fig. Ślązaczka łże, że ćma ździebko się spóźniła. ') * 10
ENGLISH_TEXT = ('The quick brown fox jumps over a lazy dog and then '
                'goes back to the forest to sleep. ') * 10
# a dictionary: a hyphen before "na" ("ba-na-na")
DIC = b'UTF-8\nLEFTHYPHENMIN 2\nRIGHTHYPHENMIN %d\n1na\n'


def make_calibre_dir(dics, locales):
    """A folder like calibre's resources/hyphenation."""
    d = tempfile.mkdtemp(prefix='eqt-test-')
    with open(os.path.join(d, 'locales.json'), 'w') as f:
        json.dump(locales, f)
    with tarfile.open(os.path.join(d, 'dictionaries.tar.xz'), 'w:xz') as tf:
        for name, data in dics.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return d


class LanguageCodesTest(unittest.TestCase):

    def test_parts(self):
        self.assertEqual(language_parts('sr-Latn-RS'), ('sr', 'Latn', 'RS'))
        self.assertEqual(language_parts(' EN_gb '), ('en', None, 'GB'))
        self.assertEqual(language_parts('es-419'), ('es', None, '419'))
        self.assertEqual(language_parts('de-1996'), ('de', None, None))
        self.assertEqual(language_parts(None), ('', None, None))

    def test_primary_language(self):
        for code in ('pl', 'PL', 'pl-PL', 'pl_pl', 'pol', ' pl '):
            self.assertEqual(primary_language(code), 'pl', code)
        self.assertEqual(primary_language('ger'), 'de')
        self.assertEqual(primary_language('fr'), 'fr')

    def test_dictionary_name(self):
        for code, name in (('en', 'hyph_en_US.dic'),
                           ('eng', 'hyph_en_US.dic'),
                           ('en-GB', 'hyph_en_GB.dic'),
                           ('en-AU', 'hyph_en_GB.dic'),
                           ('en-XX', 'hyph_en_US.dic'),
                           ('de', 'hyph_de_DE.dic'),
                           ('de-AT', 'hyph_de_AT.dic'),
                           ('pt', 'hyph_pt_PT.dic'),
                           ('pt-br', 'hyph_pt_BR.dic'),
                           ('sr', 'hyph_sr.dic'),
                           ('sr-Latn', 'hyph_sr-Latn.dic'),
                           ('sv', 'hyph_sv.dic'),
                           ('fr', None), ('und', None), ('', None)):
            self.assertEqual(dictionary_name(LOCALES, code), name, code)

    def test_words_with_combining_marks(self):
        self.assertEqual(WORD_RE.findall('मराठी भाषा'),
                         ['मराठी', ' ', 'भाषा'])
        self.assertEqual(WORD_RE.findall('a, b'), ['a', ',', ' ', 'b'])


class LooksPolishTest(unittest.TestCase):

    def test_polish(self):
        self.assertTrue(looks_polish([POLISH_TEXT]))

    def test_english_with_polish_names(self):
        self.assertFalse(looks_polish([ENGLISH_TEXT, 'Łódź, Wałęsa']))

    def test_too_short(self):
        self.assertFalse(looks_polish(['Zażółć gęślą jaźń']))


class CalibreDictionariesTest(unittest.TestCase):

    def setUp(self):
        hyphenation._cache.clear()
        self.addCleanup(hyphenation._cache.clear)
        self.dir = make_calibre_dir(
            {'hyph_en_US.dic': DIC % 3, 'hyph_en_GB.dic': DIC % 1},
            {'en_US': 'hyph_en_US.dic', 'en_GB': 'hyph_en_GB.dic',
             'de_DE': 'hyph_de_DE.dic'})
        self.addCleanup(shutil.rmtree, self.dir)
        patcher = mock.patch.object(hyphenation, 'find_calibre_hyphenation',
                                    return_value=self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dictionary_with_shortest_parts(self):
        h, name = hyphenator_for('en')
        self.assertEqual(name, 'hyph_en_US.dic')
        self.assertEqual(h.inserted('banana', '-'), 'ba-nana')  # right 3
        h, name = hyphenator_for('en-GB')
        self.assertEqual(h.inserted('banana', '-'), 'ba-na-na')  # right 1

    def test_no_dictionary(self):
        self.assertEqual(hyphenator_for('fr'),
                         (None, 'no dictionary in calibre'))

    def test_dictionary_missing_in_archive(self):
        h, reason = hyphenator_for('de')
        self.assertIsNone(h)
        self.assertIn('cannot read hyph_de_DE.dic', reason)

    def test_polish_without_calibre(self):
        with mock.patch.object(hyphenation, 'find_calibre_hyphenation',
                               return_value=None):
            h, name = hyphenator_for('pl-PL')
            self.assertEqual(name, 'hyph_pl_PL.dic')
            self.assertEqual(h.inserted('kolorowa', '-'), 'ko-lo-ro-wa')
            self.assertEqual(hyphenator_for('en'),
                             (None, 'calibre not found'))

    def test_no_language(self):
        self.assertEqual(hyphenator_for('und'), (None, 'no language'))

    def test_calibre_dirs(self):
        dirs = hyphenation.calibre_dirs()
        self.assertTrue(all(d.endswith('hyphenation') for d in dirs))
        self.assertIn(os.path.join('/opt/calibre/resources', 'hyphenation'),
                      dirs)


XHTML = ('<?xml version="1.0" encoding="utf-8"?>'
         '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>T</title>'
         '</head><body>%s</body></html>')


class HyphenateBookLanguageTest(unittest.TestCase):

    def run_hyph(self, body, lang, hyph, skip=False):
        tree = etree.fromstring((XHTML % body).encode())
        tree = hyphenate_and_fix_conjunctions(tree, '-', hyph, False, skip,
                                              lang)
        return etree.tostring(tree, encoding='unicode')

    def test_english(self):
        h = hyphenation.hyphenator_from_bytes(DIC % 1)
        out = self.run_hyph('<p>a banana</p><p xml:lang="pl">banana</p>',
                            'en', h)
        self.assertIn('xml:lang="en"', out)
        # no non-breaking space after "a"; the Polish paragraph is left
        self.assertIn('<p>a ba-na-na</p><p xml:lang="pl">banana</p>', out)

    def test_polish(self):
        out = self.run_hyph('<p>w kolorowa</p><p xml:lang="pl-pl">kolorowa'
                            '</p>', 'pl', hyphenation.polish_hyphenator())
        self.assertIn('xml:lang="pl"', out)
        self.assertIn('<p>w ko-lo-ro-wa</p>', out)
        self.assertIn('>ko-lo-ro-wa</p>', out)

    def test_skip(self):
        out = self.run_hyph('<p>ba­nana</p>', 'en', None, skip=True)
        self.assertIn('<p>banana</p>', out)


OPF = ('<?xml version="1.0" encoding="utf-8"?>'
       '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
       'unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/'
       'elements/1.1/"><dc:title>T</dc:title><dc:identifier id="id">x'
       '</dc:identifier>%s</metadata><manifest><item id="t" href="t.xhtml"'
       ' media-type="application/xhtml+xml"/><item id="ncx" href="toc.ncx"'
       ' media-type="application/x-dtbncx+xml"/></manifest>'
       '<spine toc="ncx"><itemref idref="t"/></spine></package>')
NCX = ('<?xml version="1.0" encoding="utf-8"?>'
       '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
       '<head/><docTitle><text>T</text></docTitle><navMap><navPoint id="n" '
       'playOrder="1"><navLabel><text>T</text></navLabel><content '
       'src="t.xhtml"/></navPoint></navMap></ncx>')


class BookLanguageTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='eqt-test-')
        self.addCleanup(shutil.rmtree, self.dir)

    def fix_language(self, lang_tag, text):
        xhtml = os.path.join(self.dir, 't.xhtml')
        with open(xhtml, 'w', encoding='utf-8') as f:
            f.write(XHTML % ('<p>%s</p>' % text))
        soup = etree.fromstring((OPF % lang_tag).encode())
        out = io.StringIO()
        with redirect_stdout(out):
            soup = fix_various_opf_problems(soup, self.dir, [xhtml],
                                            ['t.xhtml'])
        return (soup.xpath('//dc:language/text()', namespaces={
            'dc': 'http://purl.org/dc/elements/1.1/'}), out.getvalue())

    def test_other_language_kept(self):
        self.assertEqual(self.fix_language(
            '<dc:language>en</dc:language>', ENGLISH_TEXT)[0], ['en'])

    def test_polish_text_with_wrong_language(self):
        langs, out = self.fix_language('<dc:language>en</dc:language>',
                                       POLISH_TEXT)
        self.assertEqual(langs, ['pl'])
        self.assertIn('The text of the book is Polish, not "en"', out)

    def test_polish_variants_and_missing(self):
        for tag in ('<dc:language>pl-PL</dc:language>',
                    '<dc:language>pol</dc:language>',
                    '<dc:language>und</dc:language>',
                    '<dc:language></dc:language>', ''):
            self.assertEqual(self.fix_language(tag, ENGLISH_TEXT)[0],
                             ['pl'], tag)


class QfixLanguageTest(unittest.TestCase):
    """The whole qfix of an English book with and without calibre."""

    def setUp(self):
        hyphenation._cache.clear()
        self.addCleanup(hyphenation._cache.clear)
        self.dir = tempfile.mkdtemp(prefix='eqt-test-')
        self.addCleanup(shutil.rmtree, self.dir)
        with zipfile.ZipFile(os.path.join(self.dir, 'b.epub'), 'w') as z:
            z.writestr('mimetype', 'application/epub+zip')
            z.writestr(
                'META-INF/container.xml',
                '<?xml version="1.0"?><container version="1.0" xmlns="urn:'
                'oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                '<rootfile full-path="content.opf" media-type="application/'
                'oebps-package+xml"/></rootfiles></container>')
            z.writestr('content.opf',
                       OPF % '<dc:language>en-US</dc:language>')
            z.writestr('toc.ncx', NCX)
            z.writestr('t.xhtml', XHTML % (
                '<p>%s</p><p>a banana</p>' % ENGLISH_TEXT))

    def run_qfix(self, calibre_dir):
        with mock.patch.object(hyphenation, 'find_calibre_hyphenation',
                               return_value=calibre_dir):
            out = io.StringIO()
            with redirect_stdout(out):
                qfix(self.dir, 'b.epub', os.path.join(self.dir, 'MOH'),
                     True, False, None, False, True, False, False, False,
                     False, None, True, False)
        with zipfile.ZipFile(os.path.join(self.dir, 'MOH',
                                          'b_moh.epub')) as z:
            return (z.read('content.opf').decode(),
                    z.read('t.xhtml').decode(), out.getvalue())

    def test_with_calibre(self):
        cdir = make_calibre_dir({'hyph_en_US.dic': DIC % 2},
                                {'en_US': 'hyph_en_US.dic'})
        self.addCleanup(shutil.rmtree, cdir)
        opf, xhtml, out = self.run_qfix(cdir)
        self.assertIn('<dc:language>en-US</dc:language>', opf)
        self.assertIn('xml:lang="en-US"', xhtml)
        self.assertIn('a ba%sna%sna' % (HYPHEN_MARK, HYPHEN_MARK), xhtml)
        self.assertIn('dictionary for the book language "en-US": '
                      'hyph_en_US.dic', out)

    def test_without_calibre(self):
        opf, xhtml, out = self.run_qfix(None)
        self.assertIn('<dc:language>en-US</dc:language>', opf)
        self.assertNotIn(HYPHEN_MARK, xhtml)
        self.assertIn('a banana', xhtml)
        self.assertIn('No hyphenation dictionary for the book language '
                      '"en-US" (calibre not found)', out)


if __name__ == '__main__':
    unittest.main()
