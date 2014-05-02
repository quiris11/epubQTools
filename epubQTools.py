#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

import argparse
import hashlib
import os
import re
import tempfile
import shutil
import subprocess
import sys
import zipfile
import uuid

from urllib import unquote
from itertools import cycle
from lxml import etree
if not hasattr(sys, 'frozen'):
    sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
from htmlconstants import entities
from hyphenator import Hyphenator
from epubqcheck import qcheck
from os.path import expanduser

try:
    from PIL import ImageFont
    is_pil = True
except ImportError:
    is_pil = False


MY_LANGUAGE = 'pl'
HYPHEN_MARK = u'\u00AD'
if not hasattr(sys, 'frozen'):
    _hyph = Hyphenator(os.path.join(os.path.dirname(__file__), 'resources',
                       'dictionaries', 'hyph_pl_PL.dic'))
else:
    _hyph = Hyphenator(os.path.join(os.path.dirname(sys.executable),
                       'resources', 'dictionaries', 'hyph_pl_PL.dic'))

HOME = expanduser("~")
DTD = ('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
       '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
OPFNS = {'opf': 'http://www.idpf.org/2007/opf'}
XHTMLNS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
DCNS = {'dc': 'http://purl.org/dc/elements/1.1/'}
NCXNS = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
SVGNS = {'svg': 'http://www.w3.org/2000/svg'}
ADOBE_OBFUSCATION = 'http://ns.adobe.com/pdf/enc#RC'
IDPF_OBFUSCATION = 'http://www.idpf.org/2008/embedding'
CRNS = {'cr': 'urn:oasis:names:tc:opendocument:xmlns:container'}


parser = argparse.ArgumentParser()
parser.add_argument("directory", help="Directory with EPUB files stored")
parser.add_argument("-n", "--rename", help="rename .epub files to "
                    "'author - title.epub'",
                    action="store_true")
parser.add_argument("-q", "--qcheck", help="validate files with epubqcheck "
                    "internal tool",
                    action="store_true")
parser.add_argument("-p", "--epubcheck", help="validate epub files with "
                    " EpubCheck 3.0.1 tool",
                    action="store_true")
parser.add_argument("-m", "--mod", help="validate only _moh.epub files "
                    "(only with -q or -v)",
                    action="store_true")
parser.add_argument("-e", "--epub", help="fix and hyphenate original epub "
                    "files to _moh.epub files", action="store_true")
parser.add_argument("-r", "--resetmargins", help="reset CSS margins for "
                    "body, html and @page in _moh.epub files (only with -e)",
                    action="store_true")
parser.add_argument("-c", "--findcover", help="force find cover (risky) "
                    "(only with -e)",
                    action="store_true")
parser.add_argument("-t", "--replacefonts", help="replace font (experimental) "
                    "(only with -e)",
                    action="store_true")
parser.add_argument("-k", "--kindlegen", help="convert _moh.epub files to"
                    " .mobi with kindlegen", action="store_true")
parser.add_argument("-d", "--huffdic", help="tell kindlegen to use huffdic "
                    "compression (slow conversion)", action="store_true")
parser.add_argument("-f", "--force",
                    help="overwrite previously generated _moh.epub or "
                    " .mobi files (only with -k or -e)",
                    action="store_true")
args = parser.parse_args()

_documents = args.directory
validator = args.epubcheck


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
def process_encryption(encfile, opftree):
    print('Font decrypting started...')
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
            decrypt_font(font_path, key, algorithm)
    return True


def find_encryption_key(opftree, method):
    uid = None
    if method == ADOBE_OBFUSCATION:
        # find first UUID URN-based unique identifier
        for dcid in opftree.xpath("//dc:identifier", namespaces=DCNS):
            if dcid.text.startswith('urn:uuid:'):
                uid = dcid.text
                break
        if uid is None:
            print('UUID URN-based unique identifier in content.opf does '
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
            print('Unique identifier in content.opf does not found')
            return uid
        uid = uid.replace('\x20', '').replace('\x09', '').\
            replace('\x0D', '').replace('\x0A', '')
        uid = hashlib.sha1(uid).digest()
    return uid


# based on calibri work
def decrypt_font(path, key, method):
    if method == ADOBE_OBFUSCATION:
        crypt_len = 1024
    elif method == IDPF_OBFUSCATION:
        crypt_len = 1040
    with open(path, 'rb') as f:
        raw = f.read()
    crypt = bytearray(raw[:crypt_len])
    key = cycle(iter(bytearray(key)))
    decrypt = bytes(bytearray(x ^ key.next() for x in crypt))
    with open(path, 'wb') as f:
        f.write(decrypt)
        f.write(raw[crypt_len:])
    is_encrypted_font = False
    is_pil = False
    if is_pil:
        try:
            font_pil = ImageFont.truetype(path, 14)
        except IOError:
            is_encrypted_font = True
    else:
        is_font, signature = check_font(path)
        is_encrypted_font = not is_font
    if is_encrypted_font:
        print(os.path.basename(path) + ': Decrypting FAILED!')
    else:
        print(os.path.basename(path) + ': OK! Decrypted...')
    if is_encrypted_font:
        font_paths = [os.path.join(os.path.sep, 'Library', 'Fonts'),
                      os.path.join(HOME, 'Library', 'Fonts')]
        for font_path in font_paths:
            if os.path.exists(os.path.join(font_path,
                              os.path.basename(path))):
                os.remove(path)
                shutil.copyfile(
                    os.path.join(font_path, os.path.basename(path)),
                    path
                )
        if is_pil:
            try:
                font_pil = ImageFont.truetype(path, 14)
                print(os.path.basename(path) + ': OK! File replaced...')
            except:
                pass
        else:
            is_font, signature = check_font(path)
            if is_font:
                print(os.path.basename(path) + ': OK! File replaced...')


def find_and_replace_fonts(opftree, rootepubdir):
    print('Replacing fonts procedure started...')
    items = etree.XPath('//opf:item[@href]', namespaces=OPFNS)(opftree)
    for item in items:
        if item.get('href').lower().endswith('.otf'):
            actual_font_path = os.path.join(rootepubdir, item.get('href'))
            replace_font(actual_font_path)
            continue
        if item.get('href').lower().endswith('.ttf'):
            actual_font_path = os.path.join(rootepubdir, item.get('href'))
            replace_font(actual_font_path)
            continue


def replace_font(actual_font_path):
    font_paths = [os.path.join(os.path.sep, 'Library', 'Fonts'),
                  os.path.join(HOME, 'Library', 'Fonts')]
    for font_path in font_paths:
        if os.path.exists(
                os.path.join(font_path, os.path.basename(actual_font_path))
        ):
            print('Replacing font: ' + os.path.basename(actual_font_path))
            os.remove(actual_font_path)
            shutil.copyfile(
                os.path.join(font_path, os.path.basename(actual_font_path)),
                actual_font_path
            )


def unpack_epub(source_epub):
    epubzipfile = zipfile.ZipFile(source_epub)
    tempdir = tempfile.mkdtemp()
    epubzipfile.extractall(tempdir)
    os.remove(os.path.join(tempdir, 'mimetype'))
    return epubzipfile, tempdir


def pack_epub(output_filename, source_dir):
    with zipfile.ZipFile(output_filename, "w") as zip:
        zip.writestr("mimetype", "application/epub+zip")
    relroot = source_dir
    with zipfile.ZipFile(output_filename, "a", zipfile.ZIP_DEFLATED) as zip:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                filename = os.path.join(root, file)
                if os.path.isfile(filename):
                    arcname = os.path.join(os.path.relpath(root, relroot),
                                           file)
                    zip.write(filename, arcname)


def clean_temp(sourcedir):
    if os.path.isdir(sourcedir):
        shutil.rmtree(sourcedir)


def find_roots(tempdir):
    try:
        cr_tree = etree.parse(os.path.join(tempdir, 'META-INF',
                                           'container.xml'))
        opf_path = cr_tree.xpath('//cr:rootfile',
                                 namespaces=CRNS)[0].get('full-path')
    except:
        print('Parsing container.xml failed. Not an EPUB file?')
        return 1
    return os.path.dirname(opf_path), opf_path


def find_xhtml_files(epubzipfile, tempdir, rootepubdir, opf_file):
    opftree = etree.parse(opf_file)
    opftree = unquote_urls(opftree)
    try:
        xhtml_items = etree.XPath(
            '//opf:item[@media-type="application/xhtml+xml"]',
            namespaces=OPFNS
        )(opftree)
    except:
        print('XHTML files not found...')
    xhtml_files = []
    xhtml_file_paths = []
    for xhtml_item in xhtml_items:
        xhtml_files.append(os.path.join(rootepubdir, xhtml_item.get('href')))
        xhtml_file_paths.append(xhtml_item.get('href'))
    return opftree, xhtml_files, xhtml_file_paths


def hyphenate_and_fix_conjunctions(source_file, hyph, hyphen_mark):
    try:
        texts = etree.XPath(
            '//xhtml:body//text()',
            namespaces=XHTMLNS
        )(source_file)
    except:
        print('No texts found...')
    for t in texts:
        parent = t.getparent()
        newt = ''
        wlist = re.compile(r'\w+|[^\w]', re.UNICODE).findall(t)
        for w in wlist:
            newt += hyph.inserted(w, hyphen_mark)

        # fix for hanging single conjunctions
        newt = re.sub(r'(?<=\s\w)\s+', u'\u00A0', newt)
        if t.is_text:
            parent.text = newt
        elif t.is_tail:
            parent.tail = newt
    return source_file


def fix_styles(source_file):
    try:
        links = etree.XPath(
            '//xhtml:link',
            namespaces=XHTMLNS
        )(source_file)
    except:
        print('No links found...')
    for link in links:
        if link.get('type') is None:
            link.set('type', 'text/css')
    return source_file


def fix_html_toc(soup, tempdir, xhtml_files, xhtml_file_paths):
    reftocs = etree.XPath('//opf:reference[@type="toc"]',
                          namespaces=OPFNS)(soup)
    if len(reftocs) == 0:
        html_toc = None
        for xhtml_file in xhtml_files:
            xhtmltree = etree.parse(xhtml_file,
                                    parser=etree.XMLParser(recover=True))
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
            parser = etree.XMLParser(remove_blank_text=True)
            if not hasattr(sys, 'frozen'):
                transform = etree.XSLT(etree.parse(os.path.join(
                    os.path.dirname(__file__), 'resources', 'ncx2end-0.2.xsl'
                )))
            else:
                transform = etree.XSLT(etree.parse(os.path.join(
                    os.path.dirname(sys.executable), 'resources',
                    'ncx2end-0.2.xsl'
                )))
            toc_ncx_file = etree.XPath(
                '//opf:item[@media-type="application/x-dtbncx+xml"]',
                namespaces=OPFNS
            )(soup)[0].get('href')
            ncxtree = etree.parse(os.path.join(tempdir, toc_ncx_file), parser)
            result = transform(ncxtree)
            with open(os.path.join(tempdir, 'toc-quiris.xhtml'), "w") as f:
                f.write(etree.tostring(
                    result,
                    pretty_print=True,
                    xml_declaration=True,
                    encoding="utf-8",
                    doctype=DTD
                ))
            newtocmanifest = etree.Element(
                '{http://www.idpf.org/2007/opf}item',
                attrib={'media-type': 'application/xhtml+xml',
                        'href': 'toc-quiris.xhtml', 'id': 'toc-quiris'}
            )
            soup.xpath('//opf:manifest',
                       namespaces=OPFNS)[0].insert(0, newtocmanifest)
            newtocspine = etree.Element(
                '{http://www.idpf.org/2007/opf}itemref',
                idref='toc-quiris'
            )
            soup.xpath('//opf:spine', namespaces=OPFNS)[0].append(newtocspine)
            newtocreference = etree.Element(
                '{http://www.idpf.org/2007/opf}reference',
                title='TOC',
                type='toc',
                href='toc-quiris.xhtml'
            )
        try:
            soup.xpath('//opf:guide',
                       namespaces=OPFNS)[0].insert(0, newtocreference)
        except IndexError:
            newguide = etree.Element('{http://www.idpf.org/2007/opf}guide')
            newguide.append(newtocreference)
            soup.xpath('//opf:package',
                       namespaces=OPFNS)[0].append(newguide)
    return soup


def fix_mismatched_covers(opftree, tempdir):
    print('Checking for mismatched meta and HTML covers...')
    refcvs = opftree.xpath('//opf:reference[@type="cover"]', namespaces=OPFNS)
    if len(refcvs) > 1:
        print('Too many cover references in OPF. Giving up...')
        return 1
    try:
        cover_xhtml_file = os.path.join(tempdir, refcvs[0].get('href'))
    except:
        print('HTML cover reference not found. Giving up...')
        return 1
    xhtmltree = etree.parse(cover_xhtml_file,
                            parser=etree.XMLParser(recover=True))
    allimgs = etree.XPath('//xhtml:img', namespaces=XHTMLNS)(xhtmltree)
    if not allimgs:
        allsvgimgs = etree.XPath('//svg:image', namespaces=SVGNS)(xhtmltree)
        len_svg_images = len(allsvgimgs)
    else:
        len_svg_images = 0
    if len(allimgs) != 1 and len_svg_images != 1:
        print('HTML cover should have only one image. Giving up...')
        return 1
    if allimgs:
        html_cover_img_file = allimgs[0].get('src').split('/')[-1]
    elif allsvgimgs:
        html_cover_img_file = allsvgimgs[0].get(
            '{http://www.w3.org/1999/xlink}href'
        ).split('/')[-1]
    meta_cover_id = opftree.xpath(
        '//opf:meta[@name="cover"]',
        namespaces=OPFNS
    )[0].get('content')
    if meta_cover_id is None:
        print('Meta cover image not properly defined. Giving up...')
        return 1
    try:
        meta_cover_image_file = opftree.xpath(
            '//opf:item[@id="' + meta_cover_id + '"]',
            namespaces=OPFNS
        )[0].get('href').split('/')[-1]
    except IndexError:
        meta_cover_image_file = html_cover_img_file
    if html_cover_img_file != meta_cover_image_file:
        print('Mismatched meta and HTML covers. Fixing...')
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
                encoding="utf-8",
                doctype=DTD)
            )
    else:
        print('Meta and HTML covers are identical...')


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
            if (svg_img_href.find(itemcoverhref) != -1 or
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
            type="cover",   href=cover_file
        )
        _refcovers = etree.XPath('//opf:reference[@type="cover"]',
                                 namespaces=OPFNS)(_soup)
        try:
            if len(_refcovers) == 1:
                _refcovers[0].set('href', cover_file)
            else:
                _soup.xpath('//opf:guide',
                            namespaces=OPFNS)[0].insert(0, _newcoverreference)
        except IndexError:
            newguide = etree.Element('{http://www.idpf.org/2007/opf}guide')
            newguide.append(_newcoverreference)
            _soup.xpath('//opf:package',
                        namespaces=OPFNS)[0].append(newguide)
    return _soup


