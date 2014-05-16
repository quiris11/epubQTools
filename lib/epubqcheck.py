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
from urllib import unquote
from lxml import etree
from lib.htmlconstants import entities


OPFNS = {'opf': 'http://www.idpf.org/2007/opf'}
XHTMLNS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
DCNS = {'dc': 'http://purl.org/dc/elements/1.1/'}
NCXNS = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
SVGNS = {'svg': 'http://www.w3.org/2000/svg'}
CRNS = {'cr': 'urn:oasis:names:tc:opendocument:xmlns:container'}
SFENC = sys.getfilesystemencoding()
encryption_file_found = False


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


def check_wm_info(singlefile, epub, _file_dec):
    try:
        tree = etree.fromstring(epub.read(singlefile))
    except:
        return 0
    alltexts = etree.XPath('//xhtml:body//text()',
                           namespaces=XHTMLNS)(tree)
    alltext = ' '.join(alltexts)
    alltext = alltext.replace(u'\u00AD', '').strip()
    if alltext == 'Plik jest zabezpieczony znakiem wodnym':
        print(_file_dec + 'WM info file found: ' + singlefile)


def check_display_none(singlefile, epub, _file_dec):
    try:
        tree = etree.fromstring(epub.read(singlefile))
    except:
        return 0
    styles = etree.XPath('//*[@style]',
                         namespaces=XHTMLNS)(tree)
    for s in styles:
        if ('display: none' or 'display:none') in s.get('style'):
            print(_file_dec + 'Element with display:none style found: ' +
                  etree.tostring(s))


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
    html_cover_path = etree.XPath('//opf:reference[@type="cover"]',
                                  namespaces=OPFNS)(tree)[0].get('href')
    try:
        meta_cover_id = etree.XPath('//opf:meta[@name="cover"]',
                                    namespaces=OPFNS)(tree)[0].get('content')
    except IndexError:
        print(_file_dec + 'No meta cover image defined.')
        return 0
    try:
        meta_cover_path = etree.XPath(
            '//opf:item[@id="' + meta_cover_id + '"]',
            namespaces=OPFNS
        )(tree)[0].get('href')
    except IndexError:
        print(_file_dec + 'Meta cover does not properly defined.')
        return 0
    parser = etree.XMLParser(recover=True)
    try:
        html_cover_tree = etree.fromstring(
            epub.read(os.path.relpath(os.path.join(
                dir, html_cover_path
            )).replace('\\', '/')),
            parser
        )
    except KeyError, e:
        print(_file_dec + 'Problem with parsing HTML cover: ' + str(e))
        html_cover_tree = None
        pass
    try:
        cover_texts = etree.XPath(
            '//xhtml:body//text()',
            namespaces=XHTMLNS
        )(html_cover_tree)
        cover_texts = ' '.join(cover_texts).strip()
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
                svgimg.get('{http://www.w3.org/1999/xlink}href').find(
                    meta_cover_path
                ) == -1
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


