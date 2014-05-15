#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

from __future__ import print_function
import os
import sys
import struct


class PalmDB:
    unique_id_seed = 68
    number_of_pdb_records = 76
    first_pdb_record = 78

    def __init__(self, palmdata):
        self.data = palmdata
        self.nsec, = struct.unpack_from('>H', self.data,
                                        PalmDB.number_of_pdb_records)

    def getsecaddr(self, secno):
        secstart, = struct.unpack_from('>L', self.data,
                                       PalmDB.first_pdb_record+secno*8)
        if secno == self.nsec-1:
            secend = len(self.data)
        else:
            secend, = struct.unpack_from('>L', self.data,
                                         PalmDB.first_pdb_record+(secno+1)*8)
        return secstart, secend

    def readsection(self, secno):
        if secno < self.nsec:
            secstart, secend = self.getsecaddr(secno)
            return self.data[secstart:secend]
        return ''

    def getnumsections(self):
        return self.nsec


def find_exth(search_id, content):
    exth_begin = content.find('EXTH')
    exth_header = content[exth_begin:]
    count_items, = struct.unpack('>L', exth_header[8:12])
    pos = 12
    for _ in range(count_items):
        id, size = struct.unpack('>LL', exth_header[pos:pos+8])
        exth_record = exth_header[pos + 8: pos + size]
        if id == search_id:
            return exth_record
        pos += size
    return '* NONE *'


def mobi_header_fields(mobi_content):
    pp = PalmDB(mobi_content)
    header = pp.readsection(0)
    id = struct.unpack_from('4s', header, 0x10)[0]
    version = struct.unpack_from('>L', header, 0x24)[0]
    return id, version


def mobi_check(_documents, _rename):
    for root, dirs, files in os.walk(_documents):
        for file in files:
            file_extension = os.path.splitext(file)[1].lower()
            file_dec = file.decode(sys.getfilesystemencoding())
            if file_extension not in ['.mobi', '.azw', '.azw3']:
                continue
            with open(os.path.join(root, file), 'rb') as f:
                mobi_content = f.read()
            if mobi_content[60:68] != 'BOOKMOBI':
                print(file_dec + ': invalid file format. Skipping...')
                continue
            id, ver = mobi_header_fields(mobi_content)
            if ver == args.version:
                print(
                    id, ver, file_dec,
                    find_exth(100, mobi_content).decode('utf8'),
                    find_exth(503, mobi_content).decode('utf8'),
                    find_exth(101, mobi_content).decode('utf8'),    
                    sep='\t')
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
    parser.add_argument("--version", nargs='?',
                        default=None, type=int, metavar="VER",
                        help="find books with Mobi header version (6 or 8)")
    parser.add_argument("-n", "--rename",
                        help="rename .epub files to 'author - title.epub'",
                        action="store_true")
    parser.add_argument("-b", "--ebok",
                        help="replace PDOC to EBOK",
                        action="store_true")
    args = parser.parse_args()

    mobi_check(args.directory, args.rename)
