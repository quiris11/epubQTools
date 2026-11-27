# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
import importlib.abc
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

import lib.resource_data
from lib.resource_data import read_resource

LIB = os.path.dirname(lib.resource_data.__file__)
DIC = 'dictionaries/hyph_pl_PL.dic'


def file_bytes(name):
    with open(os.path.join(LIB, 'resources', *name.split('/')), 'rb') as f:
        return f.read()


class PluginLoader(importlib.abc.Loader):
    """A loader like the one of calibre plugins: no get_data, only
    open_resource with paths relative to the module's package."""

    def __init__(self, files):
        self.files = files

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        with open(lib.resource_data.__file__, encoding='utf-8') as f:
            exec(compile(f.read(), 'resource_data', 'exec'), module.__dict__)

    def open_resource(self, name):
        if name not in self.files:
            raise FileNotFoundError(name)
        return io.BytesIO(self.files[name])


def plugin_module(files):
    loader = PluginLoader(files)
    spec = importlib.util.spec_from_loader('plugin_resource_data', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ReadResourceTest(unittest.TestCase):

    def test_folder(self):
        self.assertEqual(read_resource('container.xml'),
                         file_bytes('container.xml'))
        self.assertEqual(read_resource(DIC), file_bytes(DIC))

    def test_missing_file(self):
        with self.assertRaises(OSError):
            read_resource('no-such-file.txt')

    # in calibre sys.executable is calibre-debug, which has no option -I
    @unittest.skipIf(getattr(sys, 'frozen', False),
                     'sys.executable is not a Python interpreter')
    def test_zip_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, 'epubQTools.zip')
            with zipfile.ZipFile(zip_path, 'w') as z:
                z.writestr('lib/__init__.py', '')
                z.write(lib.resource_data.__file__, 'lib/resource_data.py')
                z.write(os.path.join(LIB, 'resources', *DIC.split('/')),
                        'lib/resources/' + DIC)
            out = subprocess.run(
                [sys.executable, '-I', '-c',
                 'import sys; sys.path.insert(0, sys.argv[1]); '
                 'from lib.resource_data import read_resource; '
                 'sys.stdout.buffer.write(read_resource(sys.argv[2]))',
                 zip_path, DIC],
                capture_output=True, cwd=tmp)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout, file_bytes(DIC))

    def test_calibre_plugin(self):
        module = plugin_module({'resources/' + DIC: b'dic'})
        self.assertEqual(module.read_resource(DIC), b'dic')
        with self.assertRaises(OSError):
            module.read_resource('cover.xhtml')

    def test_calibre_plugin_ignores_frozen(self):
        # calibre sets sys.frozen, but the resources are in the plugin
        module = plugin_module({'resources/cover.xhtml': b'cover'})
        with mock.patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(module.read_resource('cover.xhtml'), b'cover')

    def test_standalone_application(self):
        module = plugin_module({})
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'resources', 'dictionaries'))
            with open(os.path.join(tmp, 'resources', *DIC.split('/')),
                      'wb') as f:
                f.write(b'exe')
            with mock.patch.object(sys, 'frozen', True, create=True), \
                    mock.patch.object(sys, 'executable',
                                      os.path.join(tmp, 'epubQTools.exe')):
                self.assertEqual(module.read_resource(DIC), b'exe')


if __name__ == '__main__':
    unittest.main()
