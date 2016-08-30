#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

from __future__ import print_function
import hashlib
import os
import re
import tempfile
import shutil
import subprocess
import sys
import zipfile
import uuid
import unicodedata
import StringIO

from pkgutil import get_data
from urllib import unquote
from itertools import cycle
from lib.htmlconstants import entities
from lib.hyphenator import Hyphenator
from lib.beautify_book import beautify_book

try:
    from lxml import etree
except ImportError as e:
    sys.exit('! CRITICAL! ' + str(e).decode(sys.getfilesystemencoding()))

# set up recover parser for malformed XML
recover_parser = etree.XMLParser(encoding='utf-8', recover=True)

if not hasattr(sys, 'frozen'):
    dic_tmp_dir = tempfile.mkdtemp(suffix='', prefix='epubQTools-tmp-')
    dic_name = os.path.join(dic_tmp_dir, 'hyph_pl_PL.dic')
    try:
        with open(dic_name, 'wb') as f:
            data = get_data('lib', 'resources/dictionaries/hyph_pl_PL.dic')
            f.write(data)
        hyph = Hyphenator(dic_name)
    finally:
        shutil.rmtree(dic_tmp_dir)
else:
    hyph = Hyphenator(os.path.join(
        os.path.dirname(sys.executable), 'resources',
        'dictionaries', 'hyph_pl_PL.dic'
    ))
MY_LANGUAGE = 'pl'
MY_LANGUAGE2 = 'pl-PL'
HYPHEN_MARK = u'\u00AD'

