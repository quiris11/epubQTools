#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#


import os
import sys
import tempfile
import subprocess
import shutil
import struct
import json

SFENC = sys.getfilesystemencoding()


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
                                       PalmDB.first_pdb_record + secno * 8)
        if secno == self.nsec - 1:
            secend = len(self.data)
        else:
            secend, = struct.unpack_from(
                '>L', self.data,
                PalmDB.first_pdb_record + (secno + 1) * 8
            )
        return secstart, secend

    def readsection(self, secno):
        if secno < self.nsec:
            secstart, secend = self.getsecaddr(secno)
            return self.data[secstart:secend]
        return ''

    def getnumsections(self):
        return self.nsec


def get_mobi_exth(search_id, mobi_content):
    ll = []
    exth_begin = mobi_content.find('EXTH')
    exth_header = mobi_content[exth_begin:]
    count_items, = struct.unpack('>L', exth_header[8:12])
    pos = 12
    for _ in range(count_items):
        id, size = struct.unpack('>LL', exth_header[pos:pos + 8])
        exth_record = exth_header[pos + 8: pos + size]
        if id == search_id:
            ll.append(exth_record)
        pos += size
    return ll


def get_mobi_title(mobi_content):
    pp = PalmDB(mobi_content)
    header = pp.readsection(0)
    # title
    toff, tlen = struct.unpack('>II', header[0x54:0x5c])
    tend = toff + tlen
    title = header[toff:tend]
    return title


def write_meta(metaf, mobi_file):
    with open(mobi_file, 'rb') as f:
            mobi_content = f.read()
            title = get_mobi_title(mobi_content)
            authors = get_mobi_exth(100, mobi_content)
    with open(metaf, 'r+') as f:
        fs = f.read()
        fs = fs.replace('"title":""', '"title":%s' % json.dumps(title))
        fs = fs.replace('"authorList":null',
                        '"authorList":%s' % json.dumps(authors))
        f.seek(0)
        f.truncate()
        f.write(fs)


def to_azk(root, f, force):
    mobisourcefile = os.path.splitext(f)[0] + '.mobi'
    newazkfile = os.path.splitext(f)[0] + '.azk'
    azktempdir = tempfile.mkdtemp(suffix='', prefix='quiris-azk-')
    if not force:
        if os.path.isfile(os.path.join(root, newazkfile)):
            print('* Skipping previously generated _moh file: ' +
                  newazkfile)
            return 0
    print('')
    print('* AZKcreator: Converting file: ' + os.path.splitext(
        f
    )[0] + '.mobi')
    if sys.platform == 'win32':
        sys.exit()
    else:
        azkapp = '/Applications/Kindle Previewer 3.app/Contents/'\
            'MacOS/lib/azkcreator'
    if not os.path.isfile(os.path.join(
        root, mobisourcefile
    ).encode(SFENC)):
        sys.exit('* MOBI file does not exist. Giving up...')
    proc = subprocess.Popen([
        os.path.join(azkapp).encode(SFENC),
        '--no-validation', '--source',
        os.path.join(root, mobisourcefile).encode(SFENC),
        '--target', azktempdir
    ], stdout=subprocess.PIPE).communicate()[0]
    for ln in proc.splitlines():
        if ln != '':
            print(' ', ln)
    write_meta(os.path.join(
        azktempdir, os.listdir(azktempdir)[0], 'x', 'y', 'book',
        'metadata.jsonp'
    ), os.path.join(root, mobisourcefile).encode(SFENC))
    source_dir = os.path.join(
        azktempdir, os.listdir(azktempdir)[0], 'x', 'y', 'book'
    )
    shutil.make_archive(os.path.join(root, newazkfile),
                        'zip', source_dir)
    try:
        os.rename(os.path.join(root, newazkfile + '.zip'),
                  os.path.join(root, newazkfile))
    except OSError:
        print('* Renaming file failed...')
    # clean up temp files
    for p in os.listdir(os.path.join(azktempdir, os.pardir)):
        if 'quiris-azk-' in p:
            if os.path.isdir(os.path.join(azktempdir, os.pardir, p)):
                shutil.rmtree(os.path.join(azktempdir, os.pardir, p))
