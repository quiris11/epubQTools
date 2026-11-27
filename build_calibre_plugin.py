#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Build the calibre plugin: a zip with calibre_plugin/ at the top, lib/
and the libraries missing in calibre (tinycss2) in deps/.

    python3 build_calibre_plugin.py [OUTPUT.zip]

The default output is epubQTools-calibre.zip next to this script. tinycss2
is taken from the Python running this script. Install the plugin with
'calibre-customize -a OUTPUT.zip' or in calibre: Preferences > Plugins >
Load plugin from file."""

import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
IMPORT_NAME = 'epubqtools'
DEFAULT_OUTPUT = os.path.join(HERE, 'epubQTools-calibre.zip')


def package_files(directory, prefix):
    """(path on disk, path in zip) of the files of a package directory,
    without bytecode and macOS metadata."""
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for name in sorted(files):
            if name.endswith(('.pyc', '.pyo')) or name == '.DS_Store':
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, directory).replace(os.sep, '/')
            yield path, prefix + rel


def tinycss2_dir():
    try:
        import tinycss2
    except ImportError:
        sys.exit('tinycss2 is not installed for %s (pip install tinycss2)'
                 % sys.executable)
    return os.path.dirname(os.path.abspath(tinycss2.__file__))


def build(output, tinycss2_path=None):
    """Write the plugin zip to output and return the list of its names."""
    tinycss2_path = tinycss2_path or tinycss2_dir()
    entries = list(package_files(os.path.join(HERE, 'calibre_plugin'), ''))
    entries += package_files(os.path.join(HERE, 'lib'), 'lib/')
    entries += package_files(tinycss2_path, 'deps/tinycss2/')
    entries.append((os.path.join(HERE, 'NOTICE'), 'NOTICE'))
    tmp = output + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        # an empty file with this name sets the package name of the plugin:
        # calibre_plugins.epubqtools
        z.writestr('plugin-import-name-%s.txt' % IMPORT_NAME, '')
        for path, name in entries:
            z.write(path, name)
        names = z.namelist()
    os.replace(tmp, output)
    return names


if __name__ == '__main__':
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                          else DEFAULT_OUTPUT)
    files = build(out)
    print('%s (%d files)' % (out, len(files)))
