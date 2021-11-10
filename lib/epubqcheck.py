#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#


import zipfile
import re
import os
import sys
import tempfile
import shutil
import logging
import lib.fntutls
import io
import struct
from urllib.parse import unquote
from lib.htmlconstants import entities

SFENC = sys.getfilesystemencoding()
try:
    from tidylib import tidy_document
    is_tidy = True
except ImportError as e:
    is_tidy = False

try:
    from lxml import etree
    import cssutils
    from cssutils.profiles import Profiles, properties, macros
except ImportError as e:
    sys.exit('! CRITICAL! ' + str(e).decode(SFENC))

# set up recover parser for malformed XML
recover_parser = etree.XMLParser(encoding='utf-8', recover=True)

# add the most common used non-standard properties for cssutils
properties[Profiles.CSS_LEVEL_2]['oeb-column-number'] = r'{num}'
properties[Profiles.CSS_LEVEL_2]['hyphens'] = r'none|manual|auto|all'
properties[Profiles.CSS_LEVEL_2]['-epub-hyphens'] = r'none|manual|auto|all'
properties[Profiles.CSS_LEVEL_2]['-webkit-hyphens'] = r'none|manual|auto|all'
properties[Profiles.CSS_LEVEL_2]['-moz-hyphens'] = r'none|manual|auto|all'
properties[Profiles.CSS_LEVEL_2]['adobe-hyphenate'] = r'none|explicit|auto'
cssutils.profile.addProfiles([(
    Profiles.CSS_LEVEL_2, properties[Profiles.CSS_LEVEL_2],
    macros[Profiles.CSS_LEVEL_2]
)])

# set up additional amzn MEDIA_TYPES and handler for cssutils
cssutils.stylesheets.MediaQuery.MEDIA_TYPES = \
    cssutils.stylesheets.MediaQuery.MEDIA_TYPES + \
    ['amzn-mobi', 'amzn-mobi7', 'amzn-kf8']
streamhandler = logging.StreamHandler()

formatter = logging.Formatter('* CSS %(levelname)s! Problem in '
                              '"%(name)s": %(message)s')
streamhandler.setFormatter(formatter)

OPFNS = {'opf': 'http://www.idpf.org/2007/opf'}
XHTMLNS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
DCNS = {'dc': 'http://purl.org/dc/elements/1.1/'}
NCXNS = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
SVGNS = {'svg': 'http://www.w3.org/2000/svg'}
CRNS = {'cr': 'urn:oasis:names:tc:opendocument:xmlns:container'}


def check_font(path):
    with open(path, 'rb') as f:
        raw = f.read()
    signature = raw[:4]
    return (signature in {b'\x00\x01\x00\x00', b'OTTO'}, signature)


# based on calibri work
def unquote_urls(tree):
    def get_href(item):
        raw = unquote(item.get('href', ''))
        if not isinstance(raw, str):
            raw = raw.decode('utf-8')
        return raw
    for item in tree.xpath('//opf:item', namespaces=OPFNS):
        item.set('href', get_href(item))
    for item in tree.xpath('//opf:reference', namespaces=OPFNS):
        item.set('href', get_href(item))
    return tree


def check_wm_info(singf, tree, epub, _file_dec):
    alltexts = etree.XPath('//xhtml:body//text()',
                           namespaces=XHTMLNS)(tree)
    alltext = ' '.join(alltexts)
    alltext = alltext.replace('\u00AD', '').strip()
    if (alltext == 'Plik jest zabezpieczony znakiem wodnym' or
            'Ten ebook jest chroniony znakiem wodnym' in alltext):
        print('%sWM info file found "%s"' % (_file_dec, singf))


def check_display_none(singf, tree, epub, _file_dec, cont_src_list):
    styles = etree.XPath('//*[@style]',
                         namespaces=XHTMLNS)(tree)
    for s in styles:
        if (
            (
                ('display: none' in s.get('style')) or
                ('display:none' in s.get('style'))
            ) and (os.path.basename(
                   singf) + '#' + str(s.get('id'))) in cont_src_list
        ):
            print('%sElement with problematic (for kindlegen) '
                  'display:none style found in file "%s"'
                  % (_file_dec, singf))