def set_cover_meta_elem(_metacovers, _soup, _content):
    _metadatas = etree.XPath('//opf:metadata', namespaces=OPFNS)(_soup)
    if len(_metadatas) == 1 and len(_metacovers) == 0:
        _newmeta = etree.Element(
            '{http://www.idpf.org/2007/opf}meta',
            name='cover',
            content=_content
        )
        _metadatas[0].insert(0, _newmeta)
    elif len(_metadatas) == 1 and len(_metacovers) == 1:
        _metacovers[0].set('content', _content)
    return _soup


def force_cover_find(_soup):
    print('Force cover find...')
    images = etree.XPath('//opf:item[@media-type="image/jpeg"]',
                         namespaces=OPFNS)(_soup)
    cover_found = 0
    if len(images) != 0:
        for imag in images:
            img_href_lower = imag.get('href').lower()
            if (img_href_lower.find('cover') != -1 or
                    img_href_lower.find('okladka') != -1):
                cover_found = 1
                print('Candidate image for cover found:' +
                      ' href=' + imag.get('href') +
                      ' id=' + imag.get('id'))
                return imag.get('href'), imag.get('id')
                break
    if cover_found == 0:
        return None, None


def set_correct_font_mime_types(_soup):
    print('Setting correct font mime types...')
    _items = etree.XPath('//opf:item[@href]', namespaces=OPFNS)(_soup)
    for _item in _items:
        if _item.get('href').lower().endswith('.otf'):
            _item.set('media-type', 'application/vnd.ms-opentype')
        elif _item.get('href').lower().endswith('.ttf'):
            _item.set('media-type', 'application/x-font-truetype')
    return _soup


