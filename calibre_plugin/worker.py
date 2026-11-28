# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Fixing the books in a calibre worker process (job 'arbitrary_n'), so
calibre does not stop responding and every job starts with a fresh state of
the modules of lib. Only basic types go in and out of the process."""

import io
import os
import sys
from contextlib import redirect_stderr, redirect_stdout


def add_dependencies(plugin_path):
    """Make the libraries bundled in the plugin (deps/ in the zip, e.g.
    tinycss2 missing in calibre) importable."""
    deps = os.path.join(plugin_path, 'deps')
    if deps not in sys.path:
        sys.path.append(deps)


def fix_books(plugin_path, books, settings, notification=lambda x, y: y):
    """Fix every (book_id, path, title, pages) of books with qfix (pages:
    number of pages for the page list or None). The fixed file is written
    to the MOH folder next to the copy. Return a list of dicts:
    id, title, fixed (path of the fixed file or None), problems (the book
    finished with PROBLEMS), log (all messages of qfix)."""
    add_dependencies(plugin_path)
    from .lib import epubqfix
    from .options import qfix_options
    options = qfix_options(settings)
    results = []
    for nr, (book_id, path, title, pages) in enumerate(books):
        notification(nr / len(books), title)
        root, name = os.path.split(path)
        moh_dir = os.path.join(root, 'MOH')
        fixed = os.path.join(moh_dir, os.path.splitext(name)[0] + '_moh.epub')
        before = len(epubqfix.problem_files)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            epubqfix.qfix(root, name, moh_dir, **dict(options, pages=pages))
        results.append({
            'id': book_id,
            'title': title,
            'fixed': fixed if os.path.isfile(fixed) else None,
            'problems': len(epubqfix.problem_files) > before,
            'log': out.getvalue(),
        })
    notification(1.0, '')
    return results