def check_dl_in_html_toc(tree, dir, epub, _file_dec):
    try:
        html_toc_path = os.path.relpath(os.path.join(
            dir,
            tree.xpath('//opf:reference[@type="toc"]',
                       namespaces=OPFNS)[0].get('href')
        )).replace('\\', '/')
        raw = epub.read(html_toc_path)
        if '<dl>' in raw:
            print(_file_dec + 'Problematic DL tag in HTML TOC found...')
    except:
        pass


def check_meta_html_covers(tree, dir, epub, _file_dec):
    try:
        html_cover_path = etree.XPath('//opf:reference[@type="cover"]',
                                      namespaces=OPFNS)(tree)[0].get('href')
    except:
        return 0
    try:
        meta_cover_id = etree.XPath('//opf:meta[@name="cover"]',
                                    namespaces=OPFNS)(tree)[0].get('content')
    except:
        print(_file_dec + 'Meta cover image is NOT defined.')
        return 0
    try:
        meta_cover_path = etree.XPath(
            '//opf:item[@id="' + meta_cover_id + '"]',
            namespaces=OPFNS
        )(tree)[0].get('href')
    except IndexError:
        print(_file_dec + 'Meta cover is NOT properly defined.')
        return 0
    parser = etree.XMLParser(recover=True)
    try:
        html_cover_tree = etree.fromstring(
            epub.read(os.path.relpath(os.path.join(
                dir, html_cover_path
            )).replace('\\', '/')),
            parser
        )
    except KeyError as e:
        print(_file_dec + 'Problem with parsing HTML cover: ' + str(
            e).decode(SFENC))
        html_cover_tree = None
        pass
    try:
        cover_texts = etree.XPath(
            '//xhtml:body//text()',
            namespaces=XHTMLNS
        )(html_cover_tree)
        cover_texts = ' '.join(cover_texts)
        if '\xa0' in cover_texts:
            print(_file_dec + 'HTML cover should not contain any text...')
        else:
            cover_texts = cover_texts.strip()
            if cover_texts != '':
                print(_file_dec + 'HTML cover should not contain any text...')
    except:
        pass
    if html_cover_tree is None:
        print(_file_dec + 'Error loading HTML cover... '
              'Probably not a html file...')
        return 0
    allimgs = etree.XPath('//xhtml:img', namespaces=XHTMLNS)(html_cover_tree)
    if len(allimgs) > 1:
        print(_file_dec + 'HTML cover should have only one image...')
    for img in allimgs:
        if (
                len(allimgs) == 1 and
                img.get('src').split('/')[-1].find(
                    meta_cover_path.split('/')[-1]
                )
        ) == -1:
            print(_file_dec + 'Meta cover and HTML cover mismatched.')
    allsvgimgs = etree.XPath('//svg:image', namespaces=SVGNS)(html_cover_tree)
    if len(allsvgimgs) > 1:
        print(_file_dec + 'HTML cover should have only one image...')
    for svgimg in allsvgimgs:
        if (
                len(allsvgimgs) == 1 and
                svgimg.get(
                    '{http://www.w3.org/1999/xlink}href'
                ).split('/')[-1].find(meta_cover_path.split('/')[-1]) == -1
        ):
            print(_file_dec + 'Meta cover and HTML cover mismatched.')


def find_cover_image(_opftree, _file_dec):
    images = etree.XPath('//opf:item[@media-type="image/jpeg"]',
                         namespaces=OPFNS)(_opftree)
    cover_found = 0
    if len(images) != 0:
        for imag in images:
            img_href_lower = imag.get('href').lower()
            if (img_href_lower.find('cover') != -1 or
                    img_href_lower.find('okladka') != -1):
                cover_found = 1
                print(_file_dec + 'Candidate image for cover found:' +
                      ' href=' + imag.get('href') +
                      ' id=' + imag.get('id'))
                break
        if cover_found == 0:
            print(_file_dec + 'No candidate cover images found. '
                  'Check a list of all images:')
            for imag in images:
                print(imag.get('href'))
    else:
        print(_file_dec + 'No images in an entire book found...')