def fix_various_opf_problems(soup, tempdir, xhtml_files,
                             xhtml_file_paths):

    soup = set_correct_font_mime_types(soup)

    # remove multiple dc:language
    lang_counter = 0
    for lang in soup.xpath("//dc:language", namespaces=DCNS):
        lang_counter = lang_counter + 1
        if lang_counter > 1:
            print('Removing multiple language definitions...')
            lang.getparent().remove(lang)

    # set dc:language to my language
    for lang in soup.xpath("//dc:language", namespaces=DCNS):
        if lang.text != MY_LANGUAGE:
            print('Correcting book language to: ' + MY_LANGUAGE)
            lang.text = MY_LANGUAGE

    # add missing dc:language
    if len(soup.xpath("//dc:language", namespaces=DCNS)) == 0:
        print('Setting missing book language to: ' + MY_LANGUAGE)
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
        print('Defining cover guide element...')
        itemcoverhref = os.path.basename(itemcovers[0].get('href'))
        soup = set_cover_guide_ref(
            xhtml_files, itemcoverhref, xhtml_file_paths, soup
        )

    elif len(metacovers) == 0 and len(refcovers) == 1:
        # set missing cover meta element
        cover_image = None
        coversoup = etree.parse(
            os.path.join(tempdir, refcovers[0].get('href')),
            parser=etree.XMLParser(recover=True)
        )
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
                soup = set_cover_meta_elem(metacovers, soup, imag_id)
            else:
                print('No images found...')
        if cover_image is not None:
            cover_image = re.sub('^\.\.\/', '', cover_image)
            itemhrefcovers = etree.XPath(
                '//opf:item[translate(@href, "ABCDEFGHJIKLMNOPQRSTUVWXYZ", '
                '"abcdefghjiklmnopqrstuvwxyz")="' + cover_image.lower() +
                '"]', namespaces=OPFNS
            )(soup)
            if len(itemhrefcovers) == 1:
                soup = set_cover_meta_elem(
                    metacovers, soup, itemhrefcovers[0].get('id')
                )

    elif len(metacovers) == 0 and len(refcovers) == 0 and args.findcover:
        imag_href, imag_id = force_cover_find(soup)
        if imag_href is not None and imag_id is not None:
            soup = set_cover_guide_ref(
                xhtml_files, imag_href, xhtml_file_paths, soup
            )
            soup = set_cover_meta_elem(metacovers, soup, imag_id)
        else:
            print('No images found...')

    # remove calibre staff
    for meta in soup.xpath("//opf:meta[starts-with(@name, 'calibre')]",
                           namespaces=OPFNS):
        meta.getparent().remove(meta)
    for dcid in soup.xpath(
            "//dc:identifier[@opf:scheme='calibre']",
            namespaces={'dc': 'http://purl.org/dc/elements/1.1/',
                        'opf': 'http://www.idpf.org/2007/opf'}
            ):
        dcid.getparent().remove(dcid)
    return soup