HOME = os.path.expanduser("~")
DTD = ('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
       '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
DTDN = '<!DOCTYPE html>'
OPFNS = {'opf': 'http://www.idpf.org/2007/opf'}
XHTMLNS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
DCNS = {'dc': 'http://purl.org/dc/elements/1.1/'}
NCXNS = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
SVGNS = {'svg': 'http://www.w3.org/2000/svg'}
ADOBE_OBFUSCATION = 'http://ns.adobe.com/pdf/enc#RC'
IDPF_OBFUSCATION = 'http://www.idpf.org/2008/embedding'
CRNS = {'cr': 'urn:oasis:names:tc:opendocument:xmlns:container'}
SFENC = sys.getfilesystemencoding()


def set_dtd(opftree):
    version = opftree.xpath('//opf:package',
                            namespaces=OPFNS)[0].get('version')
    if version == '3.0':
        return DTDN
    else:
        return DTD


def rename_files(opf_path, _root, _epubfile, _filename, _file_dec):
    import unicodedata

    def strip_accents(text):
        return ''.join(c for c in unicodedata.normalize(
            'NFKD', text
        ) if unicodedata.category(c) != 'Mn')

    if _filename.endswith('_moh.epub'):
        return 0
    try:
        opftree = etree.fromstring(_epubfile.read(opf_path))
    except etree.XMLSyntaxError, e:
        print('! CRITICAL! XML file "%s" is not well '
              'formed: "%s"' % (os.path.basename(opf_path),
                                str(e).decode(SFENC)))
        opfstring = StringIO.StringIO(_epubfile.read(opf_path))
        try:
            opftree = etree.parse(opfstring, recover_parser)
        except etree.XMLSyntaxError:
            return None
    try:
        tit = etree.XPath('//dc:title/text()', namespaces=DCNS)(opftree)[0]
    except:
        print('! ERROR! Renaming file "%s" failed - dc:title (book title) '
              'not found.' % _file_dec)
        return 0
    crs = etree.XPath('//dc:creator/text()', namespaces=DCNS)(opftree)
    if len(crs) == 0:
        print('! ERROR! Renaming file "%s" failed - dc:creator (book author) '
              'not found.' % _file_dec)
        return 0
    else:
        cr = ''
        for c in crs:
            cr = cr + ' ' + c
        cr = cr[1:]
    if tit.isupper():
        tit = tit.title()
    if cr.isupper():
        cr = cr.title()
    tit = tit.replace('\n', ' ').replace('\r', ' ').strip()
    cr = cr.replace('\n', ' ').replace('\r', ' ').strip()
    if cr == '':
        print('! ERROR! Renaming file "%s" failed - dc:creator (book author) '
              'is empty.' % _file_dec)
        return 0
    if tit == '':
        print('! ERROR! Renaming file "%s" failed - dc:title (book title) '
              'is empty.' % _file_dec)
        return 0
    nfname = strip_accents(unicode(cr + ' - ' + tit))
    nfname = nfname.replace(u'\u2013', '-').replace('/', '_')\
                   .replace(':', '_').replace(u'\u0142', 'l')\
                   .replace(u'\u0141', 'L')
    nfname = "".join(x for x in nfname if (
        x.isalnum() or x.isspace() or x in ('_', '-', '.')
    ))
    is_renamed = False
    counter = 1
    while True:
        if _filename == (nfname + '.epub'):
            is_renamed = False
            break
        elif _filename == (nfname + ' (' + str(counter - 1) + ').epub'):
            is_renamed = False
            break
        elif not os.path.exists(os.path.join(_root, nfname + '.epub')):
            _epubfile.close()
            os.rename(os.path.join(_root, _filename),
                      os.path.join(_root, nfname + '.epub'))
            print('* Renamed file "%s" to "%s.epub".' % (
                _file_dec, nfname
            ))
            is_renamed = True
            break
        elif not os.path.exists(os.path.join(_root, nfname + ' (' +
                                str(counter) + ').epub')):
            _epubfile.close()
            os.rename(os.path.join(_root, _filename),
                      os.path.join(_root, nfname + ' (' + str(counter) +
                                   ').epub'))
            print('* Renamed file "%s" to "%s (%s).epub"' % (
                _file_dec, nfname, str(counter)
            ))
            is_renamed = True
            break
        else:
            counter += 1
    if not is_renamed:
        print('= Renaming file "%s" is not needed.' % _file_dec)


def check_font(path):
    with open(path, 'rb') as f:
        raw = f.read()
    signature = raw[:4]
    return (signature in {b'\x00\x01\x00\x00', b'OTTO'}, signature)


# based on calibri work
def unquote_urls(tree):
    def get_href(item):
        raw = unquote(item.get('href', ''))
        if not isinstance(raw, unicode):
            raw = raw.decode('utf-8')
        return raw
    for item in tree.xpath('//opf:item', namespaces=OPFNS):
        item.set('href', get_href(item))
    for item in tree.xpath('//opf:reference', namespaces=OPFNS):
        item.set('href', get_href(item))
    return tree


def remove_node(node):
    parent = node.getparent()
    index = parent.index(node)
    if node.tail is not None:
        if index == 0:
            try:
                parent.text += node.tail
            except TypeError:
                parent.text = node.tail
        else:
            try:
                parent[index - 1].tail += node.tail
            except TypeError:
                parent[index - 1].tail = node.tail
    parent.remove(node)


# based on calibri work
def process_encryption(encfile, opftree, fontdir):
    print('* Font decrypting started...')
    root = etree.parse(encfile)
    for em in root.xpath(
            'descendant::*[contains(name(), "EncryptionMethod")]'
    ):
        algorithm = em.get('Algorithm', '')
        if algorithm not in {ADOBE_OBFUSCATION, IDPF_OBFUSCATION}:
            return False
        cr = em.getparent().xpath(
            'descendant::*[contains(name(), "CipherReference")]'
        )[0]
        uri = cr.get('URI')
        font_path = os.path.abspath(os.path.join(os.path.dirname(encfile),
                                    '..', *uri.split('/')))
        key = find_encryption_key(opftree, algorithm)
        if (key and os.path.exists(font_path)):
            decrypt_font(font_path, key, algorithm, fontdir)
    return True


def find_encryption_key(opftree, method):
    uid = None
    if method == ADOBE_OBFUSCATION:
        # find first UUID URN-based unique identifier
        for dcid in opftree.xpath("//dc:identifier", namespaces=DCNS):
            if 'urn:uuid:' in unicode(dcid.text):
                uid = dcid.text
                break
        if uid is None:
            print('* UUID URN-based unique identifier in content.opf does '
                  'not found')
            return uid
        uid = uid.replace('\x20', '').replace('\x09', '').\
            replace('\x0D', '').replace('\x0A', '').\
            replace('-', '').replace('urn:uuid:', '').\
            replace(':', '')
        uid = bytes(uid)
        uid = uuid.UUID(uid).bytes
    elif method == IDPF_OBFUSCATION:
        # find unique-identifier
        uniq_id = opftree.xpath('//opf:package',
                                namespaces=OPFNS)[0].get('unique-identifier')
        if uniq_id is not None:
            for elem in opftree.xpath("//dc:identifier", namespaces=DCNS):
                if elem.get('id') == uniq_id:
                    uid = elem.text
                    break
        if uid is None:
            print('* Unique identifier in content.opf does not found')
            return uid
        uid = uid.replace('\x20', '').replace('\x09', '').\
            replace('\x0D', '').replace('\x0A', '')
        uid = hashlib.sha1(uid).digest()
    return uid


# based on calibri work
def decrypt_font(path, key, method, fontdir):
    global qfixerr
    if method == ADOBE_OBFUSCATION:
        crypt_len = 1024
    elif method == IDPF_OBFUSCATION:
        crypt_len = 1040
    with open(path, 'rb') as f:
        raw = f.read()
    crypt = bytearray(raw[:crypt_len])
    key = cycle(iter(bytearray(key)))
    decrypt = bytes(bytearray(x ^ key.next() for x in crypt))
    print('* Starting decryption of font file "%s"...'
          % os.path.basename(path), end=' ')
    with open(path, 'wb') as f:
        f.write(decrypt)
        f.write(raw[crypt_len:])
    is_font, signature = check_font(path)
    if not is_font:
        print('FAILED!')
    else:
        print('OK! Decrypted.')
    if not is_font and not ('.ttc' in path):
        print('* Starting replace procedure for encrypted file "%s" with font'
              ' from system directory...' % os.path.basename(path), end=' ')
        if fontdir is None:
            fontdir = ''
        if sys.platform == 'win32':
            font_paths = [
                os.path.abspath(os.path.join(os.environ['WINDIR'], 'Fonts')),
                fontdir
            ]
        else:
            font_paths = [os.path.join(os.path.sep, 'Library', 'Fonts'),
                          os.path.join(HOME, 'Library', 'Fonts'),
                          fontdir]
        for font_path in font_paths:
            if os.path.exists(os.path.join(font_path,
                              os.path.basename(path))):
                os.remove(path)
                shutil.copyfile(
                    os.path.join(font_path, os.path.basename(path)),
                    path
                )
        is_font, signature = check_font(path)
        if is_font:
            print('OK! Replaced.')
        else:
            qfixerr = True
            print('FAILED! Substitute did NOT found.')


def find_and_replace_fonts(opftree, rootepubdir, fontdir):
    items = etree.XPath('//opf:item[@href]', namespaces=OPFNS)(opftree)
    for item in items:
        if (item.get('href').lower().endswith('.otf') or
                item.get('href').lower().endswith('.ttf')):
            actual_font_path = os.path.join(rootepubdir, item.get('href'))
            replace_font(actual_font_path, fontdir)


def xml2html_extension(opftree, rootepubdir):
    is_xml_ext_fixed = False
    items = etree.XPath('//opf:item[@href]', namespaces=OPFNS)(opftree)
    for i in items:
        if (i.get('media-type') == 'application/xhtml+xml' and
                i.get('href').lower().endswith('.xml')):
            is_xml_ext_fixed = True
            os.rename(
                os.path.join(rootepubdir, i.get('href')),
                os.path.join(rootepubdir, i.get('href')[:-4] + '.html')
            )
            i.set('href', i.get('href')[:-4] + '.html')
    items = etree.XPath('//opf:reference[@href]', namespaces=OPFNS)(opftree)
    for i in items:
        url = i.get('href')
        if (
            not os.path.isfile(os.path.join(rootepubdir, url)) and
            os.path.isfile(os.path.join(rootepubdir, url[:-4] + '.html')) and
            url.lower().endswith('.xml')
        ):
            i.set('href', i.get('href')[:-4] + '.html')
    return opftree, is_xml_ext_fixed


def xml2html_fix_references(tree, file_dir, ncx):
    if ncx:
        items = etree.XPath('//ncx:content', namespaces=NCXNS)(tree)
    else:
        items = etree.XPath('//xhtml:*[@href or @src]',
                            namespaces=XHTMLNS)(tree)
    exclude_urls = ('http://', 'https://', 'mailto:', 'tel:', 'data:', '#')
    for u in items:
        if u.get('src'):
            url = u.get('src')
        elif u.get('href'):
            url = u.get('href')
        if url.lower().startswith(exclude_urls):
            continue
        url = unquote(url)
        if '#' in url:
            frag_url = '#' + url.split('#')[1]
            url = url.split('#')[0]
        else:
            frag_url = ''
        if (
            not os.path.isfile(os.path.join(file_dir, url)) and
            os.path.isfile(os.path.join(file_dir, url[:-4] + '.html')) and
            url.lower().endswith('.xml')
        ):
            if u.get('src'):
                u.set('src', url[:-4] + '.html' + frag_url)
            elif u.get('href'):
                u.set('href', url[:-4] + '.html' + frag_url)
    return tree


def fix_ncx(opftree, rootepubdir):
    try:
        toc_ncx_file = etree.XPath(
            '//opf:item[@media-type="application/x-dtbncx+xml"]',
            namespaces=OPFNS
        )(opftree)[0].get('href')
    except IndexError:
        return None
    ncxtree = etree.parse(
        os.path.join(rootepubdir, toc_ncx_file),
        parser=etree.XMLParser(recover=True)
    )
    ncxtree = xml2html_fix_references(ncxtree, rootepubdir, True)

    # fix incorrect ids set by one publisher
    navPoints = etree.XPath('//ncx:navPoint', namespaces=NCXNS)(ncxtree)
    for i in navPoints:
        chid = i.get('id')
        if chid[0].isdigit():
            chid = 'eqt' + chid
        i.set('id', re.sub('[^0-9a-zA-Z_.-]+', '', chid))

    # write all NCX changes back to file
    with open(os.path.join(rootepubdir, toc_ncx_file), 'w') as f:
        f.write(etree.tostring(ncxtree.getroot(), pretty_print=True,
                standalone=False, xml_declaration=True, encoding='utf-8'))


def replace_font(actual_font_path, fontdir):
    global qfixerr
    if fontdir is None:
        fontdir = ''
    if sys.platform == 'win32':
        font_paths = [
            os.path.abspath(os.path.join(os.environ['WINDIR'], 'Fonts')),
            fontdir
        ]
    else:
        font_paths = [os.path.join(os.path.sep, 'Library', 'Fonts'),
                      os.path.join(HOME, 'Library', 'Fonts'),
                      fontdir]
    font_replaced = False
    for font_path in font_paths:
        if os.path.exists(
                os.path.join(font_path, os.path.basename(actual_font_path))
        ):
            os.remove(actual_font_path)
            shutil.copyfile(
                os.path.join(font_path, os.path.basename(actual_font_path)),
                actual_font_path
            )
            font_replaced = True
    if font_replaced:
        print('* Font replaced: ' + os.path.basename(actual_font_path))
    else:
        qfixerr = True
        print('* Font "%s" not replaced. Substitute did NOT found.'
              % os.path.basename(actual_font_path))


def unpack_epub(source_epub):
    epubzipfile = zipfile.ZipFile(source_epub)
    tempdir = tempfile.mkdtemp(suffix='', prefix='epubQTools-tmp-')
    epubzipfile.extractall(tempdir)
    try:
        os.remove(os.path.join(tempdir, 'mimetype'))
    except OSError:
        pass
    for f in epubzipfile.namelist():
        if '../' in f:
            orgf = os.path.join(tempdir, f.replace('../', ''))
            newf = os.path.join(tempdir, os.path.relpath(f))
            shutil.move(orgf, newf)
    return tempdir


def pack_epub(output_filename, source_dir):
    with zipfile.ZipFile(output_filename, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
    relroot = source_dir
    with zipfile.ZipFile(output_filename, "a", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(source_dir):
            for f in files:
                filename = os.path.join(root, f)
                if os.path.isfile(filename):
                    arcname = os.path.join(os.path.relpath(root, relroot),
                                           f)
                    if sys.platform == 'darwin':
                        arcname = unicodedata.normalize(
                            'NFC', unicode(arcname, 'utf-8')
                        ).encode('utf-8')
                    z.write(filename, arcname.decode(SFENC))


def clean_temp(sourcedir):
    for p in os.listdir(os.path.join(sourcedir, os.pardir)):
            if 'epubQTools-tmp-' in p:
                if os.path.isdir(os.path.join(sourcedir, os.pardir, p)):
                    try:
                        shutil.rmtree(os.path.join(sourcedir, os.pardir, p))
                    except:
                        if sys.platform == 'win32':
                            os.system('rmdir /S /Q \"{}\"'.format(
                                os.path.join(sourcedir, os.pardir, p)
                            ))
                        else:
                            raise


def find_roots(tempdir):
    global qfixerr
    try:
        cr_tree = etree.parse(os.path.join(tempdir, 'META-INF',
                                           'container.xml'))
        opf_path = cr_tree.xpath('//cr:rootfile',
                                 namespaces=CRNS)[0].get('full-path')
    except:
        # try to find OPF file other way and rebuild META-INF/container.xml
        for r, d, fs in os.walk(tempdir):
            for f in fs:
                if f.endswith('.opf'):
                    reldir = os.path.relpath(r, tempdir)
                    if reldir == '.':
                        reldir = ''
                    cont_file = os.path.join(tempdir, 'META-INF',
                                             'container.xml')
                    cr_tree = etree.fromstring(
                        get_data('lib', 'resources/container.xml')
                    )
                    cr_tree.xpath(
                        '//cr:rootfile',
                        namespaces=CRNS
                    )[0].set('full-path', os.path.join(reldir, f))
                    if not os.path.exists(os.path.dirname(cont_file)):
                        os.makedirs(os.path.dirname(cont_file))
                    with open(cont_file, 'w') as c:
                        c.write(
                            etree.tostring(
                                cr_tree,
                                pretty_print=True,
                                standalone=False,
                                xml_declaration=True,
                                encoding='utf-8'
                            )
                        )
                    return os.path.dirname(f), f, True
        print('* Parsing container.xml failed. Not an EPUB file?')
        qfixerr = True
        return None, None, False
    return os.path.dirname(opf_path), opf_path, False


def find_xhtml_files(rootepubdir, opftree):
    global qfixerr
    try:
        xhtml_items = etree.XPath(
            '//opf:item[@media-type="application/xhtml+xml" or '
            '@media-type="text/html"]',
            namespaces=OPFNS
        )(opftree)
    except:
        print('* XHTML files not found...')
        qfixerr = True
    xhtml_files = []
    xhtml_file_paths = []
    for xhtml_item in xhtml_items:
        xhtml_files.append(os.path.join(rootepubdir, xhtml_item.get('href')))
        xhtml_file_paths.append(xhtml_item.get('href'))
    return xhtml_files, xhtml_file_paths


def hyphenate_and_fix_conjunctions(source_file, hyphen_mark, hyph,
                                   dont_hyph_headers):
    # set correct xml:lang attribute for html tag

    def fix_hanging_single_conjunctions_and_place_back(tel, txt):
        newt = re.sub(r'(?<=\s\w)\s+', u'\u00A0', txt)
        if tel.is_text:
            parent.text = newt
        elif tel.is_tail:
            parent.tail = newt

    html_tag = source_file.xpath('//xhtml:html', namespaces=XHTMLNS)[0]
    html_tag.attrib['{http://www.w3.org/XML/1998/namespace}lang'] = MY_LANGUAGE
    if 'lang' in html_tag.attrib:
        del html_tag.attrib['lang']

    try:
        texts = etree.XPath(
            '//xhtml:body//text()',
            namespaces=XHTMLNS
        )(source_file)
    except:
        print('* No texts found...')
    # Tag list used to ignore hyphenation
    ignore_list = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'title']
    for t in texts:
        parent = t.getparent()
        if dont_hyph_headers:
            # if parent in ignore_list do not hyphenate
            try:
                if (parent.tag.replace('{http://www.w3.org/1999/xhtml}',
                                       '') in ignore_list):
                    fix_hanging_single_conjunctions_and_place_back(t, t)
                    continue
            except AttributeError:
                continue

            # define entire list of ancestors of parent tag without namespace
            # for fixing such problem: <h1><a>text</a></h1>
            ancestors = [ancestor.xpath(
                'local-name()'
            ) for ancestor in parent.iterancestors()]

            # create list with duplicates of ancestor list and ignore list
            tags = filter(set(ancestors).__contains__, ignore_list)
            if len(tags) > 0:
                fix_hanging_single_conjunctions_and_place_back(t, t)
                continue
        lang = parent.get('{http://www.w3.org/XML/1998/namespace}lang')
        if lang is not None and lang != MY_LANGUAGE and lang != MY_LANGUAGE2:
            continue
        newt = ''
        wlist = re.compile(r'\w+|[^\w]', re.UNICODE).findall(t)
        for w in wlist:
            newt += hyph.inserted(w, hyphen_mark)
        fix_hanging_single_conjunctions_and_place_back(t, newt)
    return source_file


def fix_styles(source_file):
    try:
        links = etree.XPath(
            '//xhtml:link',
            namespaces=XHTMLNS
        )(source_file)
    except:
        print('* No links found...')
    for link in links:
        if link.get('type') is None:
            link.set('type', 'text/css')
    return source_file


def fix_nav_in_cover_file(opftree, tempdir):

    def move_nav_to_new_toc(tempdir, cover_href, toc_href):
        print('* Moving problematic nav element from a cover file '
              'to a toc file...')
        cover_tree = etree.parse(os.path.join(tempdir, cover_href),
                                 parser=etree.XMLParser(recover=True))
        toc_tree = etree.parse(os.path.join(tempdir, toc_href),
                               parser=etree.XMLParser(recover=True))
        nav = etree.XPath('//xhtml:nav',
                          namespaces=XHTMLNS)(cover_tree)[0]
        remove_node(nav)
        etree.XPath(
            '//xhtml:body',
            namespaces=XHTMLNS
        )(toc_tree)[0].append(nav)
        with open(os.path.join(tempdir, cover_href),
                  "w") as f:
            f.write(etree.tostring(
                cover_tree,
                pretty_print=True,
                xml_declaration=True,
                standalone=False,
                encoding="utf-8",
                doctype=set_dtd(opftree)
            ))
        with open(os.path.join(tempdir, toc_href),
                  "w") as f:
            f.write(etree.tostring(
                toc_tree,
                pretty_print=True,
                xml_declaration=True,
                standalone=False,
                encoding="utf-8",
                doctype=set_dtd(opftree)
            ))
    if opftree.xpath('//opf:package', namespaces=OPFNS)[0].get(
        'version'
    ) != '3.0':
        return opftree
    reftocs = etree.XPath('//opf:reference[@type="toc"]',
                          namespaces=OPFNS)(opftree)
    refcovers = etree.XPath('//opf:reference[@type="cover"]',
                            namespaces=OPFNS)(opftree)
    if len(refcovers) != 1:
        return opftree
    else:
        cover_href = refcovers[0].get('href')
    if len(reftocs) != 1:
        return opftree
    else:
        toc_href = reftocs[0].get('href')
    items = etree.XPath('//opf:item', namespaces=OPFNS)(opftree)
    for i in items:
        if i.get('href') == cover_href and i.get('properties') == 'nav':
            i.attrib.pop('properties')
            for e in items:
                if e.get('href') == toc_href:
                    e.set('properties', 'nav')
                    move_nav_to_new_toc(tempdir, cover_href, toc_href)
                    break
            break
    return opftree


def fix_html_toc(soup, tempdir, xhtml_files, xhtml_file_paths):
    reftocs = etree.XPath('//opf:reference[@type="toc"]',
                          namespaces=OPFNS)(soup)
    if len(reftocs) == 0:
        html_toc = None
        for xhtml_file in xhtml_files:
            try:
                xhtmltree = etree.parse(xhtml_file,
                                        parser=etree.XMLParser(recover=True))
            except (etree.XMLSyntaxError, IOError):
                continue
            alltexts = etree.XPath('//text()', namespaces=XHTMLNS)(xhtmltree)
            alltext = ' '.join(alltexts)
            if alltext.find(u'Spis treści') != -1:
                html_toc = xhtml_file
                break
        if html_toc is not None:
            for xhtml_file_path in xhtml_file_paths:
                if xhtml_file_path.find(os.path.basename(html_toc)) != -1:
                    html_toc = xhtml_file_path
                    break
            newtocreference = etree.Element(
                '{http://www.idpf.org/2007/opf}reference', title='TOC',
                type='toc', href=html_toc
            )
        else:
            print('* Fix for a missing HTML TOC file. Generating a new TOC...')
            parser = etree.XMLParser(remove_blank_text=True)
            if not hasattr(sys, 'frozen'):
                transform = etree.XSLT(etree.fromstring(get_data('lib',
                                       'resources/ncx2end-0.2.xsl')))
            else:
                transform = etree.XSLT(etree.parse(os.path.join(
                    os.path.dirname(sys.executable), 'resources',
                    'ncx2end-0.2.xsl'
                )))
            try:
                toc_ncx_file = etree.XPath(
                    '//opf:item[@media-type="application/x-dtbncx+xml"]',
                    namespaces=OPFNS
                )(soup)[0].get('href')
            except IndexError:
                return soup
            try:
                ncxtree = etree.parse(os.path.join(tempdir, toc_ncx_file),
                                      parser)
            except:
                return soup
            result = transform(ncxtree)
            ncx_contents = ncxtree.xpath('//ncx:content', namespaces=NCXNS)
            if all(
                os.path.dirname(x.get('src')) == os.path.dirname(
                    ncx_contents[0].get('src')
                ) for x in ncx_contents
            ):
                try:
                    textdir = os.path.dirname(ncx_contents[0].get('src'))
                except IndexError:
                    textdir = ''
                anchs = result.xpath('//xhtml:a', namespaces=XHTMLNS)
                for a in anchs:
                    a.set('href', os.path.basename(a.get('href')))
            else:
                textdir = ''
            head = result.xpath('//xhtml:head', namespaces=XHTMLNS)[0]
            for ci in soup.xpath('//opf:item[@media-type="text/css"]',
                                 namespaces=OPFNS):
                head.append(etree.fromstring(
                    '<link href="%s" rel="stylesheet" type="text/css" />'
                    % os.path.join(
                        os.path.relpath(tempdir,
                                        os.path.join(tempdir, textdir)),
                        ci.get('href')
                    ).replace('\\', '/')
                ))
            with open(os.path.join(tempdir, textdir, 'epubQTools-toc.xhtml'),
                      "w") as f:
                f.write(etree.tostring(
                    result,
                    pretty_print=True,
                    xml_declaration=True,
                    standalone=False,
                    encoding="utf-8",
                    doctype=set_dtd(soup)
                ))
            newtocmanifest = etree.Element(
                '{http://www.idpf.org/2007/opf}item',
                attrib={'media-type': 'application/xhtml+xml',
                        'href': os.path.join(
                            textdir, 'epubQTools-toc.xhtml'
                        ).replace('\\', '/'),
                        'id': 'epubQTools-toc'}
            )
            soup.xpath('//opf:manifest',
                       namespaces=OPFNS)[0].append(newtocmanifest)
            newtocspine = etree.Element(
                '{http://www.idpf.org/2007/opf}itemref',
                idref='epubQTools-toc'
            )
            soup.xpath('//opf:spine', namespaces=OPFNS)[0].append(newtocspine)
            newtocreference = etree.Element(
                '{http://www.idpf.org/2007/opf}reference',
                title='TOC',
                type='toc',
                href=os.path.join(textdir,
                                  'epubQTools-toc.xhtml').replace('\\', '/')
            )
        try:
            soup.xpath('//opf:guide',
                       namespaces=OPFNS)[0].append(newtocreference)
        except IndexError:
            newguide = etree.Element('{http://www.idpf.org/2007/opf}guide')
            newguide.append(newtocreference)
            soup.xpath('//opf:package',
                       namespaces=OPFNS)[0].append(newguide)
    return soup


def fix_mismatched_covers(opftree, tempdir):
    global qfixerr
    refcvs = opftree.xpath('//opf:reference[@type="cover"]', namespaces=OPFNS)
    if len(refcvs) > 1:
        print('* Too many cover references in OPF. Giving up...')
        qfixerr = True
        return opftree
    try:
        cover_xhtml_file = os.path.join(tempdir, refcvs[0].get('href'))
    except:
        print('* HTML cover reference not found. Giving up...')
        qfixerr = True
        return opftree
    try:
        xhtmltree = etree.parse(cover_xhtml_file,
                                parser=etree.XMLParser(recover=True))
    except:
        print('* Unable to parse HTML cover file. Giving up...')
        qfixerr = True
        return opftree
    if not etree.tostring(xhtmltree):
        print('* HTML cover file is empty...')
        qfixerr = True
        return opftree
    allimgs = etree.XPath('//xhtml:img', namespaces=XHTMLNS)(xhtmltree)
    if not allimgs:
        allsvgimgs = etree.XPath('//svg:image', namespaces=SVGNS)(xhtmltree)
        len_svg_images = len(allsvgimgs)
    else:
        len_svg_images = 0
    if len(allimgs) != 1 and len_svg_images != 1:
        print('* HTML cover should have only one image. Giving up...')
        qfixerr = True
        return opftree
    if allimgs:
        html_cover_img_file = allimgs[0].get('src').split('/')[-1]
    elif allsvgimgs:
        html_cover_img_file = allsvgimgs[0].get(
            '{http://www.w3.org/1999/xlink}href'
        ).split('/')[-1]
    try:
        meta_cover_id = opftree.xpath(
            '//opf:meta[@name="cover"]',
            namespaces=OPFNS
        )[0].get('content')
    except IndexError:
        meta_cover_id = ''
    try:
        meta_cover_image_file = opftree.xpath(
            '//opf:item[@id="' + meta_cover_id + '"]',
            namespaces=OPFNS
        )[0].get('href').split('/')[-1]
    except IndexError:
        if html_cover_img_file is not None:
            for i in opftree.xpath('//opf:item', namespaces=OPFNS):
                if html_cover_img_file in i.get('href'):
                    opftree = set_cover_meta_elem(opftree, i.get('id'))
        meta_cover_image_file = html_cover_img_file
    if html_cover_img_file != meta_cover_image_file:
        print('* Mismatched meta and HTML covers. Fixing...')
        allimgs[0].set(
            'src',
            allimgs[0].get('src').replace(
                html_cover_img_file, meta_cover_image_file
            )
        )
        with open(cover_xhtml_file, "w") as f:
            f.write(etree.tostring(
                xhtmltree,
                pretty_print=True,
                xml_declaration=True,
                standalone=False,
                encoding="utf-8",
                doctype=set_dtd(opftree))
            )
    return opftree


def set_cover_guide_ref(_xhtml_files, _itemcoverhref, _xhtml_file_paths,
                        _soup):
    cover_file = None
    for xhtml_file in _xhtml_files:
        xhtmltree = etree.parse(xhtml_file,
                                parser=etree.XMLParser(recover=True))

        allimgs = etree.XPath('//xhtml:img', namespaces=XHTMLNS)(xhtmltree)
        for img in allimgs:
            if (img.get('src').find(_itemcoverhref) != -1 or
                    img.get('src').lower().find('okladka_fmt') != -1):
                cover_file = xhtml_file
                break
        allsvgimgs = etree.XPath('//svg:image', namespaces=SVGNS)(xhtmltree)
        for svgimg in allsvgimgs:
            svg_img_href = svgimg.get('{http://www.w3.org/1999/xlink}href')
            if (svg_img_href.find(_itemcoverhref) != -1 or
                    svg_img_href.lower().find('okladka_fmt') != -1):
                cover_file = xhtml_file
                break
    if cover_file is not None:
        for xhtml_file_path in _xhtml_file_paths:
            if xhtml_file_path.find(os.path.basename(cover_file)) != -1:
                cover_file = xhtml_file_path
                break
        _newcoverreference = etree.Element(
            '{http://www.idpf.org/2007/opf}reference', title='Cover',
            type="cover", href=cover_file
        )
        _refcovers = etree.XPath('//opf:reference[@type="cover"]',
                                 namespaces=OPFNS)(_soup)
        try:
            if len(_refcovers) == 1:
                _refcovers[0].set('href', cover_file)
            else:
                _soup.xpath('//opf:guide',
                            namespaces=OPFNS)[0].append(_newcoverreference)
        except IndexError:
            newguide = etree.Element('{http://www.idpf.org/2007/opf}guide')
            newguide.append(_newcoverreference)
            _soup.xpath('//opf:package',
                        namespaces=OPFNS)[0].append(newguide)
    return _soup


def set_cover_meta_elem(_soup, _content):
    _metadatas = _soup.xpath('//opf:metadata', namespaces=OPFNS)
    _metacovers = _soup.xpath('//opf:meta[@name="cover"]', namespaces=OPFNS)
    if len(_metadatas) == 1 and len(_metacovers) == 0:
        _newmeta = etree.Element(
            '{http://www.idpf.org/2007/opf}meta',
            name='cover',
            content=_content
        )
        _metadatas[0].append(_newmeta)
    elif len(_metadatas) == 1 and len(_metacovers) == 1:
        _metacovers[0].set('content', _content)
    return _soup


def force_cover_find(_soup):
    print('* Trying to find cover image:', end=' ')
    images = etree.XPath('//opf:item[@media-type="image/jpeg"]',
                         namespaces=OPFNS)(_soup)
    if len(images) != 0:
        for imag in images:
            img = os.path.basename(imag.get('href')).lower()
            if 'cover' in img or 'okladka' in img:
                print('"%s" file found.' % img)
                return imag.get('href'), imag.get('id')
    print('NOT found!')
    return None, None


def remove_fonts(opftree, rootepubdir):
    print('* Removing all fonts...')
    for i in opftree.xpath('//opf:item[@href]', namespaces=OPFNS):
        if (i.get('href').lower().endswith('.otf') or
                i.get('href').lower().endswith('.ttf')):
            remove_node(i)
            os.remove(os.path.join(rootepubdir, i.get('href')))
    return opftree


def correct_mime_types(_soup):
    _items = etree.XPath('//opf:item[@href]', namespaces=OPFNS)(_soup)
    for _item in _items:
        if (
                (_item.get('href').lower().endswith('.otf') or
                    _item.get('href').lower().endswith('.ttf')) and
                _item.get('media-type') != 'application/vnd.ms-opentype'
        ):
            print('* Setting correct mime type "application/vnd.ms-opentype" '
                  'for font "%s"' % _item.get('href'))
            _item.set('media-type', 'application/vnd.ms-opentype')
        elif _item.get('media-type').lower() == 'text/html':
            _item.set('media-type', 'application/xhtml+xml')
    return _soup


def fix_various_opf_problems(soup, tempdir, xhtml_files,
                             xhtml_file_paths):

    soup = correct_mime_types(soup)

    # remove multiple dc:language
    lang_counter = 0
    for lang in soup.xpath("//dc:language", namespaces=DCNS):
        lang_counter = lang_counter + 1
        if lang_counter > 1:
            print('* Removing multiple language definitions...')
            lang.getparent().remove(lang)

    # set dc:language to my language
    for lang in soup.xpath("//dc:language", namespaces=DCNS):
        if lang is not None and lang.text != MY_LANGUAGE:
            print('* Correcting book language to: ' + MY_LANGUAGE)
            lang.text = MY_LANGUAGE

    # add missing dc:language
    if len(soup.xpath("//dc:language", namespaces=DCNS)) == 0:
        print('* Setting missing book language to: ' + MY_LANGUAGE)
        for metadata in soup.xpath("//opf:metadata", namespaces=OPFNS):
            newlang = etree.Element(
                '{http://purl.org/dc/elements/1.1/}language'
            )
            newlang.text = MY_LANGUAGE
            metadata.insert(0, newlang)

    # add missing meta cover and cover reference guide element
    metacovers = etree.XPath('//opf:meta[@name="cover"]',
                             namespaces=OPFNS)(soup)
    refcovers = etree.XPath('//opf:reference[@type="cover"]',
                            namespaces=OPFNS)(soup)
    if len(metacovers) == 1 and len(refcovers) == 0:
        # set missing cover reference guide element
        itemcovers = etree.XPath(
            '//opf:item[@id="' + metacovers[0].get('content') + '"]',
            namespaces=OPFNS
        )(soup)
        print('* Defining cover guide element...')
        try:
            itemcoverhref = os.path.basename(itemcovers[0].get('href'))
            soup = set_cover_guide_ref(
                xhtml_files, itemcoverhref, xhtml_file_paths, soup
            )
        except IndexError:
            print('* No cover images found...')
    elif len(metacovers) == 0 and len(refcovers) == 1:
        # set missing cover meta element
        cover_image = None
        try:
            coversoup = etree.parse(
                os.path.join(tempdir, refcovers[0].get('href')),
                parser=etree.XMLParser(recover=True)
            )
        except:
            coversoup = None
        if etree.tostring(coversoup) is not None:
            imgs = etree.XPath('//xhtml:img',
                               namespaces=XHTMLNS)(coversoup)
            if len(imgs) == 1:
                cover_image = imgs[0].get('src')
            images = etree.XPath('//svg:image',
                                 namespaces=SVGNS)(coversoup)
            if len(imgs) == 0 and len(images) == 1:
                cover_image = images[0].get(
                    '{http://www.w3.org/1999/xlink}href'
                )
        else:
            imag_href, imag_id = force_cover_find(soup)
            if imag_href is not None and imag_id is not None:
                soup = set_cover_guide_ref(
                    xhtml_files, imag_href, xhtml_file_paths, soup
                )
                soup = set_cover_meta_elem(soup, imag_id)
            else:
                print('* No cover images found...')
        if cover_image is not None:
            cib = os.path.basename(cover_image)
            cov_img_id = None
            for item in soup.xpath('//opf:item', namespaces=OPFNS):
                if cib in item.get('href'):
                    cov_img_id = item.get('href')
                    break
            if cov_img_id is not None:
                soup = set_cover_meta_elem(soup, cov_img_id)

    elif len(metacovers) == 0 and len(refcovers) == 0:
        imag_href, imag_id = force_cover_find(soup)
        if imag_href is not None and imag_id is not None:
            soup = set_cover_guide_ref(
                xhtml_files, imag_href, xhtml_file_paths, soup
            )
            soup = set_cover_meta_elem(soup, imag_id)
        else:
            print('* No cover images found...')

    # remove calibre staff
    for meta in soup.xpath("//opf:meta[starts-with(@name, 'calibre')]",
                           namespaces=OPFNS):
        meta.getparent().remove(meta)

    # remove sigil version
    for meta in soup.xpath("//opf:meta[@name='Sigil version']",
                           namespaces=OPFNS):
        meta.getparent().remove(meta)

    for dcid in soup.xpath(
            "//dc:identifier[@opf:scheme='calibre']",
            namespaces={'dc': 'http://purl.org/dc/elements/1.1/',
                        'opf': 'http://www.idpf.org/2007/opf'}
    ):
        dcid.getparent().remove(dcid)

    # remove empty tours element
    for i in soup.xpath('//opf:tours', namespaces=OPFNS):
        if len(list(i)) == 0:
            remove_node(i)

    # remove OPF remainings in EPUB 3.0 files
    try:
        book_ver = soup.xpath(
            '//opf:package', namespaces=OPFNS
        )[0].get('version')
    except:
        print("! No EPUB version found...")
        return soup
    if not book_ver == '3.0':
        return soup
    opfmetadata = soup.xpath('//opf:metadata', namespaces=OPFNS)[0]
    creators = soup.xpath('//dc:creator', namespaces=DCNS)
    counter = 0
    for c in creators:
        counter += 1
        if c.get('{http://www.idpf.org/2007/opf}role'):
            opf_role = c.get('{http://www.idpf.org/2007/opf}role')
            new_role = etree.Element(
                'meta',
                attrib={'refines': '#' + opf_role + str(counter),
                        'property': 'role',
                        'scheme': 'marc:relators'}
            )
            new_role.text = opf_role
            c.set('id', opf_role + str(counter))
            c.attrib.pop('{http://www.idpf.org/2007/opf}role')
            opfmetadata.append(new_role)
        if c.get('{http://www.idpf.org/2007/opf}file-as'):
            opf_file_as = c.get('{http://www.idpf.org/2007/opf}file-as')
            if c.get('id'):
                new_file_as = etree.Element(
                    'meta',
                    attrib={'refines': '#' + c.get('id'),
                            'property': 'file-as'}
                )
                new_file_as.text = opf_file_as
                c.attrib.pop('{http://www.idpf.org/2007/opf}file-as')
                opfmetadata.append(new_file_as)
            else:
                c.attrib.pop('{http://www.idpf.org/2007/opf}file-as')
    for i in soup.xpath('//dc:identifier', namespaces=DCNS):
        if i.text is None:
            continue
        scheme = i.get('{http://www.idpf.org/2007/opf}scheme')
        if scheme:
            if i.text.startswith('urn:'):
                i.attrib.pop('{http://www.idpf.org/2007/opf}scheme')
            else:
                i.text = 'urn:' + scheme.lower() + ':' + i.text
                i.attrib.pop('{http://www.idpf.org/2007/opf}scheme')
    return soup


def fix_meta_cover_order(soup):
    # name='cover' should be before content attribute
    for cover in soup.xpath('//opf:meta[@name="cover" and @content]',
                            namespaces=OPFNS):
        cover.set('content', cover.attrib.pop('content'))
    return soup


def fix_ncx_dtd_uid(opftree, tempdir):
    try:
        ncxfile = etree.XPath(
            '//opf:item[@media-type="application/x-dtbncx+xml"]',
            namespaces=OPFNS
        )(opftree)[0].get('href')
    except IndexError:
        return opftree
    try:
        ncxtree = etree.parse(os.path.join(tempdir, ncxfile))
    except:
        return opftree
    # remove empty dc:identifiers
    for i in opftree.xpath('//dc:identifier', namespaces=DCNS):
        if i.text is None:
            i.getparent().remove(i)
    uniqid = opftree.xpath('//opf:package',
                           namespaces=OPFNS)[0].get('unique-identifier')
    try:
        dc_identifier = opftree.xpath(
            '//dc:identifier[@id="' + str(uniqid) + '"]/text()',
            namespaces=DCNS
        )[0]
    except IndexError:
        uniqid = None
        id_found = False
    if uniqid is None:
        dcidentifiers = opftree.xpath('//dc:identifier', namespaces=DCNS)
        for dcid in dcidentifiers:
            if dcid.get('id') is not None:
                opftree.xpath('//opf:package', namespaces=OPFNS)[0].set(
                    'unique-identifier', dcid.get('id')
                )
                uniqid = dcid.get('id')
                id_found = True
                break
        if not id_found:
            # find first UUID URN-based unique identifier
            for dcid in opftree.xpath("//dc:identifier", namespaces=DCNS):
                if 'urn:uuid:' in str(dcid.text):
                    dcid.set('id', 'BookId')
                    opftree.xpath('//opf:package', namespaces=OPFNS)[0].set(
                        'unique-identifier', 'BookId'
                    )
                    uniqid = 'BookId'
                    break
            # find other dc:identifier if UUID not found
            for dcid in opftree.xpath("//dc:identifier", namespaces=DCNS):
                dcid.set('id', 'BookId')
                opftree.xpath('//opf:package', namespaces=OPFNS)[0].set(
                    'unique-identifier', 'BookId'
                )
                uniqid = 'BookId'
                break
    try:
        dc_identifier = opftree.xpath(
            '//dc:identifier[@id="' + str(uniqid) + '"]/text()',
            namespaces=DCNS
        )[0]
    except IndexError:
        return opftree
    try:
        metadtd = etree.XPath('//ncx:meta[@name="dtb:uid"]',
                              namespaces=NCXNS)(ncxtree)[0]
    except IndexError:
        newmetadtd = etree.Element(
            '{http://www.daisy.org/z3986/2005/ncx/}meta',
            attrib={'name': 'dtb:uid', 'content': ''}
        )
        ncxtree.xpath('//ncx:head', namespaces=NCXNS)[0].append(newmetadtd)
        metadtd = etree.XPath('//ncx:meta[@name="dtb:uid"]',
                              namespaces=NCXNS)(ncxtree)[0]
    if metadtd.get('content') != dc_identifier:
        metadtd.set('content', dc_identifier)
    with open(os.path.join(tempdir, ncxfile), 'w') as f:
        f.write(etree.tostring(ncxtree.getroot(), pretty_print=True,
                xml_declaration=True, encoding='utf-8', standalone=False))
    return opftree


def append_reset_css(source_file, xhtml_file, opf_path, opftree):
    try:
        heads = etree.XPath(
            '//xhtml:head',
            namespaces=XHTMLNS
        )(source_file)
    except:
        print('* No head found...')
    for ci in opftree.xpath('//opf:item[@media-type="text/css"]',
                            namespaces=OPFNS):
        if 'epubQTools-reset.css' in ci.get('href'):
            rqcss = ci.get('href')
            break
    heads[0].append(etree.fromstring(
        '<link href="%s" rel="stylesheet" type="text/css" />'
        % os.path.join(os.path.relpath(opf_path, os.path.dirname(xhtml_file)),
                       rqcss).replace('\\', '/')
    ))
    return source_file


def append_reset_css_file(opftree, tempdir, is_rm_family, del_fonts,
                          html_margin):

    def splitkeepsep(s, sep):
        return reduce(lambda acc, elem: acc[:-1] + [acc[-1] + elem]
                      if elem == sep else acc + [elem],
                      re.split("(%s)" % re.escape(sep), s), [])

    def most_common(lst):
        return max(set(lst), key=lst.count)

    is_reset_css = is_body_family = is_calibre_class = False
    ff = ''
    cssitems = opftree.xpath('//opf:item[@media-type="text/css"]',
                             namespaces=OPFNS)
    for c in cssitems:
        if 'epubQTools-reset.css' in c.get('href'):
            is_reset_css = True
            return opftree, is_reset_css
    try:
        for c in cssitems:
            if not is_body_family:
                with open(os.path.join(tempdir, c.get('href')), 'r') as f:
                    fs = f.read()
                    lis = splitkeepsep(fs, '}')
                    for e in lis:
                        if re.search(r'(^|,|\s+)\.calibre(\s+|,|{)', e):
                            is_calibre_class = True
                        if re.search(r'(^|,|\s+)body(\s+|,|{)', e):
                            try:
                                ff = re.search(
                                    r'font-family\s*:\s*(.*?)(;|})', e
                                ).group(1)
                                is_body_family = True
                            except:
                                pass
                        # if ff != '':
                        #     break
        if not is_body_family:
            print('! Font-family for body or .calibre does not found. Trying '
                  'to find the best font...')
            fflist = []
            for c in cssitems:
                with open(os.path.join(tempdir, c.get('href')), 'r') as f:
                    fs = f.read()
                    lis = splitkeepsep(fs, '}')
                    for e in lis:
                        if 'font-family' in e:
                            try:
                                fflist.append(re.search(
                                    r'font-family\s*:\s*(.+?)(;|})', e
                                ).group(1))
                            except:
                                continue
            try:
                ff = most_common(fflist)
            except:
                ff = ''
    except IndexError:
        is_reset_css = True
        return opftree, is_reset_css
    if ff != '':
        for c in cssitems:
            with open(os.path.join(tempdir, c.get('href')), 'r+') as f:
                fs = f.read()
                if del_fonts:
                    print('* Removing all @font-face rules...')
                    fs = re.sub(re.compile(
                        r'@font-face.*?\{.*?\}', re.DOTALL
                    ), '', fs)
                if is_rm_family:
                    print('* Removing problematic font-family...')
                    ffr = ff.split(',')[0]
                    ffr = ffr.replace('"', '').replace("'", '')
                    lis = splitkeepsep(fs, '}')
                    for e in lis:
                        if '@font-face' in e:
                            continue
                        lis[lis.index(e)] = re.sub(
                            r'font-family\s*:\s*(\"|\')?' + re.escape(ffr) +
                            r'(\"|\')?.*?;', '', e
                        )
                        try:
                            lis[lis.index(e)] = re.sub(
                                r'font-family\s*:\s*(\"|\')?' +
                                re.escape(ffr) + r'(\"|\')?.*?}', '}', e
                            )
                        except:
                            continue
                    fs = ''.join(lis)
                if is_calibre_class:
                    fs = 'body, .calibre {font-family: ' + ff + ' }\r\n' + fs
                else:
                    fs = 'body {font-family: ' + ff + ' }\r\n' + fs
                f.seek(0)
                f.truncate()
                f.write(fs)

    if len(cssitems) > 0 and all(
        os.path.dirname(x.get('href')) == os.path.dirname(
            cssitems[0].get('href')
        ) for x in cssitems
    ):
        cssdir = os.path.dirname(cssitems[0].get('href'))
    else:
        cssdir = ''
    if ff != '':
            print('! Setting font-family for body to: %s' % ff)
            if is_calibre_class:
                bs = 'body, .calibre {font-family: %s }\r\n' % ff
            else:
                bs = 'body {font-family: %s }\r\n' % ff
    else:
        bs = ''
    if html_margin is not None:
        bs = bs + 'html {margin-left: ' + html_margin + \
            'px !important; margin-right: ' + html_margin + \
            'px !important;} \r\n'
    with open(os.path.join(tempdir, cssdir, 'epubQTools-reset.css'), 'w') as f:
        f.write(bs +
                '@page { margin: 5pt; } \r\n'
                'body, body.calibre  { margin: 5pt; padding: 0; }\r\n'
                'p { margin-left: 0; margin-right: 0; }\r\n'
                '* { adobe-hyphenate: explicit !important;\r\n'
                'hyphens: manual !important;\r\n'
                '-webkit-hyphens: manual !important;\r\n'
                '-moz-hyphens: manual !important; }\r\n')
    newcssmanifest = etree.Element(
        '{http://www.idpf.org/2007/opf}item',
        attrib={'media-type': 'text/css',
                'href': os.path.join(
                    cssdir,
                    'epubQTools-reset.css'
                ).replace('\\', '/'),
                'id': 'epubQTools-reset'}
    )
    opftree.xpath('//opf:manifest',
                  namespaces=OPFNS)[0].append(newcssmanifest)
    return opftree, is_reset_css


def modify_problematic_styles(source_file):
    img_styles = etree.XPath('//xhtml:img[@style]',
                             namespaces=XHTMLNS)(source_file)
    for s in img_styles:
        s_words = re.split(r'[:; ]+', s.get('style'))
        maxw = w = False
        for sw in s_words:
            if sw == 'max-width':
                maxw = True
            if sw == 'width':
                w = True
        if (maxw and w):
            print('* Fixing problematic combo max-width and width: "' +
                  s.get('style') + '"')
            stylestr = s.get('style')
            stylestr = re.sub(r'[^-]width:(\s*)100%;*', '',
                              stylestr)
            s.set('style', stylestr)
    return source_file


def remove_text_from_html_cover(opftree, rootepubdir):
    try:
        html_cover_path = os.path.join(rootepubdir, opftree.xpath(
            '//opf:reference[@type="cover"]',
            namespaces=OPFNS
        )[0].get('href'))
    except:
        return 0
    try:
        html_cover_tree = etree.parse(html_cover_path,
                                      parser=etree.XMLParser(recover=True))
    except:
        print('* Unable to parse HTML cover file. Giving up...')
        return 0
    try:
        cover_texts = html_cover_tree.xpath('//xhtml:body//text()',
                                            namespaces=XHTMLNS)
    except:
        return None
    if len(cover_texts) > 0:
        print('* Removing needless texts from HTML cover...')
    for t in cover_texts:
        parent = t.getparent()
        if t.startswith('==='):
            continue
        if t.is_text:
            parent.text = ''
        elif t.is_tail:
            parent.tail = ''
    with open(html_cover_path, 'w') as f:
        f.write(etree.tostring(
            html_cover_tree,
            pretty_print=True,
            xml_declaration=True,
            standalone=False,
            encoding='utf-8',
            doctype=set_dtd(opftree))
        )


def convert_dl_to_ul(opftree, rootepubdir):
    try:
        html_toc_path = os.path.join(rootepubdir, opftree.xpath(
            '//opf:reference[@type="toc"]',
            namespaces=OPFNS
        )[0].get('href').split('#')[0])
    except IndexError:
        return None
    with open(html_toc_path, 'r') as f:
        raw = f.read()
    if '<dl>' in raw:
        print('* Coverting HTML TOC from definition list to unsorted list...')
        raw = re.sub(r'<dd>(\s*)<dl>', '<li><ul>', raw)
        raw = re.sub(r'</dl>(\s*)</dd>', '</ul></li>', raw)
        raw = raw.replace('<dl>', '<ul>')
        raw = raw.replace('</dl>', '</ul>')
        raw = raw.replace('<dt>', '<li>')
        raw = raw.replace('</dt>', '</li>')
        with open(html_toc_path, 'w') as f:
            f.write(raw)


def remove_wm_info(opftree, rootepubdir):
    wmfiles = ['watermark.', 'default-info.', 'generated.', 'platon_wm.',
               'cover-special.', 'default-info-epub3.']
    items = opftree.xpath('//opf:item', namespaces=OPFNS)
    for wmf in wmfiles:
        for i in items:
            if wmf in i.get('href'):
                try:
                    wmtree = etree.parse(os.path.join(rootepubdir,
                                                      i.get('href')))
                except:
                    continue
                alltexts = wmtree.xpath('//xhtml:body//text()',
                                        namespaces=XHTMLNS)
                alltext = ' '.join(alltexts)
                alltext = alltext.replace(u'\u00AD', '').strip()
                if (
                    alltext == 'Plik jest zabezpieczony znakiem wodnym' or
                    'Ten ebook jest chroniony znakiem wodnym' in alltext or
                    alltext == ''
                ):
                    remove_file_from_epub(i.get('href'), opftree, rootepubdir)
                    print('* Watermark info page removed: ' + i.get('href'))
    return opftree


def remove_jacket(opftree, rootepubdir):
    items = opftree.xpath('//opf:item', namespaces=OPFNS)
    for i in items:
        if 'jacket.xhtml' in i.get('href'):
            print('* Removing calibre file: "%s"' % i.get('href'))
            remove_file_from_epub(i.get('href'), opftree, rootepubdir)
    return opftree


def remove_file_from_epub(file_rel_to_opf, opftree, rootepubdir):
    item = opftree.xpath('//opf:item[@href="' + file_rel_to_opf + '"]',
                         namespaces=OPFNS)[0]
    item_ncx = opftree.xpath('//opf:itemref[@idref="' + item.get('id') + '"]',
                             namespaces=OPFNS)[0]
    item_ncx.getparent().remove(item_ncx)
    item.getparent().remove(item)
    os.remove(os.path.join(rootepubdir, file_rel_to_opf))


def process_xhtml_file(xhfile, opftree, _resetmargins, skip_hyph, opf_path,
                       is_reset_css, opf_dir_abs, is_xml_ext_fixed, book_lang,
                       dont_hyph_headers):
    global qfixerr
    try:
        with open(xhfile, 'r') as content_file:
            c = content_file.read()
    except IOError, e:
        print('* File skipped: %s. Problem with processing: '
              '%s' % (os.path.basename(xhfile), e))
        qfixerr = True
        return 1
    # placeholder
    for key in entities.iterkeys():
        c = c.replace(key, entities[key])
    try:
        xhtree = etree.fromstring(c, parser=etree.XMLParser(recover=False))
    except etree.XMLSyntaxError, e:
        if ('XML declaration allowed only at the start of the '
                'document' in str(e).decode(SFENC)):
            xhtree = etree.fromstring(c[c.find('<?xml'):],
                                      parser=etree.XMLParser(recover=False))
        elif re.search('Opening and ending tag mismatch: body line \d+ and '
                       'html', str(e).decode(SFENC)):
            try:
                xhtree = etree.fromstring(
                    c.replace('</html>', '</body></html>'),
                    parser=etree.XMLParser(recover=False)
                )
            except:
                print('* File skipped: ' + os.path.basename(xhfile) +
                      '. NOT well formed: "' + str(e).decode(SFENC) + '"')
                qfixerr = True
                return 1
        else:
            print('* File skipped: ' + os.path.basename(xhfile) +
                  '. NOT well formed: "' + str(e).decode(SFENC) + '"')
            qfixerr = True
            return 1

    # remove WM remainings
    for i in etree.XPath("//xhtml:body", namespaces=XHTMLNS)(xhtree):
        try:
            if (
                len(i) > 0 and
                i[-1].text is None and
                i[-1].tail is None and
                i[-1].tag == "{http://www.w3.org/1999/xhtml}div" and
                i[-1][0].tag == "{http://www.w3.org/1999/xhtml}span" and
                len(i[-1]) == 1 and
                i[-1][0].get('style').replace(' ', '').replace(
                    ';', ''
                ) == 'color:whitefont-size:1px' and
                len(i[-1][0]) == 0 and
                i[-1][0].text is None and
                i[-1][0].tail is None
            ):
                print('* Removing WM remaining <div><span/></div>...')
                remove_node(i[-1])
        except:
            continue

    # remove WM reset spans
    wm_classes = ('black', 'black-fore', 'black2', 'dark-gray', 'dark-gray2')
    deltag = "epubqtoolsdelme"  # bogus temporary tag
    for i in wm_classes:
        wm_spans = etree.XPath("//xhtml:span[contains(@class, 'reset') "
                               "and contains(@class, '" + i + "')]",
                               namespaces=XHTMLNS)(xhtree)
        for w in wm_spans:
            w.tag = deltag
    etree.strip_tags(xhtree, deltag)  # strip bogus tags with attributes
    # workaround strange strip tag bug during hyphenation:
    xhtree = etree.fromstring(etree.tostring(xhtree))
    if not skip_hyph and book_lang == 'pl':
        xhtree = hyphenate_and_fix_conjunctions(xhtree, HYPHEN_MARK, hyph,
                                                dont_hyph_headers)
    xhtree = fix_styles(xhtree)
    if is_xml_ext_fixed:
        xhtree = xml2html_fix_references(xhtree, os.path.dirname(xhfile),
                                         False)
    if _resetmargins and not is_reset_css:
        xhtree = append_reset_css(xhtree, xhfile, opf_path, opftree)
    xhtree = modify_problematic_styles(xhtree)
    _wmarks = xhtree.xpath('//xhtml:span[starts-with(text(), "===")]',
                           namespaces=XHTMLNS)
    wm2s = xhtree.xpath(
        '//xhtml:div[@style="padding:0;border:0;text-indent:0;'
        'line-height:normal;margin:0 1cm 0.5cm 1cm;font-size:0pt;'
        'color:#FFFFFF;text-decoration:none;text-align:left;'
        'background:none;display:none;"]',
        namespaces=XHTMLNS
    )
    for wm in wm2s:
        remove_node(wm)
    for wm in _wmarks:
        parent = wm.getparent()
        remove_node(wm)
        if ''.join(parent.itertext()) == '' and len(parent) == 0:
            remove_node(parent)

    # remove meta charsets
    _metacharsets = xhtree.xpath('//xhtml:meta[@charset="utf-8"]',
                                 namespaces=XHTMLNS)
    for mch in _metacharsets:
        mch.getparent().remove(mch)

    # remove useless <?fragment ?> processing-instructions
    p_is = etree.XPath('//processing-instruction("fragment")')(xhtree)
    for p in p_is:
        remove_node(p)

    with open(xhfile, "w") as f:
        f.write(etree.tostring(xhtree, pretty_print=True, xml_declaration=True,
                standalone=False, encoding="utf-8", doctype=set_dtd(opftree)))


def process_epub(_tempdir, _replacefonts, _resetmargins,
                 skip_hyph, arg_justify, arg_left, irmf, fontdir, del_colors,
                 del_fonts, html_margin, dont_hyph_headers):
    global qfixerr
    qfixerr = False
    opf_dir, opf_file_path, is_fixed = find_roots(_tempdir)
    opf_dir_abs = os.path.join(_tempdir, opf_dir)
    opf_file_path_abs = os.path.join(_tempdir, opf_file_path)

    # remove obsolete files
    for roott, dirst, filest in os.walk(_tempdir):
        for f in filest:
            if '.DS_Store' in f:
                os.remove(os.path.join(roott, f))
    try:
        os.remove(os.path.join(_tempdir, 'META-INF', 'calibre_bookmarks.txt'))
    except OSError:
        pass
    try:
        os.remove(os.path.join(_tempdir, 'iTunesMetadata.plist'))
    except OSError:
        pass
    try:
        os.remove(os.path.join(_tempdir, 'msg.txt'))
    except OSError:
        pass

    # append com.apple.ibooks.display-options.xml file
    ibooks_file = os.path.join(_tempdir, 'META-INF',
                               'com.apple.ibooks.display-options.xml')
    if not os.path.exists(ibooks_file) and not del_fonts:
        print('* Adding com.apple.ibooks.display-options.xml '
              'file...')
        with open(ibooks_file, 'wb') as f:
            data = get_data('lib',
                            'resources/com.apple.ibooks.display-options.xml')
            f.write(data)
    elif os.path.exists(ibooks_file) and del_fonts:
        print('* Removing needless com.apple.ibooks.display-options.xml '
              'file...')
        try:
            os.remove(os.path.join(_tempdir, 'META-INF',
                                   'com.apple.ibooks.display-options.xml'))
        except OSError:
            pass

    parser = etree.XMLParser(remove_blank_text=True)
    try:
        opftree = etree.parse(opf_file_path_abs, parser)
    except (etree.XMLSyntaxError, IOError) as e:
        print('! CRITICAL! XML file "%s" is not well '
              'formed: "%s"' % (os.path.basename(opf_file_path_abs),
                                str(e).decode(SFENC)))
        print('! Unable to proceed...')
        return True
    titles = opftree.xpath('//dc:title', namespaces=DCNS)
    if len(titles) == 0:
        print('! CRITICAL! dc:title (book title) element is NOT '
              'defined in OPF file. Unable to proceed...')
        return True
    try:
        etree.XPath('//opf:item[@media-type="application/x-dtbncx+xml"]',
                    namespaces=OPFNS)(opftree)[0].get('href')
    except IndexError:
        print('! CRITICAL! NCX file element is NOT defined in OPF file. '
              'Unable to proceed...')
        return True
    opftree = unquote_urls(opftree)

    opftree, is_xml_ext_fixed = xml2html_extension(opftree, opf_dir_abs)

    fix_ncx(opftree, opf_dir_abs)

    _xhtml_files, _xhtml_file_paths = find_xhtml_files(opf_dir_abs, opftree)

    opftree = fix_various_opf_problems(opftree, opf_dir_abs, _xhtml_files,
                                       _xhtml_file_paths)
    opftree = fix_ncx_dtd_uid(opftree, opf_dir_abs)
    opftree = fix_meta_cover_order(opftree)

    opftree = fix_mismatched_covers(opftree, opf_dir_abs)

    # parse encryption.xml file
    enc_file = os.path.join(_tempdir, 'META-INF', 'encryption.xml')
    if os.path.exists(enc_file):
        process_encryption(enc_file, opftree, fontdir)
        os.remove(enc_file)

    if _replacefonts:
        find_and_replace_fonts(opftree, opf_dir_abs, fontdir)
    if _resetmargins:
        print('* Setting custom CSS styles...')
        opftree, is_reset_css = append_reset_css_file(
            opftree, opf_dir_abs, irmf, del_fonts, html_margin
        )
    else:
        is_reset_css = False
    opftree = remove_jacket(opftree, opf_dir_abs)
    _xhtml_files, _xhtml_file_paths = find_xhtml_files(opf_dir_abs, opftree)
    opftree = fix_html_toc(opftree, opf_dir_abs, _xhtml_files,
                           _xhtml_file_paths)
    convert_dl_to_ul(opftree, opf_dir_abs)
    try:
        book_lang = opftree.xpath("//dc:language", namespaces=DCNS)[0].text
    except IndexError:
        book_lang = ''
    if not skip_hyph and book_lang == 'pl':
        print('* Hyphenating texts...')
        if dont_hyph_headers:
            print('* ... except headers...')
    for s in _xhtml_files:
        process_xhtml_file(s, opftree, _resetmargins, skip_hyph, opf_dir_abs,
                           is_reset_css, opf_dir_abs, is_xml_ext_fixed,
                           book_lang, dont_hyph_headers)
    opftree = remove_wm_info(opftree, opf_dir_abs)
    opftree = html_cover_first(opftree)
    opftree = fix_nav_in_cover_file(opftree, opf_dir_abs)
    remove_text_from_html_cover(opftree, opf_dir_abs)
    if del_fonts:
        opftree = remove_fonts(opftree, opf_dir_abs)
    if arg_justify:
        print('* Replacing "text-align: left" with "text-align: justify" in '
              'all CSS files...')
        modify_css_align(opftree, opf_dir_abs, 'justify', del_colors)
    elif arg_left:
        print('* Replacing "text-align: justify" with "text-align: left" in '
              'all CSS files...')
        modify_css_align(opftree, opf_dir_abs, 'left', del_colors)
    # write all OPF changes back to file
    with open(opf_file_path_abs, 'w') as f:
        f.write(etree.tostring(opftree.getroot(), pretty_print=True,
                standalone=False, xml_declaration=True, encoding='utf-8'))
    return False


def process_corrupted_zip(e, root, f, zipbinf):
    if sys.platform == 'win32':
        print('* Corrupted EPUB file. Unable to fix it...')
        print('FINISH (with PROBLEMS) qfix for: ' + f)
        return 1
    print('* EPUB file "%s" is corrupted! Trying to fix it...'
          % f, end=' ')
    zipbinpath = 'zip'
    if 'differ' in str(e).decode(SFENC):
        zipp = subprocess.Popen([
            zipbinpath, '-FF', '%s' % str(os.path.join(root, f)), '--out',
            '%s' % str(os.path.join(root, 'fixed_' + f))
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zippout, zipperr = zipp.communicate()
        print('FIXED')
        return os.path.join(root, 'fixed_' + f)
    elif 'Bad CRC-32 for file' in str(e).decode(SFENC):
        zipp = subprocess.Popen([
            zipbinpath, '-d', '%s' % str(os.path.join(root, f)),
            str(e).decode(SFENC).split("'")[1],
            '--out', '%s' % str(os.path.join(root, 'fixed_' + f))
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zippout, zipperr = zipp.communicate()
        print('FIXED (with WARNING!)')
        print ('WARNING! Corrupted file "%s" was removed from EPUB file' %
               str(e).decode(SFENC).split("'")[1])
        return os.path.join(root, 'fixed_' + f)
    else:
        print('NOT FIXED')
        print('* ' + str(e).decode(SFENC))
        print('FINISH (with PROBLEMS) qfix for: ' + f)
        return 1


def modify_css_align(opftree, opfdir, mode, del_colors):
    global qfixerr
    if mode == 'justify':
        searchmode = 'left'
    elif mode == 'left':
        searchmode = 'justify'
    cssitems = opftree.xpath('//opf:item[@media-type="text/css"]',
                             namespaces=OPFNS)
    for c in cssitems:
        try:
            with open(os.path.join(opfdir, c.get('href')), 'r+') as cf:
                cc = cf.read()
                cc = re.sub(r'text-align\s*:\s*' + searchmode,
                            'text-align: ' + mode, cc)
                if del_colors:
                    print('* Removing all color definitions from all '
                          'CSS files...')
                    cc = re.sub(r'color\s*:\s*(.*?)(;|\r|\n)', '', cc)
                cf.seek(0)
                cf.truncate()
                cf.write(cc)
        except IOError:
            pass


def html_cover_first(opftree):
    refcvs = opftree.xpath('//opf:reference[@type="cover"]', namespaces=OPFNS)
    if len(refcvs) != 1:
        return opftree
    try:
        if not refcvs[0].get('href').endswith('html'):
            return opftree
        id = opftree.xpath('//opf:item[@href="' + refcvs[0].get('href') + '"]',
                           namespaces=OPFNS)[0].get('id')
        coverir = opftree.xpath('//opf:itemref[@idref="' + id + '"]',
                                namespaces=OPFNS)[0]
        if coverir.attrib['linear']:
            del coverir.attrib['linear']
        spine = coverir.getparent()
        spine.remove(coverir)
    except:
        return opftree
    spine.insert(0, coverir)
    return opftree


def qfix(root, f, _forced, _replacefonts, _resetmargins, zbf,
         skip_hyph, arg_justify, arg_left, irmf, del_colors, del_fonts,
         fontdir, fix_container_only, html_margin, dont_hyph_headers,
         pair_family):
    global qfixerr
    qfixerr = False
    newfile = os.path.splitext(f)[0] + '_moh.epub'
    if not _forced:
        if os.path.isfile(os.path.join(root, newfile)):
            print('* Skipping previously generated _moh file: ' +
                  newfile)
            return 0
    try:
        _tempdir = unpack_epub(os.path.join(root, f))
    except zipfile.BadZipfile, e:
        fixed_pth = process_corrupted_zip(e, root, f, zbf)
        if str(fixed_pth) == '1':
            return 0
        else:
            _tempdir = unpack_epub(fixed_pth)
            os.unlink(fixed_pth)
    if fix_container_only:
        print('')
        print('* Checking for missing META-INF/container.xml in '
              'original file: ' + f)
        opf_dir, opf_file_path, is_fixed = find_roots(_tempdir)
        if is_fixed:
            print('* Repairing missing META-INF/container.xml done! '
                  'Writing changes back to original file...')
            pack_epub(os.path.join(root, f), _tempdir)
        else:
            print('* Repairing not needed...')
    else:
        print('')
        print('START qfix for: ' + f)
        if skip_hyph:
            print('* Hyphenating is turned OFF...')
        is_failed = process_epub(
            _tempdir, _replacefonts, _resetmargins, skip_hyph,
            arg_justify, arg_left, irmf, fontdir, del_colors,
            del_fonts, html_margin, dont_hyph_headers)
        if not is_failed:
            pack_epub(os.path.join(root, newfile), _tempdir)
        else:
            qfixerr = True
        if qfixerr:
            print('FINISH (with PROBLEMS) qfix for: ' + f)
        else:
            print('FINISH qfix for: ' + f)
    clean_temp(_tempdir)
    if not fix_container_only and not is_failed:
        beautify_book(root, f, fontdir, pair_family)
