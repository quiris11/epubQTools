# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
"""Parts of the calibre plugin which work without calibre: settings,
work with the library (on a fake library) and the built zip."""
import ast
import collections
import importlib.util
import inspect
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import build_calibre_plugin
from lib import epubqfix

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'calibre_plugin')


def load(name):
    """A module of calibre_plugin/ without its package (its __init__.py
    needs calibre)."""
    spec = importlib.util.spec_from_file_location(
        'eqt_plugin_' + name, os.path.join(PLUGIN, name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


options = load('options')
library = load('library')
translations = load('translations')
update = load('update')
ORIG = library.ORIGINAL_FILE


class FakeDB(object):
    """The calls of db.new_api used by the plugin, with the behaviour of
    calibre 9.19. Data files are kept under their relpath next to the
    formats."""

    def __init__(self, books):
        self.books = books          # id -> {'title': str, fmt: bytes}

    def has_id(self, book_id):
        return book_id in self.books

    def has_format(self, book_id, fmt):
        return fmt in self.books.get(book_id, {}) and '/' not in fmt

    def field_for(self, field, book_id):
        return self.books[book_id][field]

    def copy_format_to(self, book_id, fmt, dest):
        with open(dest, 'wb') as f:
            f.write(self.books[book_id][fmt])

    def add_format(self, book_id, fmt, path, run_hooks=True):
        with open(path, 'rb') as f:
            self.books[book_id][fmt] = f.read()
        return True

    def remove_formats(self, formats_map):
        for book_id, fmts in formats_map.items():
            for fmt in fmts:
                self.books[book_id].pop(fmt, None)

    def restore_original_format(self, book_id, original_fmt):
        book = self.books[book_id]
        book[original_fmt[len('ORIGINAL_'):]] = book.pop(original_fmt)
        return True

    def list_extra_files(self, book_id):
        return tuple(collections.namedtuple('ExtraFile', 'relpath')(k)
                     for k in self.books[book_id] if '/' in k)

    def add_extra_files(self, book_id, files):
        for relpath, path in files.items():
            with open(path, 'rb') as f:
                self.books[book_id][relpath] = f.read()
        return dict.fromkeys(files, True)

    def copy_extra_file_to(self, book_id, relpath, dest):
        self.copy_format_to(book_id, relpath, dest)

    def remove_extra_files(self, book_id, relpaths):
        for relpath in relpaths:
            del self.books[book_id][relpath]
        return dict.fromkeys(relpaths)


class OldFakeDB(FakeDB):
    """calibre < 8: no remove_extra_files."""

    @property
    def remove_extra_files(self):
        raise AttributeError('remove_extra_files')


class TestOptions(unittest.TestCase):

    def test_defaults_are_like_c_r_e(self):
        o = options.qfix_options({})
        self.assertEqual(o['_resetmargins'], False)     # -c
        self.assertEqual(o['arg_justify'], True)        # --skip-justify too
        self.assertEqual(o['arg_left'], False)
        self.assertEqual(o['skip_hyph'], False)
        self.assertEqual(o['dont_hyph_headers'], True)      # -r
        self.assertEqual(o['skip_pages'], False)
        self.assertEqual(o['del_colors'], False)
        self.assertEqual(o['del_fonts'], False)
        self.assertIsNone(o['html_margin'])
        self.assertEqual(o['fix_container_only'], False)

    def test_names_are_arguments_of_qfix(self):
        params = list(inspect.signature(epubqfix._qfix).parameters)
        self.assertEqual(sorted(options.qfix_options({})),
                         sorted(params[3:]))

    def test_settings(self):
        o = options.qfix_options({
            'hyphenate': False, 'hyphenate_headers': False,
            'reset_css': False, 'align': options.ALIGN_LEFT,
            'remove_colors': True, 'remove_fonts': True,
            'book_margin': 15, 'page_list': False})
        self.assertEqual(
            (o['skip_hyph'], o['dont_hyph_headers'], o['_resetmargins'],
             o['arg_justify'], o['arg_left'], o['del_colors'],
             o['del_fonts'], o['html_margin'], o['skip_pages']),
            (True, True, False, False, True, True, True, '15', True))
        o = options.qfix_options({'align': options.ALIGN_KEEP})
        self.assertEqual((o['arg_justify'], o['arg_left']), (False, False))

    def test_wrong_values(self):
        s = options.with_defaults({'align': 'center', 'book_margin': 'x',
                                   'unknown': 1})
        self.assertEqual(s, options.DEFAULTS)
        self.assertIsNone(options.with_defaults({'book_margin': -3})
                          ['book_margin'])
        self.assertEqual(options.with_defaults({'book_margin': '7'})
                         ['book_margin'], 7)


class TestLibrary(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def fixed(self, data):
        path = os.path.join(self.dir, 'fixed.epub')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_file_name(self):
        self.assertEqual(library.file_name('Ala: ma/kota?', 1),
                         'Ala_ ma_kota_.epub')
        self.assertEqual(library.file_name('Żółć', 1), 'Żółć.epub')
        self.assertEqual(library.file_name('...', 7), 'book 7.epub')
        self.assertEqual(len(library.file_name('a' * 300, 1)), 105)

    def test_copy_books_prefers_original(self):
        db = FakeDB({1: {'title': 'A', 'EPUB': b'fixed', ORIG: b'orig',
                         'ORIGINAL_EPUB': b'polished'},
                     2: {'title': 'B', 'EPUB': b'b'},
                     3: {'title': 'C', 'MOBI': b'c'},
                     4: {'title': 'D', 'EPUB': b'fixed',
                         'ORIGINAL_EPUB': b'orig'}})
        books, skipped = library.copy_books(db, [1, 2, 3, 4], self.dir)
        self.assertEqual([(b[0], b[2]) for b in books],
                         [(1, 'A'), (2, 'B'), (4, 'D')])
        self.assertEqual(skipped, ['C'])
        for book, data in zip(books, (b'orig', b'b', b'orig')):
            with open(book[1], 'rb') as f:
                self.assertEqual(f.read(), data)
        self.assertEqual(os.path.dirname(books[1][1]),
                         os.path.join(self.dir, '2'))

    def test_store_keeps_first_original(self):
        db = FakeDB({1: {'title': 'A', 'EPUB': b'orig'}})
        self.assertTrue(library.store_fixed(db, 1, self.fixed(b'fix1')))
        self.assertTrue(library.store_fixed(db, 1, self.fixed(b'fix2')))
        self.assertEqual(db.books[1], {'title': 'A', 'EPUB': b'fix2',
                                       ORIG: b'orig'})

    def test_converted_from_fixed(self):
        """calibre converts from ORIGINAL_EPUB if the book has it, so the
        book must not have it after fixing."""
        db = FakeDB({1: {'title': 'A', 'EPUB': b'fix0',
                         'ORIGINAL_EPUB': b'orig'},
                     2: {'title': 'B', 'EPUB': b'polished', ORIG: b'orig',
                         'ORIGINAL_EPUB': b'fix1'}})
        self.assertTrue(library.store_fixed(db, 1, self.fixed(b'fix')))
        self.assertTrue(library.store_fixed(db, 2, self.fixed(b'fix')))
        for book in (db.books[1], db.books[2]):
            self.assertEqual(book[ORIG], b'orig')
            self.assertEqual(book['EPUB'], b'fix')
            self.assertNotIn('ORIGINAL_EPUB', book)

    def test_store_book_gone(self):
        db = FakeDB({1: {'title': 'A', 'MOBI': b'm'}})
        self.assertFalse(library.store_fixed(db, 1, self.fixed(b'x')))
        self.assertFalse(library.store_fixed(db, 2, self.fixed(b'x')))
        self.assertEqual(db.books[1], {'title': 'A', 'MOBI': b'm'})

    def test_store_epub_removed_original_kept(self):
        db = FakeDB({1: {'title': 'A', 'ORIGINAL_EPUB': b'orig'}})
        self.assertTrue(library.store_fixed(db, 1, self.fixed(b'fix')))
        self.assertEqual(db.books[1], {'title': 'A', 'EPUB': b'fix',
                                       ORIG: b'orig'})

    def test_restore(self):
        db = FakeDB({1: {'title': 'A', 'EPUB': b'orig'},
                     2: {'title': 'B', 'EPUB': b'b'},
                     3: {'title': 'C', 'EPUB': b'fix',
                         'ORIGINAL_EPUB': b'orig'}})
        library.store_fixed(db, 1, self.fixed(b'fix'))
        self.assertEqual([library.has_original(db, i) for i in (1, 2, 3, 4)],
                         [True, False, True, False])
        self.assertTrue(library.restore_original(db, 1, self.dir))
        self.assertEqual(db.books[1], {'title': 'A', 'EPUB': b'orig'})
        self.assertFalse(library.restore_original(db, 2, self.dir))
        self.assertTrue(library.restore_original(db, 3, self.dir))
        self.assertEqual(db.books[3], {'title': 'C', 'EPUB': b'orig'})
        self.assertFalse(library.has_original(db, 1))

    def test_restore_old_calibre(self):
        """calibre < 8 cannot remove data files: the original stays."""
        db = OldFakeDB({1: {'title': 'A', 'EPUB': b'orig'}})
        library.store_fixed(db, 1, self.fixed(b'fix'))
        self.assertTrue(library.restore_original(db, 1, self.dir))
        self.assertEqual(db.books[1], {'title': 'A', 'EPUB': b'orig',
                                       ORIG: b'orig'})


def release(tag='v1.1', zip_name='epubQTools-calibre-1.1.zip', **extra):
    """An answer of GitHub for the latest release."""
    answer = {'tag_name': tag, 'draft': False, 'prerelease': False,
              'html_url': 'https://github.com/quiris11/epubQTools/releases/'
                          'tag/' + tag,
              'assets': [{'name': zip_name}] if zip_name else []}
    answer.update(extra)
    return answer


class TestUpdate(unittest.TestCase):

    def test_versions(self):
        self.assertEqual(update.parse_version('v1.2'), (1, 2, 0))
        self.assertEqual(update.parse_version('1.2.3'), (1, 2, 3))
        self.assertEqual(update.parse_version('V2'), (2, 0, 0))
        for wrong in (None, '', 'v', 'v1.0-beta', 'latest', '1..2'):
            self.assertIsNone(update.parse_version(wrong), wrong)
        self.assertEqual(update.version_text((1, 0, 0)), '1.0')
        self.assertEqual(update.version_text((1, 2, 1)), '1.2.1')
        self.assertTrue(update.is_newer('1.10', (1, 9, 0)))
        self.assertTrue(update.is_newer('1.0.1', (1, 0, 0)))
        self.assertFalse(update.is_newer('1.0', (1, 0, 0)))
        self.assertFalse(update.is_newer('0.9', (1, 0, 0)))
        self.assertFalse(update.is_newer(None, (1, 0, 0)))

    def test_newer_release(self):
        self.assertEqual(update.newer_release(release(), (1, 0, 0)), {
            'version': '1.1',
            'url': 'https://github.com/quiris11/epubQTools/releases/tag/'
                   'v1.1'})
        self.assertEqual(update.newer_release(
            release('v1.0.2', 'epubQTools-calibre-1.0.2.zip'),
            (1, 0, 0))['version'], '1.0.2')

    def test_no_newer_release(self):
        current = (1, 0, 0)
        for answer in (release('v1.0'),            # the same version
                       release('v0.9'),            # older
                       release(zip_name=None),     # without the plugin
                       release(zip_name='epubQTools-1.1.zip'),
                       release(draft=True), release(prerelease=True),
                       release('nightly'),
                       release(html_url='https://example.com/x'),
                       release(assets=None), {}, None, [], 'v1.1'):
            self.assertIsNone(update.newer_release(answer, current), answer)

    def test_check_due(self):
        day = update.CHECK_EVERY
        self.assertTrue(update.check_due(None, 1000))
        self.assertTrue(update.check_due('x', 1000))
        self.assertFalse(update.check_due(1000, 1000 + day - 1))
        self.assertTrue(update.check_due(1000, 1000 + day))
        self.assertTrue(update.check_due(1000 + day, 1000))  # clock back


class TestTranslations(unittest.TestCase):

    def texts(self):
        """The texts given to tr() in the modules of the plugin."""
        found = set()
        for name in os.listdir(PLUGIN):
            if not name.endswith('.py') or name == 'translations.py':
                continue
            with open(os.path.join(PLUGIN, name), encoding='utf-8') as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and
                        isinstance(node.func, ast.Name) and
                        node.func.id == 'tr'):
                    self.assertIsInstance(node.args[0], ast.Constant)
                    found.add(node.args[0].value)
        return found

    def test_every_text_has_polish(self):
        self.assertEqual(self.texts(), set(translations.POLISH))

    def test_same_placeholders(self):
        for en, pl in translations.POLISH.items():
            self.assertEqual(re.findall('%.', en), re.findall('%.', pl), en)
            self.assertNotEqual(en, pl)

    def test_language(self):
        tr = translations.tr
        self.assertEqual(tr('No change', 'pl'), 'Bez zmian')
        self.assertEqual(tr('No change', 'pl_PL'), 'Bez zmian')
        self.assertEqual(tr('No change', 'en'), 'No change')
        self.assertEqual(tr('No change', 'de'), 'No change')
        self.assertEqual(tr('Not translated', 'pl'), 'Not translated')
        try:
            from calibre.utils.localization import get_lang
            expected = get_lang()       # in calibre: its language
        except ImportError:
            expected = 'en'             # without calibre
        self.assertEqual(translations.language(), expected)


class TestBuild(unittest.TestCase):

    def test_zip(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        out = os.path.join(tmp, 'plugin.zip')
        names = build_calibre_plugin.build(out)
        with zipfile.ZipFile(out) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(sorted(z.namelist()), sorted(names))
        for name in ('__init__.py', 'action.py', 'config.py', 'library.py',
                     'options.py', 'translations.py', 'update.py',
                     'worker.py',
                     'plugin-import-name-epubqtools.txt', 'NOTICE',
                     'lib/__init__.py', 'lib/epubqfix.py',
                     'lib/resources/dictionaries/hyph_pl_PL.dic',
                     'deps/tinycss2/__init__.py'):
            self.assertIn(name, names)
        self.assertFalse([n for n in names
                          if n.endswith('.pyc') or '__pycache__' in n or
                          n.endswith('.DS_Store')])
        root = os.path.dirname(PLUGIN)
        tracked = subprocess.run(
            ['git', '-C', root, 'ls-files', 'lib', 'calibre_plugin'],
            capture_output=True, text=True).stdout.split()
        for path in tracked:
            name = path[len('calibre_plugin/'):] if path.startswith(
                'calibre_plugin/') else path
            self.assertIn(name, names)


if __name__ == '__main__':
    unittest.main()