def qcheck_opf_file(opf_root, opf_path, _epubfile, _file_dec, alter):

    def check_orphan_files(epub, opftree, root, _file_dec):
        def is_exluded(name):
            excludes = ['mimetype',
                        'META-INF/container.xml',
                        'META-INF/com.apple.ibooks.display-options.xml',
                        'META-INF/encryption.xml',
                        '/',
                        opf_path]
            for e in excludes:
                if name.endswith(e):
                    return True
            return False

        nlist = []
        enc_found = False
        for n in epub.namelist():
            if 'META-INF/encryption.xml' in n:
                enc_found = True
            if not isinstance(n, str):
                n = n.decode('utf-8')
            if not is_exluded(n):
                nlist.append(os.path.relpath(n))

        hlist = []
        for i in opftree.xpath('//*[@href]'):
            h = i.get('href')
            if not isinstance(h, str):
                h = h.decode('utf-8')
            hlist.append(os.path.relpath(os.path.join(root, h)))

        for n in nlist:
            found = False
            for h in hlist:
                if n == h:
                    found = True
                    break
            if not found:
                print('%sORPHAN file "%s" is NOT defined in OPF file'
                      % (_file_dec, n.encode('utf-8')))
        return enc_found

    def check_dupl_ids_insensitive(tree):
        items = tree.xpath('//opf:itemref/@idref', namespaces=OPFNS)
        seen = set()
        dupl = []
        for x in items:
            x = x.lower()
            if x not in seen:
                seen.add(x)
            else:
                dupl.append(x)
        if len(dupl) > 0:
            print('%sDuplicated problematic case-insensitive '
                  'ids: %s found in <spine>' % (_file_dec, dupl))

    def check_mime_types(tree):
        items = tree.xpath('//opf:item[@href]', namespaces=OPFNS)
        for i in items:

            if (
                    (i.get('href').lower().endswith('.otf') or
                     i.get('href').lower().endswith('.ttf')) and
                    i.get('media-type') != 'application/vnd.ms-opentype'
            ):
                print('%sFont file "%s" has incorrect media-type "%s".' % (
                    _file_dec, i.get('href'), i.get('media-type')
                ))
            elif i.get('href').lower().endswith('.ttc'):
                print('%sFont file "%s" has problematic format "TTC".' % (
                    _file_dec, i.get('href'))
                )
            elif i.get('media-type') == 'text/html':
                print('%sA file "%s" has incorrect media-type "%s".' % (
                    _file_dec, i.get('href'), i.get('media-type')
                ))
            if (i.get('href').lower().endswith('.xml') and
                    i.get('media-type') == 'application/xhtml+xml'):
                print(
                    '%sA file "%s" has incorrect extension ".xml" '
                    'for specified media-type "%s".' % (
                        _file_dec, i.get('href'), i.get('media-type')
                    )
                )
    if opf_root == '':
        _folder = ''
    else:
        _folder = opf_root + '/'
    try:
        opftree = etree.fromstring(_epubfile.read(opf_path))
    except etree.XMLSyntaxError as e:
        print('%sCRITICAL! XML file "%s" is not well '
              'formed: "%s"' % (_file_dec, os.path.basename(opf_path),
                                str(e).decode(SFENC)))
        opfstring = io.StringIO(_epubfile.read(opf_path))
        try:
            opftree = etree.parse(opfstring, recover_parser)
        except etree.XMLSyntaxError:
            return None
    opftree = unquote_urls(opftree)
    try:
        book_ver = opftree.xpath('//opf:package',
                                 namespaces=OPFNS)[0].get('version')
        if not alter and book_ver != '2.0':
            print(_file_dec + 'Info: EPUB version: ' + book_ver)
    except:
        print(_file_dec + 'CRITICAL! No EPUB version info...')
    enc_found = check_orphan_files(_epubfile, opftree, _folder, _file_dec)
    if opftree.xpath('//opf:metadata', namespaces=OPFNS) is None:
        print(_file_dec + 'CRITICAL! No metadata defined in OPF file...')
    creators = opftree.xpath('//dc:creator', namespaces=DCNS)
    if creators is None:
        print(_file_dec + 'CRITICAL! dc:creator (book author) element is NOT '
              'defined in OPF file...')
    else:
        for c in creators:
            if c.text is None or c.text.strip() == '':
                print(_file_dec + 'CRITICAL! dc:creator (book author) is '
                      'empty...')
            elif '\n' in c.text or '\r' in c.text:
                print(_file_dec + 'CRITICAL! dc:creator (book author) contains'
                      ' problematic marks "\r" or "\n"...')
            elif c.text is not None:
                if c.text.isupper():
                    print(_file_dec + 'dc:creator (book author) UPPERCASED: '
                          '"%s". Consider changing...' % c.text)
    titles = opftree.xpath('//dc:title', namespaces=DCNS)
    if len(titles) == 0:
        print(_file_dec + 'CRITICAL! dc:title (book title) element is NOT '
              'defined in OPF file...')
    else:
        if len(titles) > 1:
            print(_file_dec + 'Warning! Multiple dc:title (book title) '
                  'elements defined in OPF file may be problematic...')
        for t in titles:
            if t.text is None or t.text.strip() == '':
                print(_file_dec + 'CRITICAL! dc:title (book title) is '
                      'empty...')
            elif '\n' in t.text or '\r' in t.text:
                print(_file_dec + 'CRITICAL! dc:title (book title) contains'
                      ' problematic marks "\r" or "\n"...')
            elif t.text is not None:
                if t.text.isupper():
                    print(_file_dec + 'dc:title (book title) UPPERCASED: '
                          '"%s". Consider changing...' % titles[0].text)
    language_tags = etree.XPath('//dc:language/text()',
                                namespaces=DCNS)(opftree)
    if len(language_tags) == 0:
        print(_file_dec + 'No dc:language defined')
    else:
        if len(language_tags) > 1:
            print(_file_dec + 'Multiple dc:language tags')
        for _lang in language_tags:
            if _lang != 'pl':
                print(_file_dec + 'Problem with '
                      'dc:language. Current value: ' + _lang)

    _metacovers = etree.XPath('//opf:meta[@name="cover"]',
                              namespaces=OPFNS)(opftree)
    if len(_metacovers) > 1:
        print(_file_dec + 'Multiple meta cover images defined.')

    _references = etree.XPath('//opf:reference', namespaces=OPFNS)(opftree)
    _refcovcount = _reftoccount = _reftextcount = 0
    for _reference in _references:
        if _reference.get('type') == 'cover':
            _refcovcount += 1
        if _reference.get('type') == 'toc':
            _reftoccount += 1
        if _reference.get('type') == 'text':
            _reftextcount += 1

    if _refcovcount == 0:
        print(_file_dec + 'HTML cover is NOT defined.')
    if _refcovcount > 1:
        print(_file_dec + 'Multiple HTML covers defined.')

    if _reftoccount == 0:
        print(_file_dec + 'HTML TOC is NOT defined.')
    elif _reftoccount > 1:
        print(_file_dec + 'Multiple HTML TOCs defined.')

    if _reftextcount == 0:
        pass  # print(_file_dec + 'No text guide element defined.')
    elif _reftextcount > 1:
        print(_file_dec + 'Multiple text guide elements defined.')

    if len(_metacovers) == 0 and _refcovcount == 0:
        find_cover_image(opftree, _file_dec)
    else:
        check_meta_html_covers(opftree, _folder, _epubfile, _file_dec)

    check_dl_in_html_toc(opftree, _folder, _epubfile, _file_dec)

    _htmlfiletags = etree.XPath(
        '//opf:item[@media-type="application/xhtml+xml"]', namespaces=OPFNS
    )(opftree)
    _linkfound = _unbfound = _ufound = _wmfound = metcharfound = False
    body_id_list = []
    for _htmlfiletag in _htmlfiletags:
        _htmlfilepath = _htmlfiletag.get('href')
        parser = etree.XMLParser(recover=False)
        try:
            html_str = _epubfile.read(os.path.relpath(os.path.join(
                _folder, _htmlfilepath
            )).replace('\\', '/'))
            for key, entity in entities.items():
                key = key.encode('utf-8')
                entity = entity.encode('utf-8')
                html_str = html_str.replace(key, entity)
            if is_tidy:
                document, errors = tidy_document(html_str)
                if errors != '':
                    print(_file_dec + 'HTML Tidy problems '
                          'for: ' + _htmlfilepath)
                    for i in errors.split('\n'):
                        if i != '':
                            print('  ' + i)
            _xhtmlsoup = etree.fromstring(html_str, parser)
        except (KeyError, zipfile.BadZipfile) as e:
            print(_file_dec + 'Problem with a file: ' + str(e).decode(SFENC))
            continue
        except etree.XMLSyntaxError as e:
            print(_file_dec + 'XML file: ' + _htmlfilepath +
                  ' not well formed: "' + str(e).decode(SFENC) + '"')
            continue

        # build list with body tags with id attributes
        try:
            body_id = etree.XPath('//xhtml:body[@id]',
                                  namespaces=XHTMLNS)(_xhtmlsoup)[0]
        except IndexError:
            body_id = None
        if body_id is not None:
            body_id_list.append(os.path.basename(
                _htmlfilepath
            ) + '#' + body_id.get('id'))

        if _wmfound is False:
            _watermarks = etree.XPath('//*[starts-with(text(),"===")]',
                                      namespaces=XHTMLNS)(_xhtmlsoup)
            if len(_watermarks) > 0:
                print(_file_dec + 'Potential problematic WM found ("===")...')
                _wmfound = True

        if metcharfound is False:
            _metacharsets = etree.XPath('//xhtml:meta[@charset="utf-8"]',
                                        namespaces=XHTMLNS)(_xhtmlsoup)
            if len(_metacharsets) > 0:
                print(_file_dec + 'At least one xhtml file hase problematic'
                      ' <meta charset="utf-8" /> defined...')
                metcharfound = True

        _alltexts = etree.XPath('//xhtml:body//text()',
                                namespaces=XHTMLNS)(_xhtmlsoup)
        _alltext = ' '.join(_alltexts)

        if _reftoccount == 0 and _alltext.find('Spis treści') != -1:
                print(_file_dec + 'Html TOC candidate found: ' +
                      _htmlfilepath)
        check_hyphs = False
        if check_hyphs:
            if not _ufound and _alltext.find('\u00AD') != -1:
                print(_file_dec + 'U+00AD hyphenate marks found.')
                _ufound = True
            if not _unbfound and _alltext.find('\u00A0') != -1:
                print(_file_dec + 'U+00A0 non-breaking space found.')
                _unbfound = True
        p_is = etree.XPath('//processing-instruction("fragment")')(_xhtmlsoup)
        for p in p_is:
            print(_file_dec + 'Useless ' + etree.tostring(p).decode('utf-8') + ' processing '
                  'instruction found...')
        _links = etree.XPath('//xhtml:link', namespaces=XHTMLNS)(_xhtmlsoup)
        for _link in _links:
            if not _linkfound and (_link.get('type') is None):
                _linkfound = True
                print(_file_dec + 'At least one xhtml file has link tag '
                      'without type attribute defined')

    # Check dtb:uid - should be identical go dc:identifier
    try:
        ncxfile = etree.XPath(
            '//opf:item[@media-type="application/x-dtbncx+xml"]',
            namespaces=OPFNS
        )(opftree)[0].get('href')
        ncxstr = _epubfile.read(os.path.relpath(os.path.join(_folder,
                                ncxfile)).replace('\\', '/'))
    except (IndexError, KeyError):
        print('%sCRITICAL! NCX file is missing...' % (_file_dec))
        ncxstr = '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" />'
    try:
        ncxtree = etree.fromstring(ncxstr)
    except etree.XMLSyntaxError as e:
        print('%sCRITICAL! XML file "%s" is not well '
              'formed: "%s"' % (_file_dec, ncxfile, str(e).decode(SFENC)))
        ncxtree = etree.parse(io.StringIO(ncxstr), recover_parser)
    contents = etree.XPath('//ncx:content[@src]', namespaces=NCXNS)(ncxtree)
    cont_src_list = []
    for c in contents:
        cont_src_list.append(c.get('src').split('/')[-1])
    try:
        uniqid = etree.XPath(
            '//opf:package',
            namespaces=OPFNS)(opftree)[0].get('unique-identifier')
    except IndexError:
        uniqid = None
    if uniqid is not None:
        try:
            dc_identifier = etree.XPath('//dc:identifier[@id="' + uniqid +
                                        '"]/text()',
                                        namespaces=DCNS)(opftree)[0]
        except:
            dc_identifier = ''
            print(_file_dec + 'dc:identifier with unique-id not found')
    else:
        dc_identifier = ''
        print(_file_dec + 'no unique-identifier found')
    try:
        metadtb = etree.XPath('//ncx:meta[@name="dtb:uid"]',
                              namespaces=NCXNS)(ncxtree)[0]
        if metadtb.get('content') != dc_identifier:
            print(_file_dec + 'dtb:uid and dc:identifier mismatched')
    except IndexError:
        print(_file_dec + 'dtb:uid not properly defined')

    # Check for duplicated content attribute of navPoints in NCX file
    srcs = etree.XPath('//ncx:content/@src',
                       namespaces=NCXNS)(ncxtree)
    seen = set()
    dupl = []
    for x in srcs:
        if x not in seen:
            seen.add(x)
        else:
            dupl.append(x)

        # check if NCX item links to body with id (kindlegen reports error)
        if x.split('/')[-1] in body_id_list:
            print('* Problem: NCX item links to body with id: ' + x)

    if len(dupl) > 0:
        print('%sDuplicated content attributes of navPoints: '
              '%s found in NCX file' % (_file_dec, dupl))

    for meta in opftree.xpath("//opf:meta[starts-with(@name, 'calibre')]",
                              namespaces=OPFNS):
        print(_file_dec + 'calibre staff found')
        break
    for meta in opftree.xpath("//opf:meta[@name='Sigil version']",
                              namespaces=OPFNS):
        print(_file_dec + 'Sigil version info found')
        break
    for dcid in opftree.xpath(
        "//dc:identifier[@opf:scheme='calibre']",
        namespaces={'dc': 'http://purl.org/dc/elements/1.1/',
                    'opf': 'http://www.idpf.org/2007/opf'}
    ):
        print(_file_dec + 'other calibre staff found')
        break

    check_dupl_ids_insensitive(opftree)
    check_mime_types(opftree)

    # check for empty tours element
    for i in opftree.xpath('//opf:tours', namespaces=OPFNS):
        if len(list(i)) == 0:
            print(_file_dec + 'Obsolete empty <tours> element found')

    if enc_found:
        uid = None
        for dcid in opftree.xpath("//dc:identifier", namespaces=DCNS):
            if dcid.get("{http://www.idpf.org/2007/opf}scheme") == "UUID":
                if dcid.text[:9] == "urn:uuid:":
                    uid = dcid.text
                    break
            if dcid.text is not None:
                if dcid.text[:9] == "urn:uuid:":
                    uid = dcid.text
                    break
        if uid is None:
            print(_file_dec + 'UUID identifier in content.opf missing')
    return cont_src_list