def fix_meta_cover_order(soup):
    # name='cover' should be before content attribute
    for cover in soup.xpath('//opf:meta[@name="cover" and @content]',
                            namespaces=OPFNS):
        cover.set('content', cover.attrib.pop('content'))
    return soup


def fix_ncx_dtd_uid(opftree, tempdir):
    ncxfile = etree.XPath(
        '//opf:item[@media-type="application/x-dtbncx+xml"]',
        namespaces=OPFNS
    )(opftree)[0].get('href')
    ncxtree = etree.parse(os.path.join(tempdir, ncxfile))
    uniqid = etree.XPath('//opf:package',
                         namespaces=OPFNS)(opftree)[0].get('unique-identifier')
    if uniqid is None:
        dcidentifiers = etree.XPath('//dc:identifier',
                                    namespaces=DCNS)(opftree)
        for dcid in dcidentifiers:
            if dcid.get('id') is not None:
                uniqid = dcid.get('id')
                break
        opftree.xpath('//opf:package',
                      namespaces=OPFNS)[0].set('unique-identifier', uniqid)
    dc_identifier = etree.XPath('//dc:identifier[@id="' + uniqid + '"]/text()',
                                namespaces=DCNS)(opftree)[0]
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
                xml_declaration=True, encoding='utf-8'))
    return opftree