def qcheck_opf_file(opf_root, opf_path, _epubfile, _file_dec):

    def check_orphan_files(epub, opftree, root, _file_dec):
        def is_exluded(name):
            excludes = ['mimetype',
                        'META-INF/container.xml',
                        'META-INF/com.apple.ibooks.display-options.xml',
                        'META-INF/encryption.xml', '/',
                        opf_path]
            for e in excludes:
                if name.endswith(e):
                    return True
            return False

        for n in epub.namelist():
            if not isinstance(n, unicode):
                n = n.decode('utf-8')
            if 'calibre_bookmarks.txt' in n:
                print('%scalibre bookmarks file found: %s' % (_file_dec, n))
            elif 'itunesmetadata.plist' in n.lower():
                print('%siTunesMetadata file found: %s' % (_file_dec, n))
            elif not is_exluded(n):
                found = False
                for i in opftree.xpath('//*[@href]'):
                    if os.path.relpath(n) == os.path.relpath(
                        os.path.join(root, i.get('href'))
                    ):
                        found = True
                if not found:
                    print('%sORPHAN file "%s" does NOT defined in OPF file'
                          % (_file_dec, os.path.relpath(os.path.join(n))))

    def check_font_mime_types(tree):
        items = tree.xpath('//opf:item[@href]', namespaces=OPFNS)
        for i in items:
            if (
                    i.get('href').lower().endswith('.otf') and
                    i.get('media-type') != 'application/vnd.ms-opentype'
            ):
                print('%sFont file "%s" has incorrect media-type "%s".' % (
                    _file_dec, i.get('href'), i.get('media-type')
                ))
            elif (
                    i.get('href').lower().endswith('.ttf') and
                    i.get('media-type') != 'application/x-font-truetype'
            ):
                print('%sFont file "%s" has incorrect media-type "%s".' % (
                    _file_dec, i.get('href'), i.get('media-type')
                ))

    if opf_root == '':
        _folder = ''
    else:
        _folder = opf_root + '/'
    opftree = etree.fromstring(_epubfile.read(opf_path))
    opftree = unquote_urls(opftree)
    check_orphan_files(_epubfile, opftree, _folder, _file_dec)
    if not opftree.xpath('//opf:metadata', namespaces=OPFNS):
        print(_file_dec + 'CRITICAL! No metadata defined in OPF file...')
    if not opftree.xpath('//dc:creator', namespaces=DCNS):
        print(_file_dec + 'CRITICAL! dc:creator (book author) element not '
              'defined in OPF file...')
    elif opftree.xpath('//dc:creator', namespaces=DCNS)[0].text.isupper():
        print(_file_dec + 'dc:creator (book author) UPPERCASED: "%s". '
              'Consider changing...' % opftree.xpath('//dc:creator',
                                                     namespaces=DCNS)[0].text)
    if not opftree.xpath('//dc:title', namespaces=DCNS):
        print(_file_dec + 'CRITICAL! dc:title (book title) element not '
              'defined in OPF file...')
    elif opftree.xpath('//dc:title', namespaces=DCNS)[0].text.isupper():
        print(_file_dec + 'dc:title (book title) UPPERCASED: "%s". '
              'Consider changing...' % opftree.xpath('//dc:title',
                                                     namespaces=DCNS)[0].text)
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
        print(_file_dec + 'No cover guide element defined.')
    elif _refcovcount > 1:
        print(_file_dec + 'Multiple cover guide elements defined.')

    if _reftoccount == 0:
        print(_file_dec + 'No TOC guide element defined.')
    elif _reftoccount > 1:
        print(_file_dec + 'Multiple TOC guide elements defined.')

    if _reftextcount == 0:
        pass  # print(_file_dec + 'No text guide element defined.')
    elif _reftextcount > 1:
        print(_file_dec + 'Multiple text guide elements defined.')

    if len(_metacovers) == 0 and _refcovcount == 0:
        find_cover_image(opftree, _file_dec)

    if _refcovcount == 1 and len(_metacovers) == 1:
        check_meta_html_covers(opftree, _folder, _epubfile, _file_dec)

    check_dl_in_html_toc(opftree, _folder, _epubfile, _file_dec)

    _htmlfiletags = etree.XPath(
        '//opf:item[@media-type="application/xhtml+xml"]', namespaces=OPFNS
    )(opftree)
    _linkfound = _unbfound = _ufound = _wmfound = metcharfound = False
    for _htmlfiletag in _htmlfiletags:
        _htmlfilepath = _htmlfiletag.get('href')
        parser = etree.XMLParser(recover=False)
        try:
            html_str = _epubfile.read(os.path.relpath(os.path.join(
                _folder, _htmlfilepath
            )).replace('\\', '/'))
            for key in entities.iterkeys():
                html_str = html_str.replace(key, entities[key])
            _xhtmlsoup = etree.fromstring(html_str, parser)
        except KeyError, e:
            print(_file_dec + 'Problem with a file: ' + str(e))
            continue
        except etree.XMLSyntaxError, e:
            print(_file_dec + 'XML file: ' + _htmlfilepath +
                  ' not well formed: "' + str(e) + '"')
            continue
#         for u in _xhtmlsoup.xpath('//*[@href or @src]'):
#             if u.get('src'):
#                 url = u.get('src')
#             elif u.get('href'):
#                 url = u.get('href')
#             if 'http://' in url or 'mailto:' in url:
#                 continue
#             if '%' in url:
#                 print('%sEncoded URLs: %s found '
#                       'in html file: %s' % (_file_dec, url, _htmlfilepath))
        if _wmfound is False:
            _watermarks = etree.XPath('//*[starts-with(text(),"==")]',
                                      namespaces=XHTMLNS)(_xhtmlsoup)
            if len(_watermarks) > 0:
                print(_file_dec + 'Potential problematic WM found...')
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

        if _reftoccount == 0 and _alltext.find(u'Spis treści') != -1:
                print(_file_dec + 'Html TOC candidate found: ' +
                      _htmlfilepath)
        check_hyphs = False
        if check_hyphs:
            if not _ufound and _alltext.find(u'\u00AD') != -1:
                print(_file_dec + 'U+00AD hyphenate marks found.')
                _ufound = True
            if not _unbfound and _alltext.find(u'\u00A0') != -1:
                print(_file_dec + 'U+00A0 non-breaking space found.')
                _unbfound = True
        _links = etree.XPath('//xhtml:link', namespaces=XHTMLNS)(_xhtmlsoup)
        for _link in _links:
            if not _linkfound and (_link.get('type') is None):
                _linkfound = True
                print(_file_dec + 'At least one xhtml file has link tag '
                      'without type attribute defined')

    #Check dtb:uid - should be identical go dc:identifier
    ncxfile = etree.XPath('//opf:item[@media-type="application/x-dtbncx+xml"]',
                          namespaces=OPFNS)(opftree)[0].get('href')
    ncxtree = etree.fromstring(_epubfile.read(os.path.relpath(
        os.path.join(_folder, ncxfile)
    ).replace('\\', '/')))
    uniqid = etree.XPath('//opf:package',
                         namespaces=OPFNS)(opftree)[0].get('unique-identifier')
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
        metadtd = etree.XPath('//ncx:meta[@name="dtb:uid"]',
                              namespaces=NCXNS)(ncxtree)[0]
        if metadtd.get('content') != dc_identifier:
            print(_file_dec + 'dtd:uid and dc:identifier mismatched')
    except IndexError:
        print(_file_dec + 'dtd:uid not properly defined')

    for meta in opftree.xpath("//opf:meta[starts-with(@name, 'calibre')]",
                              namespaces=OPFNS):
        print(_file_dec + 'calibre staff found')
        break
    for dcid in opftree.xpath(
        "//dc:identifier[@opf:scheme='calibre']",
        namespaces={'dc': 'http://purl.org/dc/elements/1.1/',
                    'opf': 'http://www.idpf.org/2007/opf'}
    ):
        print(_file_dec + 'other calibre staff found')
        break

    check_font_mime_types(opftree)

    if encryption_file_found:
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