def find_opf(epub):
    if epub.namelist()[0] != 'mimetype':
        print('* CRITICAL! mimetype file is missing or '
              'is not the first file in the archive.')
    elif epub.read('mimetype') != b'application/epub+zip':
        print('* CRITICAL! mimetype file has defined incorrect '
              'MIME type: ' + epub.read('mimetype'))
    try:
        cr_tree = etree.fromstring(epub.read('META-INF/container.xml'))
        opf_path = cr_tree.xpath('//cr:rootfile',
                                 namespaces=CRNS)[0].get('full-path')
    except:
        # try to find OPF file other way
        for i in epub.namelist():
            if i.endswith('.opf'):
                print('* CRITICAL! META-INF/container.xml '
                      'is missing or is broken.')
                return os.path.dirname(i), i
        print('* CRITICAL! Parsing container.xml failed!'
              'Probably broken EPUB file...')
        return None, None
    return os.path.dirname(opf_path), opf_path


def check_urls_in_css(singf, epub, prepnl, _file_dec):
    with epub.open(singf) as f:
        cl = re.sub(r'\/\*[^*]*\*+([^/*][^*]*\*+)*\/',
                    '', f.read().decode('utf-8')).splitlines()
        for line in cl:
            m = re.match(r'.+?url\([ ]?(\"|\')?(.+?)(\"|\')?[ ]?\)', line)
            if m is not None:
                check_url(unquote(m.group(2)), singf, prepnl, _file_dec)