def append_reset_css(source_file):
    print('Resetting CSS body margin and padding...')
    try:
        heads = etree.XPath(
            '//xhtml:head',
            namespaces=XHTMLNS
        )(source_file)
    except:
        print('No head found...')
    heads[0].append(etree.fromstring(
        '<style type="text/css">'
        '@page { margin: 5pt } '
        'body { margin: 5pt; padding: 0 }'
        '</style>'
    ))
    return source_file


def modify_problematic_styles(source_file):
    styles = etree.XPath('//*[@style]',
                         namespaces=XHTMLNS)(source_file)
    for s in styles:
        if ('display: none' or 'display:none') in s.get('style'):
            print('Replacing problematic style: none with visibility: hidden'
                  '...')
            stylestr = s.get('style')
            stylestr = re.sub(r'display:(\s*)none', 'visibility: hidden',
                              stylestr)
            s.set('style', stylestr)
    img_styles = etree.XPath('//xhtml:img[@style]',
                             namespaces=XHTMLNS)(source_file)
    for s in img_styles:
        if ('max-width' and 'width') in s.get('style'):
            print('Fixing problematic combo max-width and width...')
            print(s.get('style'))
            stylestr = s.get('style')
            stylestr = re.sub(r'width:(\s*)100%;*', '',
                              stylestr)
            s.set('style', stylestr)
    return source_file


