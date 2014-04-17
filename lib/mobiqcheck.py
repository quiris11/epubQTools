#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of pyBookTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

import os
import sys
import struct


def find_headers(content, mobi_file):
    if content[60:68] != 'BOOKMOBI':
        print(mobi_file + ': invalid file format. Skipping...')
        return 0
    exth_begin = content.find('EXTH')
    exth_begin2 = content.find('EXTH', content.find('EXTH')+4)
    exth_header = content[exth_begin:]
    count_items, = struct.unpack('>L', exth_header[8:12])
    pos = 12
    found_129 = book_autor_found = book_title_found = False
    for _ in range(count_items):
        id, size = struct.unpack('>LL', exth_header[pos:pos+8])
        exth_record = exth_header[pos + 8: pos + size]
        if id == 100:
            book_autor_found = True
            book_author = exth_record.decode('utf-8')
        if id == 503:
            book_title_found = True
            book_title = exth_record.decode('utf-8')
        if id == 524 and exth_record != 'pl':
            print('Unexpected book language \'' +
                  exth_record.decode('utf-8') + '\': ' + mobi_file)
        if (id == 129 and exth_record != '' and
                os.path.splitext(mobi_file)[1].lower() == '.azw'):
            print('Incorrect file extension. Should be: azw3: ' + mobi_file)
        if id == 501:
            print(mobi_file + ': ' + exth_record.decode('utf-8'))
        if id == 129:
            found_129 = True
        if (id == 129 and exth_record == ''):
            print('Old AZW (Mobi6) format: ' + mobi_file)
        pos += size
    if not found_129:
        print('Old AZW (Mobi6) format: ' + mobi_file)
    if book_autor_found and book_title_found:
        pass  # print(mobi_file + ': ' + book_author + ' - ' + book_title)
    else:
        print('Book title or author not properly defined.' + mobi_file)


def mobi_check(_documents, _rename):
    for root, dirs, files in os.walk(_documents):
        for file in files:
            file_extension = os.path.splitext(file)[1].lower()
            file_dec = file.decode(sys.getfilesystemencoding())
            if file_extension not in ['.mobi', '.azw', '.azw3']:
                continue
            with open(os.path.join(root, file), 'rb') as f:
                mobi_content = f.read()
                find_headers(mobi_content, file_dec)

            # experimental feature
            if args.ebok:
                mobi_content = mobi_content.replace('PDOC', 'EBOK')
                with open(os.path.join(root, 'mod_' + file), 'wb') as f:
                    f.write(mobi_content)

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("directory",
                        help="Directory with EPUB files stored")
    parser.add_argument("-n", "--rename",
                        help="rename .epub files to 'author - title.epub'",
                        action="store_true")
    parser.add_argument("-b", "--ebok",
                        help="replace PDOC to EBOK",
                        action="store_true")
    args = parser.parse_args()

    mobi_check(args.directory, args.rename)
