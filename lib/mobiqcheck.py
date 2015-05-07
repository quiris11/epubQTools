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
import codecs
from datetime import datetime
import unicodedata

SFENC = sys.getfilesystemencoding()


class Logger(object):
    def __init__(self, filename='eQT-default.log'):
        self.terminal = sys.stdout
        self.log = codecs.open(filename, 'w', 'utf-8')

    def write(self, message):
        self.terminal.write(message)
        if sys.platform == 'win32':
            message = message.replace('\n', '\r\n')
        self.log.write(message)


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


def strip_accents(text):
    return ''.join(c for c in unicodedata.normalize(
        'NFKD', text
    ) if unicodedata.category(c) != 'Mn')


def rename_mobi(title, author):
    if title.isupper():
        title = title.title()
    if author.isupper():
        author = author.title()
    nfname = strip_accents(unicode(author + ' - ' + title))
    nfname = nfname.replace(u'\u2013', '-').replace('/', '_')\
                   .replace(':', '_').replace(u'\u0142', 'l')\
                   .replace(u'\u0141', 'L')
    nfname = "".join(x for x in nfname if (
        x.isalnum() or x.isspace() or x in ('_', '-', '.')
    ))
    return nfname.encode(SFENC)


def mobi_header_fields(mobi_content):
    pp = PalmDB(mobi_content)
    header = pp.readsection(0)
    id = struct.unpack_from('4s', header, 0x10)[0]
    version = struct.unpack_from('>L', header, 0x24)[0]
    # number of locations
    text_length = struct.unpack('>I', header[4:8])[0]
    locations = text_length/150 + 1
    # title
    toff, tlen = struct.unpack('>II', header[0x54:0x5c])
    tend = toff + tlen
    title = header[toff:tend]

    return id, version, title, locations


def mobi_check(_documents):
    if args.locations:
        print('pages', 'locations', 'author - title', sep='\t')
    for dirpath, dirs, files in os.walk(_documents):
        for file in files:
            file_extension = os.path.splitext(file)[1].lower()
            file_dec = file.decode(sys.getfilesystemencoding())
            if file_extension not in ['.mobi', '.azw', '.azw3']:
                continue
            with open(os.path.join(dirpath, file), 'rb') as f:
                mobi_content = f.read()
            if mobi_content[60:68] != 'BOOKMOBI':
                print(file_dec + ': invalid file format. Skipping...')
                continue
            id, ver, title, locations = mobi_header_fields(mobi_content)
            author = find_exth(100, mobi_content)
            if args.locations:
                print(
                    locations/15+1, locations,
                    strip_accents(author.decode('utf8')) + ' - ' + strip_accents(title.decode('utf8')),
                    sep='\t')
            if ver == args.version:
                print(
                    id, ver, file_dec, title,
                    author.decode(SFENC),
                    find_exth(503, mobi_content).decode(SFENC),
                    find_exth(101, mobi_content).decode(SFENC),
                    sep='\t')
            # experimental feature
            if args.ebok:
                mobi_content = mobi_content.replace('PDOC', 'EBOK')
                with open(os.path.join(dirpath, 'mod_' + file), 'wb') as f:
                    f.write(mobi_content)
            # rename MOBI files
            if args.rename:
                nt = rename_mobi(title.decode('utf8'), author.decode('utf8'))
                newfn = nt.encode(SFENC) + file_extension
                if (
                    file.decode(SFENC) == newfn or
                    file.decode(SFENC).split(
                        '('
                    )[0][:-1] + file_extension == newfn
                ):
                    print('= Renaming file %s is not needed' % (
                        file.decode(SFENC)
                    ))
                elif os.path.exists(os.path.join(dirpath,
                                    newfn)):
                    counter = 0
                    while True:
                        counter += 1
                        if not os.path.exists(os.path.join(dirpath,
                                              nt.encode(SFENC) + ' (' +
                                              str(counter) + ')' +
                                              file_extension)):
                            print('* Renaming file: %s to %s' % (
                                file,
                                nt.encode(SFENC) + ' (' + str(counter) + ')' +
                                file_extension
                            ))
                            os.rename(os.path.join(dirpath, file),
                                      os.path.join(
                                      dirpath,
                                      nt.encode(SFENC) + ' (' + str(counter) +
                                      ')' + file_extension
                                      ))
                            break

                else:
                    print('* Renaming file: %s to %s' % (file, newfn))
                    os.rename(os.path.join(dirpath, file),
                              os.path.join(dirpath, newfn))


def fix_extension(dir):
    for dirpath, dirs, files in os.walk(dir):
        for file in files:
            file_extension = os.path.splitext(file)[1].lower()
            file_dec = file.decode(sys.getfilesystemencoding())
            if file_extension not in ['.azw', '.azw3']:
                continue
            with open(os.path.join(dirpath, file), 'rb') as f:
                mobi_content = f.read()
            if mobi_content[60:68] != 'BOOKMOBI':
                print(file_dec + ': invalid file format. Skipping...')
                continue
            id, ver = mobi_header_fields(mobi_content)
            if ver == 8:
                new_ext = '.azw3'
            elif ver == 6:
                new_ext = '.azw'
            else:
                continue
            if new_ext == os.path.splitext(file)[1]:
                continue
            if not os.path.exists(os.path.join(dirpath,
                                  os.path.splitext(file)[0] + new_ext)):
                os.rename(os.path.join(dirpath, file),
                          os.path.join(dirpath,
                                       os.path.splitext(file)[0] + new_ext))
                print('* File extension for "%s" was changed to "%s"'
                      % (file_dec, new_ext))
            else:
                print('* File extension was not changed for file "%s". '
                      'File with updated filename already exists...'
                      % file_dec)


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("directory",
                        help="Directory with EPUB files stored")
    parser.add_argument("--version", nargs='?',
                        default=None, type=int, metavar="VER",
                        help="find books with Mobi header version (6 or 8)")
    parser.add_argument("-e", "--fix-extension",
                        help='rename file with correct extension .azw or'
                        '.azw3',
                        action="store_true")
    parser.add_argument("-n", "--rename",
                        help="rename MOBI files to 'author - title.ext'",
                        action="store_true")
    parser.add_argument("-l", "--locations",
                        help="print list of books with number of locations",
                        action="store_true")
    parser.add_argument("-b", "--ebok",
                        help="replace PDOC to EBOK (experimental)",
                        action="store_true")
    parser.add_argument('--log', nargs='?', metavar='DIR', const='1',
                        help='path to directory to write log file. If DIR is '
                        ' omitted write log to directory with epub files')
    args = parser.parse_args()

    if args.log == '1':
        st = datetime.now().strftime('%Y%m%d%H%M%S')
        sys.stdout = Logger(os.path.join(args.directory, 'eQM-' + st + '.log'))
    elif args.log != '1' and args.log is not None:
        st = datetime.now().strftime('%Y%m%d%H%M%S')
        sys.stdout = Logger(os.path.join(args.log, 'eQM-' + st + '.log'))

    if args.fix_extension:
        fix_extension(args.directory)
    else:
        mobi_check(args.directory)