def check_urls(singf, tree, prepnl, _file_dec):
    exclude_urls = ('http://', 'https://', 'mailto:', 'tel:', 'data:', '#')
    for u in tree.xpath('//*[@href or @src]'):
        if u.get('src'):
            url = u.get('src')
        elif u.get('href'):
            url = u.get('href')
        if url.lower().startswith(exclude_urls):
            continue
        url = unquote(url)
        if '#' in url:
            url = url.split('#')[0]
        check_url(url, singf, prepnl, _file_dec)


def check_url(url, singf, nlist, _file_dec):
    if not isinstance(url, str):
        url = url.decode('utf-8')
    try:
        relp = os.path.relpath(
            os.path.join("/".join(singf.split("/")[:-1]), url)
        ).replace('\\', '/')
    except ValueError:
        print('%sLinked resource "%s" in "%s" does NOT exist'
              % (_file_dec, url, singf))
        return None
    found_proper_url = False
    for n in nlist:
        if n == relp:
            found_proper_url = True
            break
    if not found_proper_url:
        print('%sLinked resource "%s" in "%s" does NOT exist'
              % (_file_dec, url, singf))


def check_body_font_family(singf, epub, _file_dec, is_body_family,
                           is_font_face, ff, sfound):
    with epub.open(singf) as f:
        fs = f.read()
        lis = fs.split('}')
        for e in lis:
            if 'body' in e or '.calibre' in e:
                try:
                    fft = re.search(r'font-family\s*:\s*(.*?)(;|$)',
                                    e).group(1)
                    ff = fft.split(',')[0]
                    is_body_family = True
                    sfound = singf
                except:
                    pass
            if ff != '':
                break
        if ff == '':
            for e in lis:
                if '@font-face' in e:
                    is_font_face = True
                    break
        else:
            ff = ff.replace('"', '').replace("'", '')
            for e in lis:
                if '@font-face' in e:
                    continue
                elif 'body' in e:
                    continue
                if re.search(r'font-family\s*:\s*(\"|\')?' + re.escape(ff), e):
                    print('%sProblematic (same as in body) '
                          'font-family: "%s" found in at least one other '
                          'declaration in file: "%s"'
                          % (_file_dec, ff, singf))
    return is_body_family, is_font_face, ff, sfound