def remove_text_from_html_cover(opftree, rootepubdir):
    print('Removing text from HTML cover...')
    try:
        html_cover_path = os.path.join(rootepubdir, opftree.xpath(
            '//opf:reference[@type="cover"]',
            namespaces=OPFNS
        )[0].get('href'))
    except:
        return 0
    html_cover_tree = etree.parse(html_cover_path,
                                  parser=etree.XMLParser(recover=True))
    try:
        trash = html_cover_tree.xpath('//xhtml:h1[@class="invisible"]',
                                      namespaces=XHTMLNS)[0]
        trash.text = ''
    except:
        return 0
    with open(html_cover_path, "w") as f:
        f.write(etree.tostring(
            html_cover_tree,
            pretty_print=True,
            xml_declaration=True,
            encoding="utf-8",
            doctype=DTD)
        )


def replace_svg_html_cover(opftree, rootepubdir):
    print('Replacing svg cover procedure starting...')
    html_cover_path = os.path.join(rootepubdir, opftree.xpath(
        '//opf:reference[@type="cover"]',
        namespaces=OPFNS
    )[0].get('href'))
    html_cover_tree = etree.parse(html_cover_path,
                                  parser=etree.XMLParser(recover=True))
    svg_imgs = html_cover_tree.xpath('//svg:image', namespaces=SVGNS)
    if len(svg_imgs) == 1:
        if not hasattr(sys, 'frozen'):
            new_cover_tree = etree.parse(os.path.join(
                os.path.dirname(__file__), 'resources', 'cover.xhtml'
            ))
        else:
            new_cover_tree = etree.parse(os.path.join(
                os.path.dirname(sys.executable), 'resources',
                'cover.xhtml'
            ))
        new_cover_tree.xpath(
            '//xhtml:img',
            namespaces=XHTMLNS
        )[0].set('src', svg_imgs[0].get('{http://www.w3.org/1999/xlink}href'))
        with open(html_cover_path, "w") as f:
            f.write(etree.tostring(
                new_cover_tree,
                pretty_print=True,
                xml_declaration=True,
                encoding="utf-8",
                doctype=DTD)
            )


