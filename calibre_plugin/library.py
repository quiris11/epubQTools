# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Work with the calibre library (db.new_api), without the GUI.

The fixed book becomes the EPUB format and the original is kept as a data
file of the book (ORIGINAL_FILE), not as the ORIGINAL_EPUB format: when
a book has ORIGINAL_EPUB, calibre converts from it (e.g. to MOBI), so the
fixes would be lost. The original is saved only once and a second run
fixes the book again from it, not from the already fixed EPUB.

ORIGINAL_EPUB left by older versions of the plugin or by calibre (Polish
books, conversion EPUB to EPUB) is the format the book is fixed from when
there is no saved original yet; it then becomes the saved original. After
storing a fixed book, the book has no ORIGINAL_EPUB."""

import os
import re

ORIGINAL = 'ORIGINAL_EPUB'
ORIGINAL_FILE = 'data/epubQTools original.epub'


def has_original_file(db, book_id):
    return any(f.relpath == ORIGINAL_FILE
               for f in db.list_extra_files(book_id))


def has_original(db, book_id):
    """True if the book has a saved original (data file or ORIGINAL_EPUB)."""
    return (db.has_id(book_id) and
            (has_original_file(db, book_id) or
             db.has_format(book_id, ORIGINAL)))


def source_format(db, book_id):
    """What the book is fixed from: ORIGINAL_FILE, ORIGINAL_EPUB, EPUB or
    None."""
    if has_original_file(db, book_id):
        return ORIGINAL_FILE
    for fmt in (ORIGINAL, 'EPUB'):
        if db.has_format(book_id, fmt):
            return fmt
    return None


def copy_source(db, book_id, source, dest):
    if source == ORIGINAL_FILE:
        db.copy_extra_file_to(book_id, ORIGINAL_FILE, dest)
    else:
        db.copy_format_to(book_id, source, dest)


def file_name(title, book_id):
    """Name of the copy of the book: the title (shown in the messages of
    qfix) without characters not allowed in file names."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', title or '').strip(' .')
    return (name[:100].strip(' .') or 'book %d' % book_id) + '.epub'


def copy_books(db, book_ids, work_dir):
    """Copy what every book is fixed from to its own folder in work_dir.
    Return (books, skipped): books - (book_id, path, title) for qfix,
    skipped - titles of the books without an EPUB."""
    books, skipped = [], []
    for book_id in book_ids:
        title = db.field_for('title', book_id)
        source = source_format(db, book_id)
        if source is None:
            skipped.append(title)
            continue
        book_dir = os.path.join(work_dir, str(book_id))
        os.makedirs(book_dir, exist_ok=True)
        path = os.path.join(book_dir, file_name(title, book_id))
        copy_source(db, book_id, source, path)
        books.append((book_id, path, title))
    return books, skipped


def store_fixed(db, book_id, fixed_path):
    """Make the fixed file the EPUB of the book. The original (ORIGINAL_EPUB
    or EPUB) is saved as ORIGINAL_FILE if it is not saved yet; ORIGINAL_EPUB
    is removed, so that calibre converts the fixed EPUB. False if the book
    or everything it can be fixed from is gone (e.g. removed while the job
    was running)."""
    if not db.has_id(book_id):
        return False
    source = source_format(db, book_id)
    if source is None:
        return False
    if source != ORIGINAL_FILE:
        original = fixed_path + '.original'
        db.copy_format_to(book_id, source, original)
        if not db.add_extra_files(book_id, {ORIGINAL_FILE: original}).get(
                ORIGINAL_FILE):
            return False
    if db.has_format(book_id, ORIGINAL):
        db.remove_formats({book_id: (ORIGINAL,)})
    # no import hooks (e.g. other plugins), the file is not a new import
    return db.add_format(book_id, 'EPUB', fixed_path, run_hooks=False)


def restore_original(db, book_id, work_dir):
    """Replace the EPUB with the saved original, which is removed (the data
    file only in calibre 8.0 and newer, which can remove data files). False
    if the book has no saved original."""
    if not db.has_id(book_id):
        return False
    if has_original_file(db, book_id):
        path = os.path.join(work_dir, '%d.epub' % book_id)
        db.copy_extra_file_to(book_id, ORIGINAL_FILE, path)
        if not db.add_format(book_id, 'EPUB', path, run_hooks=False):
            return False
        if hasattr(db, 'remove_extra_files'):
            db.remove_extra_files(book_id, (ORIGINAL_FILE,))
        return True
    if db.has_format(book_id, ORIGINAL):
        return bool(db.restore_original_format(book_id, ORIGINAL))
    return False
