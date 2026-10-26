# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CommandLineTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='eqt-test-')
        for sub in ('a', 'b'):
            os.makedirs(os.path.join(self.dir, sub))
            open(os.path.join(self.dir, sub, 'x.epub'), 'wb').close()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_eqt(self, *args):
        return subprocess.run([sys.executable, REPO] + list(args),
                              capture_output=True, text=True, cwd=self.dir)

    def test_individual_without_number_before_directory(self):
        for args in (('-i', self.dir), (self.dir, '-i'),
                     ('--individual', self.dir)):
            with self.subTest(args):
                result = self.run_eqt(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('[b]\n  1  x.epub', result.stdout)

    def test_individual_list_alphabetical(self):
        for name in ('Żak.epub', 'zebra.epub', 'Łoś.epub', 'lis.epub',
                     'Ala.epub', 'Ala 2.epub'):
            open(os.path.join(self.dir, name), 'wb').close()
        result = self.run_eqt('-i', self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = [line.split(None, 1)[1] for line in
                  result.stdout.splitlines()
                  if line.startswith('  ') and line.split()[0].isdigit()]
        self.assertEqual(listed, ['Ala.epub', 'Ala 2.epub', 'lis.epub',
                                  'Łoś.epub', 'zebra.epub', 'Żak.epub',
                                  'x.epub', 'x.epub'])
        self.assertIn('[a]\n  6  x.epub\n\n[b]\n  7  x.epub',
                      result.stdout)
        self.assertIn('8 file(s)', result.stdout)

    def test_individual_number_list(self):
        # x.epub in a and b are numbers 0 and 1; --author needs one file
        for nr in ('0,1', '0-1', '1,0'):
            with self.subTest(nr):
                result = self.run_eqt('-i', nr, '--author', 'A, B', self.dir)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('work only with one file', result.stdout)
        for nr in ('2', '0,2', '1-3'):
            with self.subTest(nr):
                result = self.run_eqt('-i', nr, self.dir)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('File number "%s" not found' % nr,
                              result.stdout)

    def test_log_or_tools_without_value_before_directory(self):
        logs = tempfile.mkdtemp(prefix='eqt-logs-')
        self.addCleanup(shutil.rmtree, logs)
        for args, log_dir in ((('-i', '-l', self.dir), self.dir),
                              (('-i', '--log', self.dir), self.dir),
                              (('-i', '--tools', self.dir), None),
                              (('-i', '--tools', logs, '-l', self.dir),
                               self.dir),
                              (('-i', '-l', logs, self.dir), logs)):
            with self.subTest(args):
                result = self.run_eqt(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('[b]\n  1  x.epub', result.stdout)
                for d in (self.dir, logs):
                    found = [f for f in os.listdir(d) if f.endswith('.log')]
                    self.assertEqual(len(found), d == log_dir, d)
                    for f in found:
                        os.remove(os.path.join(d, f))

    def test_log_directory_named_1(self):
        # run_eqt runs in self.dir, so '1' is self.dir/1
        log_dir = os.path.join(self.dir, '1')
        os.makedirs(log_dir)
        result = self.run_eqt('-i', '-l', '1', self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            len([f for f in os.listdir(log_dir) if f.endswith('.log')]), 1)
        self.assertFalse(
            [f for f in os.listdir(self.dir) if f.endswith('.log')])

    def test_old_moh_files_skipped(self):
        def touch(*path):
            os.makedirs(os.path.join(self.dir, *path[:-1]), exist_ok=True)
            open(os.path.join(self.dir, *path), 'wb').close()
        touch('a', 'A - T.epub')
        touch('MOH', 'a', 'A - T_moh.epub')
        touch('MOH', 'A - T_moh.epub')          # flat MOH of older versions
        touch('a', 'A - T_moh.epub')            # next to the original
        touch('MOH', 'A - U_moh.epub')          # original deleted: kept
        result = self.run_eqt('-t', self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            sorted(os.listdir(os.path.join(self.dir, 'TS2K'))),
            ['T.epub', 'U.epub'])
        for path in (('MOH', 'A - T_moh.epub'), ('a', 'A - T_moh.epub')):
            self.assertIn('  - ' + os.path.join(self.dir, *path),
                          result.stdout)

    def test_send_to_kindle_individual(self):
        for sub, title in (('a', 'T'), ('b', 'U')):
            os.makedirs(os.path.join(self.dir, 'MOH', sub))
            open(os.path.join(self.dir, sub, 'A - %s.epub' % title),
                 'wb').close()
            open(os.path.join(self.dir, 'MOH', sub, 'A - %s_moh.epub' %
                              title), 'wb').close()
        # 0 A - T.epub, 1 x.epub, 2 A - U.epub, 3 x.epub
        result = self.run_eqt('-i', '2', '-t', self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.listdir(os.path.join(self.dir, 'TS2K')),
                         ['U.epub'])

    def test_send_to_kindle_individual_keeps_other_files(self):
        os.makedirs(os.path.join(self.dir, 'MOH', 'b'))
        open(os.path.join(self.dir, 'b', 'A - U.epub'), 'wb').close()
        with open(os.path.join(self.dir, 'MOH', 'b', 'A - U_moh.epub'),
                  'wb') as f:
            f.write(b'new')
        os.makedirs(os.path.join(self.dir, 'TS2K'))
        for name in ('T.epub', 'U.epub'):
            with open(os.path.join(self.dir, 'TS2K', name), 'wb') as f:
                f.write(b'old')
        # 0 a/x.epub, 1 A - U.epub, 2 b/x.epub
        result = self.run_eqt('-i', '1', '-t', self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        ts2k = os.path.join(self.dir, 'TS2K')
        self.assertEqual(sorted(os.listdir(ts2k)), ['T.epub', 'U.epub'])
        with open(os.path.join(ts2k, 'U.epub'), 'rb') as f:
            self.assertEqual(f.read(), b'new')

    def test_send_to_kindle_composes_polish_letters(self):
        nfd = unicodedata.normalize('NFD', 'Ścieżka żółwia')
        os.makedirs(os.path.join(self.dir, 'MOH'))
        open(os.path.join(self.dir, 'A - %s.epub' % nfd), 'wb').close()
        open(os.path.join(self.dir, 'MOH', 'A - %s_moh.epub' % nfd),
             'wb').close()
        # an old decomposed copy from an earlier run
        os.makedirs(os.path.join(self.dir, 'TS2K'))
        open(os.path.join(self.dir, 'TS2K', nfd + '.epub'), 'wb').close()
        result = self.run_eqt('-i', '0', '-t', self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.listdir(os.path.join(self.dir, 'TS2K')),
                         ['Ścieżka żółwia.epub'])

    def test_missing_directory(self):
        result = self.run_eqt('-q')
        self.assertEqual(result.returncode, 2)
        self.assertIn('required: directory', result.stderr)
        self.assertNotIn('[directory]', result.stderr)


if __name__ == '__main__':
    unittest.main()