def convert_dl_to_ul(opftree, rootepubdir):
    html_toc_path = os.path.join(rootepubdir, opftree.xpath(
        '//opf:reference[@type="toc"]',
        namespaces=OPFNS
    )[0].get('href').split('#')[0])
    with open(html_toc_path, 'r') as f:
        raw = f.read()
    if '<dl>' in raw:
        print('Coverting HTML TOC from definition list to unsorted list...')
        raw = re.sub(r'<dd>(\s*)<dl>', '<li><ul>', raw)
        raw = re.sub(r'</dl>(\s*)</dd>', '</ul></li>', raw)
        raw = raw.replace('<dl>', '<ul>')
        raw = raw.replace('</dl>', '</ul>')
        raw = raw.replace('<dt>', '<li>')
        raw = raw.replace('</dt>', '</li>')
        with open(html_toc_path, 'w') as f:
            f.write(raw)


def remove_wm_info(opftree, rootepubdir):
    wmfiles = ['watermark.', 'default-info.', 'generated.', 'platon_wm.']
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
                if alltext == 'Plik jest zabezpieczony znakiem wodnym':
                    remove_file_from_epub(i.get('href'), opftree, rootepubdir)
                    print('Watermark info page removed: ' + i.get('href'))
    return opftree


def remove_file_from_epub(file_rel_to_opf, opftree, rootepubdir):
    item = opftree.xpath('//opf:item[@href="' + file_rel_to_opf + '"]',
                         namespaces=OPFNS)[0]
    item_ncx = opftree.xpath('//opf:itemref[@idref="' + item.get('id') + '"]',
                             namespaces=OPFNS)[0]
    item_ncx.getparent().remove(item_ncx)
    item.getparent().remove(item)
    os.remove(os.path.join(rootepubdir, file_rel_to_opf))


