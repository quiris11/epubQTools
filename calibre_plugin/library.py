# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Work with the calibre library (db.new_api), without the GUI.

The fixed book becomes the EPUB format and the original is kept as
ORIGINAL_EPUB (as calibre's Polish books does). The original is saved only
once: calibre's save_original_format overwrites an existing ORIGINAL_EPUB,
so a second run would lose the real original. A second run fixes the book
again from ORIGINAL_EPUB, not from the already fixed EPUB."""

import os
import re

ORIGINAL = 'ORIGINAL_EPUB'


def source_format(db, book_id):
    """Format the book is fixed from: ORIGINAL_EPUB, EPUB or None."""
    for fmt in (ORIGINAL, 'EPUB'):
        if db.has_format(book_id, fmt):
            return fmt
    return None


def file_name(title, book_id):
    """Name of the copy of the book: the title (shown in the messages of
    qfix) without characters not allowed in file names."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', title or '').strip(' .')
    return (name[:100].strip(' .') or 'book %d' % book_id) + '.epub'


def copy_books(db, book_ids, work_dir):
    """Copy the source format of every book to its own folder in work_dir.
    Return (books, skipped): books - (book_id, path, title) for qfix,
    skipped - titles of the books without an EPUB."""
    books, skipped = [], []
    for book_id in book_ids:
        title = db.field_for('title', book_id)
        fmt = source_format(db, book_id)
        if fmt is None:
            skipped.append(title)
            continue
        book_dir = os.path.join(work_dir, str(book_id))
        os.makedirs(book_dir, exist_ok=True)
        path = os.path.join(book_dir, file_name(title, book_id))
        db.copy_format_to(book_id, fmt, path)
        books.append((book_id, path, title))
    return books, skipped


def store_fixed(db, book_id, fixed_path):
    """Make the fixed file the EPUB of the book; the original is saved as
    ORIGINAL_EPUB if it is not saved yet. False if the book or both its
    formats are gone (e.g. removed while the job was running)."""
    if not db.has_id(book_id) or source_format(db, book_id) is None:
        return False
    if not db.has_format(book_id, ORIGINAL):
        db.save_original_format(book_id, 'EPUB')
    # no import hooks (e.g. other plugins), the file is not a new import
    return db.add_format(book_id, 'EPUB', fixed_path, run_hooks=False)


def restore_original(db, book_id):
    """Replace the EPUB with ORIGINAL_EPUB (which is removed). False if the
    book has no ORIGINAL_EPUB."""
    if not db.has_id(book_id) or not db.has_format(book_id, ORIGINAL):
        return False
    return bool(db.restore_original_format(book_id, ORIGINAL))