def find_opf(epub):
    try:
        cr_tree = etree.fromstring(epub.read('META-INF/container.xml'))
        opf_path = cr_tree.xpath('//cr:rootfile',
                                 namespaces=CRNS)[0].get('full-path')
    except:
        print('Parsing container.xml failed. Not an EPUB file?')
        return 0, 0
    return os.path.dirname(opf_path), opf_path


def check_urls(singf, epub, _file_dec):
    if singf.endswith('.css'):
        with epub.open(singf) as f:
            for line in f:
                m = re.match(r'.+?url\([ ]?(\"|\')?(.+?)(\"|\')?[ ]?\)', line)
                if m is not None:
                    check_url(unquote(m.group(2)), singf, epub, _file_dec)
    else:
        try:
            tree = etree.fromstring(epub.read(singf))
        except:
            return 0
        exclude_urls = ('http://', 'https://', 'mailto:', 'tel:', 'data:', '#')
        for u in tree.xpath('//*[@href or @src]'):
            if u.get('src'):
                url = u.get('src')
            elif u.get('href'):
                url = u.get('href')
            if url.startswith(exclude_urls):
                continue
            url = unquote(url)
            if '#' in url:
                url = url.split('#')[0]
            check_url(url, singf, epub, _file_dec)


def check_url(url, singf, epub, _file_dec):
    if not isinstance(url, unicode):
        url = url.decode('utf-8')
    relp = os.path.relpath(os.path.join("/".join(
        singf.split("/")[:-1]), url
    ))
    relp = relp.replace('\\', '/')
    found_proper_url = False
    for n in epub.namelist():
        if not isinstance(n, unicode):
            n = n.decode('utf-8')
        if n == relp:
            found_proper_url = True
    if not found_proper_url:
        print('%sLinked resource "%s" in "%s" does NOT exist'
              % (_file_dec, url, singf))


def qcheck(_documents, _moded, alter):
    if _moded:
        fe = '_moh.epub'
        nfe = '_org.epub'
    else:
        fe = '.epub'
        nfe = '_moh.epub'
    for root, dirs, files in os.walk(_documents):
        for _file in files:
            file_dec = _file.decode(SFENC)
            if alter:
                _file_dec = file_dec + ': '
            else:
                _file_dec = '* '
            if _file.endswith(fe) and not _file.endswith(nfe):
                if not alter:
                    print('')
                    print('START qcheck for: ' + file_dec)
                encryption_file_found = False
                epubfile = zipfile.ZipFile(os.path.join(root, _file))
                opf_root, opf_path = find_opf(epubfile)
                qcheck_opf_file(opf_root, opf_path, epubfile, _file_dec)
                for singlefile in epubfile.namelist():
                    if 'META-INF/encryption.xml' in singlefile:
                        encryption_file_found = True
                        print(_file_dec + 'Encryption.xml file found. '
                              'Embedded fonts probably are encrypted...')
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
                        if os.path.getsize(
                                os.path.join(temp_font_dir, singlefile)
                        ) == 0:
                            print('%sFont file "%s" is EMPTY!'
                                  % (_file_dec, singlefile))
                            is_empty = True
                        if not is_empty:
                            is_font, signature = check_font(
                                os.path.join(temp_font_dir, singlefile)
                            )
                            if not is_font:
                                print('%sFont file "%s" is probably encrypted.'
                                      ' Incorrect signature %r.'
                                      % (_file_dec, singlefile, signature))
                        if os.path.isdir(temp_font_dir):
                            shutil.rmtree(temp_font_dir)
                    else:
                        check_urls(singlefile, epubfile, _file_dec)
                        check_wm_info(singlefile, epubfile, _file_dec)
                        check_display_none(singlefile, epubfile, _file_dec)
                if not alter:
                    print('FINISH qcheck for: ' + file_dec)