def main():
    if args.qcheck or args.rename:
        qcheck(_documents, args.mod, args.epubcheck, args.rename)
    elif args.kindlegen:
        compression = '-c2' if args.huffdic else '-c1'
        for root, dirs, files in os.walk(_documents):
            for _file in files:
                if _file.endswith('_moh.epub'):
                    newmobifile = os.path.splitext(_file)[0] + '.mobi'
                    if not args.force:
                        if os.path.isfile(os.path.join(root, newmobifile)):
                            print(
                                'Skipping previously generated _moh file: ' +
                                newmobifile.decode(sys.getfilesystemencoding())
                            )
                            continue
                    print('')
                    print('Kindlegen: Converting file: ' +
                          _file.decode(sys.getfilesystemencoding()))
                    proc = subprocess.Popen([
                        'kindlegen',
                        '-dont_append_source',
                        compression,
                        os.path.join(root, _file)
                    ], stdout=subprocess.PIPE).communicate()[0]

                    cover_html_found = False
                    for ln in proc.splitlines():
                        if ln.find('Warning') != -1:
                            print(ln)
                        if ln.find('Error') != -1:
                            print(ln)
                        if ln.find('I1052') != -1:
                            cover_html_found = True
                    if not cover_html_found:
                        print('')
                        print(
                            'WARNING: Probably duplicated covers '
                            'generated in file: ' +
                            newmobifile.decode(sys.getfilesystemencoding())
                        )

    elif args.epub:
        for root, dirs, files in os.walk(_documents):
            for _file in files:
                if (_file.endswith('.epub') and
                        not _file.endswith('_moh.epub') and
                        not _file.endswith('_org.epub')):
                    _newfile = os.path.splitext(_file)[0] + '_moh.epub'

                    # if not forced skip previously generated files
                    if not args.force:
                        if os.path.isfile(os.path.join(root, _newfile)):
                            print(
                                'Skipping previously generated _moh file: ' +
                                _newfile.decode(sys.getfilesystemencoding())
                            )
                            continue

                    print('')
                    print('Working on: ' +
                          _file.decode(sys.getfilesystemencoding()))
                    _epubzipfile, _tempdir = unpack_epub(
                        os.path.join(root, _file)
                    )

                    opf_dir, opf_file_path = find_roots(_tempdir)
                    opf_dir_abs = os.path.join(_tempdir, opf_dir)
                    opf_file_path_abs = os.path.join(_tempdir, opf_file_path)

                    # remove obsolete calibre_bookmarks.txt
                    try:
                        os.remove(os.path.join(
                            _tempdir, 'META-INF', 'calibre_bookmarks.txt'
                        ))
                    except OSError:
                        pass

                    (
                        opftree, _xhtml_files, _xhtml_file_paths
                    ) = find_xhtml_files(
                        _epubzipfile, _tempdir, opf_dir_abs, opf_file_path_abs
                    )

                    opftree = fix_various_opf_problems(
                        opftree, opf_dir_abs,
                        _xhtml_files, _xhtml_file_paths
                    )

                    opftree = fix_ncx_dtd_uid(opftree, opf_dir_abs)

                    opftree = fix_html_toc(
                        opftree, opf_dir_abs,
                        _xhtml_files, _xhtml_file_paths
                    )

                    opftree = fix_meta_cover_order(opftree)

                    # experimental - disabled
                    # replace_svg_html_cover(opftree, opf_dir_abs)

                    fix_mismatched_covers(opftree, opf_dir_abs)

                    convert_dl_to_ul(opftree, opf_dir_abs)
                    remove_text_from_html_cover(opftree, opf_dir_abs)

                    # parse encryption.xml file
                    enc_file = os.path.join(
                        _tempdir, 'META-INF', 'encryption.xml'
                    )
                    if os.path.exists(enc_file):
                        process_encryption(enc_file, opftree)
                        os.remove(enc_file)

                    if args.replacefonts:
                        find_and_replace_fonts(opftree, opf_dir_abs)

                    hyph_info_printed = False
                    for _single_xhtml in _xhtml_files:
                        with open(_single_xhtml, 'r') as content_file:
                            c = content_file.read()
                        for key in entities.iterkeys():
                            c = c.replace(key, entities[key])
                        _xhtmltree = etree.fromstring(
                            c, parser=etree.XMLParser(recover=False)
                        )

                        if opftree.xpath(
                                "//dc:language", namespaces=DCNS
                        )[0].text == 'pl':
                            if not hyph_info_printed:
                                print('Hyphenating book with Polish '
                                      'dictionary...')
                                hyph_info_printed = True
                            _xhtmltree = hyphenate_and_fix_conjunctions(
                                _xhtmltree, _hyph, HYPHEN_MARK
                            )

                        _xhtmltree = fix_styles(_xhtmltree)

                        if args.resetmargins:
                            _xhtmltree = append_reset_css(_xhtmltree)

                        _xhtmltree = modify_problematic_styles(_xhtmltree)

                        # remove watermarks
                        _wmarks = etree.XPath(
                            '//xhtml:span[starts-with(text(), "==")]',
                            namespaces=XHTMLNS
                        )(_xhtmltree)
                        for wm in _wmarks:
                            remove_node(wm)

                        # remove meta charsets
                        _metacharsets = etree.XPath(
                            '//xhtml:meta[@charset="utf-8"]',
                            namespaces=XHTMLNS
                        )(_xhtmltree)
                        for mch in _metacharsets:
                            mch.getparent().remove(mch)

                        with open(_single_xhtml, "w") as f:
                            f.write(etree.tostring(
                                _xhtmltree,
                                pretty_print=True,
                                xml_declaration=True,
                                encoding="utf-8",
                                doctype=DTD)
                            )
                    opftree = remove_wm_info(opftree, opf_dir_abs)

                    # write all OPF changes back to file
                    with open(opf_file_path_abs, 'w') as f:
                        f.write(etree.tostring(
                            opftree.getroot(),
                            pretty_print=True,
                            xml_declaration=True,
                            encoding='utf-8'
                        ))

                    pack_epub(os.path.join(root, _newfile),
                              _tempdir)
                    clean_temp(_tempdir)
                    print('Done...')
    else:
        parser.print_help()
        print("* * *")
        print("* At least one of above optional arguments is required.")
        print("* * *")
    return 0

if __name__ == '__main__':
    sys.exit(main())
