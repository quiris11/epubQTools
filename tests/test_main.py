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
                self.assertIn('1 ' + os.path.join(self.dir, ''),
                              result.stdout)


if __name__ == '__main__':
    unittest.main()