def list_font_basic_properties(raw_file):
    try:
        font_family = lib.fntutls.get_all_font_names(
            raw_file)['family_name']
    except KeyError:
        font_family = 'NOT DEFINED'
    italic = lib.fntutls.get_font_characteristics(raw_file)[1]
    bold = lib.fntutls.get_font_characteristics(raw_file)[2]
    regular = lib.fntutls.get_font_characteristics(raw_file)[3]
    return font_family, regular, bold, italic


def qcheck(root, _file, alter, mod, is_list_fonts):
    if alter:
        _file_dec = _file + ': '
    else:
        _file_dec = '* '
    if not alter:
        print('')
        print('START qcheck for: ' + _file)
    try:
        epubfile = zipfile.ZipFile(os.path.join(root, _file))
    except zipfile.BadZipfile as e:
        print('%sCRITICAL! "%s" is invalid: "%s"' % (
              _file_dec, _file, str(e).decode(SFENC)))
        return None
    opf_root, opf_path = find_opf(epubfile)
    if not opf_path:
        if not alter:
            print('FINISH qcheck for: ' + _file)
        return None
    cont_src_list = qcheck_opf_file(opf_root, opf_path, epubfile, _file_dec,
                                    alter)
    prepnl = []
    for n in epubfile.namelist():
        if not isinstance(n, str):
            n = n.decode('utf-8')
        prepnl.append(os.path.relpath(n).replace('\\', '/'))
    is_body_family = is_font_face = False
    ff = sfound = ''
    for singlefile in epubfile.namelist():
        if '../' in singlefile:
            print(_file_dec + 'CRITICAL! Problematic path found'
                  ' in ePUB archive: ' + singlefile)
        if 'META-INF/encryption.xml' in singlefile:
            print('%sEncryption.xml file found: "%s" '
                  % (_file_dec, singlefile))
        elif 'jacket.xhtml' in singlefile.lower():
            print('%scalibre Jacket file found: %s'
                  % (_file_dec, singlefile))
        elif 'calibre_bookmarks.txt' in singlefile.lower():
            print('%scalibre bookmarks file found: %s'
                  % (_file_dec, singlefile))
        elif 'itunesmetadata.plist' in singlefile.lower():
            print('%siTunesMetadata file found: %s'
                  % (_file_dec, singlefile))
        elif (
                singlefile.lower().endswith('.otf') or
                singlefile.lower().endswith('.ttf')
        ):
            temp_font_dir = tempfile.mkdtemp()
            try:
                epubfile.extract(singlefile, temp_font_dir)
            except zipfile.BadZipfile:
                print(_file_dec + 'Font file: ' + singlefile +
                      ' is corrupted!')
                continue
            is_empty = False
            try:
                if os.path.getsize(
                        os.path.join(temp_font_dir, singlefile)
                ) == 0:
                    print('%sERROR! Font file "%s" is EMPTY!'
                          % (_file_dec, singlefile))
                    is_empty = True
            except (OSError, IOError) as e:
                    is_empty = True
                    print('%sERROR! Problem with file "%s": %s'
                          % (_file_dec, os.path.basename(singlefile),
                             str(e).decode(SFENC)))
            if not is_empty:
                is_font, signature = check_font(
                    os.path.join(temp_font_dir, singlefile)
                )
                if not is_font:
                    print('%sFont file "%s" is probably encrypted.'
                          ' Incorrect signature %r.'
                          % (_file_dec, singlefile, signature))
                elif is_list_fonts:
                    with open(os.path.join(temp_font_dir, singlefile),
                              'rb') as f:
                        c = f.read()
                        try:
                            print(
                                '%sFont info for %s, Family name: "%s", '
                                'isRegular: %s, isBold: %s, isItalic: %s' %
                                (
                                    _file_dec,
                                    singlefile,
                                    list_font_basic_properties(c)[0],
                                    list_font_basic_properties(c)[1],
                                    list_font_basic_properties(c)[2],
                                    list_font_basic_properties(c)[3]
                                )
                            )
                        except (lib.fntutls.UnsupportedFont,
                                struct.error) as e:
                            print(
                                '%sERROR! Problem with font file "%s": %s' %
                                (_file_dec, singlefile, e)
                            )

            if os.path.isdir(temp_font_dir):
                shutil.rmtree(temp_font_dir)
        elif singlefile.lower().endswith('.css'):
            with epubfile.open(singlefile) as f:
                cssutils.log.setLog(logging.getLogger(singlefile))
                cssutils.log.addHandler(streamhandler)
                cssutils.log.setLevel(logging.WARNING)
                cssutils.parseString(f.read(), validate=True)
            check_urls_in_css(singlefile, epubfile, prepnl, _file_dec)
            # TODO: not a real problem with file (make separate check for it)
            # is_body_family, is_font_face, ff, sfound\
            #     = check_body_font_family(
            #         singlefile, epubfile, _file_dec,
            #         is_body_family, is_font_face, ff, sfound
            #     )
        else:
            try:
                c = epubfile.read(singlefile)
                for key in entities.keys():
                    c = c.replace(key, entities[key])
                sftree = etree.fromstring(c)
            except:
                sftree = None
            if sftree is not None:
                check_urls(singlefile, sftree, prepnl, _file_dec)
                check_wm_info(singlefile, sftree, epubfile, _file_dec)
                check_display_none(singlefile, sftree, epubfile, _file_dec,
                                   cont_src_list)
    if is_body_family:
        if not mod:
            print('%sfont-family for body: "%s" found in "%s"'
                  % (_file_dec, ff, sfound))
    elif is_font_face:
        print('%sWarning! Potential "stripping font" problem!' % (_file_dec))
    if not alter:
        print('FINISH qcheck for: ' + _file)
