#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#


import os
import sys
import re
import logging
from collections import Counter
from urllib.parse import unquote

try:
    from lxml import etree
    import css_parser
except ImportError as e:
    sys.exit('! CRITICAL! ' + str(e) + ' (install with: '
             'python -m pip install lxml css_parser)')

HOME = os.path.expanduser("~")
DCNS = {'dc': 'http://purl.org/dc/elements/1.1/'}
OPFNS = {'opf': 'http://www.idpf.org/2007/opf'}
XHTMLNS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
NCXNS = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
XLXHTNS = {'xhtml': 'http://www.w3.org/1999/xhtml',
           'xlink': 'http://www.w3.org/1999/xlink'}

css_parser.log.setLevel(logging.CRITICAL)
css_parser.ser.prefs.omitLastSemicolon = False


def clean_meta_tags(opftree):

    def clean_meta_tag(meta):
        import html
        if meta.text is None:
            return None
        meta.text = meta.text.replace('\r', ' ').replace('\n', ' ').strip()
        meta.text = html.unescape(meta.text)
        try:
            tree = etree.HTML(meta.text)
        except etree.XMLSyntaxError:
            return None
        try:
            clean_text = etree.tostring(tree, method="text", encoding="utf-8")
            meta.text = clean_text.decode('utf-8')
        except TypeError:
            return None

    tags = ['creator', 'title', 'description']
    for t in tags:
        dcs = opftree.xpath('//dc:' + t, namespaces=DCNS)
        for dc in dcs:
            clean_meta_tag(dc)


def fix_property(prop, old_name, new_name):
    changed = False
    ff = prop.propertyValue
    for i in range(ff.length):
        val = ff.item(i)
        if (hasattr(val.value, 'lower') and
                val.value.lower() == old_name.lower()):
            val.value = new_name
            changed = True
    return changed


def fix_sheet(sheet, old_name, new_name):
    """Replace the URL old_name with new_name in "src" of @font-face
    rules."""
    changed = False
    for rule in sheet.cssRules:
        if rule.type == css_parser.css.CSSRule.FONT_FACE_RULE:
            prop = rule.style.getProperty('src')
            if prop is not None and fix_property(prop, old_name, new_name):
                changed = True
    return changed


def fix_body_id_links(opftree, epub_dir, ncxtree):

    def get_body_id_list(opftree, epub_dir):
        # build list with body tags with id attributes
        xhtml_items = etree.XPath(
            '//opf:item[@media-type="application/xhtml+xml"]',
            namespaces=OPFNS
        )(opftree)
        body_id_list = []
        for i in xhtml_items:
            xhtml_url = i.get('href')
            try:
                xhtree = etree.parse(os.path.join(epub_dir, xhtml_url),
                                     parser=etree.XMLParser(recover=False))
            except etree.XMLSyntaxError as e:
                print('! ERROR! File skipped: ' + os.path.basename(xhtml_url) +
                      '. NOT well formed: "' + str(e) + '"')
                return []
            try:
                body_id = etree.XPath('//xhtml:body[@id]',
                                      namespaces=XHTMLNS)(xhtree)[0]
            except IndexError:
                body_id = None
            if body_id is not None:
                body_id_list.append(os.path.basename(
                    xhtml_url
                ) + '#' + body_id.get('id'))
        return body_id_list

    body_id_list = get_body_id_list(opftree, epub_dir)
    contents = etree.XPath('//ncx:content', namespaces=NCXNS)(ncxtree)
    content_src_list = []
    for c in contents:
        content_src_list.append(c.get('src'))
    for c in contents:
        if (c.get('src').split('/')[-1] in body_id_list and
                c.get('src').split('#')[0] not in content_src_list):
            print("* Fixing body_id link: " + c.get('src'))
            c.set('src', c.get('src').split('#')[0])


def rename_file(opftree, ncxtree, epub_dir, old_name_path, new_name_path):

    def fix_references_in_xhtml(opftree, epub_dir, old_name_path,
                                new_name_path):
        xhtml_items = etree.XPath(
            '//opf:item[@media-type="application/xhtml+xml"]',
            namespaces=OPFNS
        )(opftree)

        for i in xhtml_items:
            xhtml_url = i.get('href')
            try:
                xhtree = etree.parse(os.path.join(epub_dir, xhtml_url),
                                     parser=etree.XMLParser(recover=False))
            except (etree.XMLSyntaxError, IOError):
                continue
            urls = etree.XPath('//*[@href or @src or @xlink:href]',
                               namespaces=XLXHTNS)(xhtree)
            exclude_urls = ('http://', 'https://', 'mailto:',
                            'tel:', 'data:', '#')
            xhtml_dir = os.path.dirname(os.path.join(epub_dir, xhtml_url))
            diff_path = os.path.relpath(
                os.path.dirname(os.path.join(epub_dir, old_name_path)),
                os.path.dirname(os.path.join(epub_dir, new_name_path))
            )
            for u in urls:
                if u.get('src'):
                    url = u.get('src')
                elif u.get('href'):
                    url = u.get('href')
                elif u.get('{http://www.w3.org/1999/xlink}href'):
                    url = u.get('{http://www.w3.org/1999/xlink}href')
                if url.lower().startswith(exclude_urls):
                    continue
                url = unquote(url)
                if '#' in url:
                    frag_url = '#' + url.split('#')[1]
                    url = url.split('#')[0]
                else:
                    frag_url = ''
                if os.path.basename(
                    xhtml_url
                ) == os.path.basename(new_name_path):
                    if u.get('src'):
                        u.set('src', os.path.join(
                            diff_path, u.get('src')
                        ).replace('\\', '/') + frag_url)
                    elif u.get('href'):
                        u.set('href', os.path.join(
                            diff_path, u.get('href')
                        ).replace('\\', '/') + frag_url)
                    elif u.get('{http://www.w3.org/1999/xlink}href'):
                        u.set(
                            '{http://www.w3.org/1999/xlink}href',
                            os.path.join(
                                diff_path,
                                u.get('{http://www.w3.org/1999/xlink}href')
                            ).replace('\\', '/') + frag_url
                        )
                if os.path.basename(url) == os.path.basename(old_name_path):
                    if u.get('src'):
                        u.set('src', os.path.relpath(
                            os.path.join(epub_dir, new_name_path), xhtml_dir
                        ).replace('\\', '/') + frag_url)
                    elif u.get('href'):
                        u.set('href', os.path.relpath(
                            os.path.join(epub_dir, new_name_path), xhtml_dir
                        ).replace('\\', '/') + frag_url)
                    elif u.get('{http://www.w3.org/1999/xlink}href'):
                        u.set(
                            '{http://www.w3.org/1999/xlink}href',
                            os.path.relpath(
                                os.path.join(epub_dir, new_name_path),
                                xhtml_dir
                            ).replace('\\', '/') + frag_url
                        )
            write_file_changes_back(xhtree, os.path.join(epub_dir, xhtml_url))

    def update_css(opftree, epub_dir, old_name_path, new_name_path):
        css_items = etree.XPath(
            '//opf:item[@media-type="text/css"]',
            namespaces=OPFNS
        )(opftree)
        for c in css_items:
            sheet = css_parser.parseFile(os.path.join(
                epub_dir, c.get('href')), validate=True)
            old_css_path = os.path.relpath(
                old_name_path,
                os.path.dirname(c.get('href'))
            ).replace('\\', '/')
            new_css_path = os.path.relpath(
                new_name_path,
                os.path.dirname(c.get('href'))
            ).replace('\\', '/')

            fix_sheet(sheet, old_css_path, new_css_path)

            with open(os.path.join(epub_dir, c.get('href')), 'wb') as f:
                f.write(sheet.cssText)

    def update_opf(opftree, old_name_path, new_name_path):
        items = etree.XPath('//opf:item[@href]', namespaces=OPFNS)(opftree)
        for i in items:
            if i.get('href') == new_name_path:
                # if new_name_path exists unable to continue
                print("! New file name is already taken by other file...")
                return opftree, False
        for i in items:
            if i.get('href') == old_name_path:
                i.set('href', new_name_path.replace('\\', '/'))
                break
        references = etree.XPath('//opf:reference[@href]',
                                 namespaces=OPFNS)(opftree)
        for r in references:
            if r.get('href') == old_name_path:
                r.set('href', new_name_path.replace('\\', '/'))
        return opftree, True

    def update_ncx(ncxtree, old_name_path, new_name_path):
        contents = etree.XPath('//ncx:content', namespaces=NCXNS)(ncxtree)
        for c in contents:
            if c.get('src') == old_name_path:
                c.set('src', new_name_path.replace('\\', '/'))

    opftree, is_updated = update_opf(opftree, old_name_path, new_name_path)
    if is_updated:
        try:
            os.rename(os.path.join(epub_dir, old_name_path),
                      os.path.join(epub_dir, new_name_path))
        except WindowsError:
            os.unlink(os.path.join(epub_dir, new_name_path))
            os.rename(os.path.join(epub_dir, old_name_path),
                      os.path.join(epub_dir, new_name_path))
        ncxtree = update_ncx(ncxtree, old_name_path, new_name_path)
        update_css(opftree, epub_dir, old_name_path, new_name_path)
        fix_references_in_xhtml(opftree, epub_dir, old_name_path,
                                new_name_path)
    return opftree, ncxtree


def most_common(lst):
    # on a tie the first element wins (independent of the string hash seed)
    return Counter(lst).most_common(1)[0][0]


def write_file_changes_back(tree, file_path):
    with open(file_path, 'wb') as f:
        f.write(etree.tostring(tree.getroot(), pretty_print=True,
                standalone=False, xml_declaration=True, encoding='utf-8'))


def rename_calibre_cover(opftree, ncxtree, epub_dir):
    for r in etree.XPath('//opf:reference[@type="cover"]',
                         namespaces=OPFNS)(opftree):
        if os.path.basename(r.get('href')) == 'titlepage.xhtml':
            print("* Renaming calibre cover file to 'cover.html'...")
            xhtml_items = etree.XPath(
                '//opf:item[@media-type="application/xhtml+xml"]',
                namespaces=OPFNS
            )(opftree)
            xhtml_dirs = []
            for i in xhtml_items:
                xhtml_dirs.append(os.path.dirname(i.get('href')))
            most_xthml_dir = most_common(xhtml_dirs)
            if most_xthml_dir != '':
                pass
            try:
                rename_file(
                    opftree, ncxtree, epub_dir, r.get('href'),
                    os.path.join(most_xthml_dir, 'cover.html')
                )
            except WindowsError:
                pass


def rename_cover_img(opftree, ncxtree, epub_dir):
    try:
        meta_cover_id = opftree.xpath('//opf:meta[@name="cover"]',
                                      namespaces=OPFNS)[0].get('content')
    except IndexError:
        print('! ERROR! Unable to rename cover file. '
              'Cover file is not properly defined...')
        return None
    try:
        cover_item = opftree.xpath('//opf:item[@id="' + meta_cover_id + '"]',
                                   namespaces=OPFNS)[0]
    except IndexError:
        print('! ERROR! Unable to rename cover file. '
              'Cover is not properly defined...')
        return None
    cover_file = cover_item.get('href')
    cover_mime = cover_item.get('media-type')

    if os.path.splitext(os.path.basename(cover_file))[0] != 'cover':
        extensions = [os.path.splitext(os.path.basename(cover_file))[1]]
        if cover_mime == 'image/jpeg':
            extensions += ['.jpg', '.jpeg', '.jpe']
        for e in extensions:
            new_name_path = os.path.join(os.path.dirname(cover_file),
                                         'cover' + e)
            if not os.path.isfile(os.path.join(epub_dir, new_name_path)):
                print("* Renaming cover image to: " + new_name_path)
                rename_file(opftree, ncxtree, epub_dir, cover_file,
                            new_name_path)
                break


def make_cover_item_first(opftree):
    try:
        meta_cover_id = opftree.xpath('//opf:meta[@name="cover"]',
                                      namespaces=OPFNS)[0].get('content')
        cover_item = opftree.xpath('//opf:item[@id="' + meta_cover_id + '"]',
                                   namespaces=OPFNS)[0]
    except IndexError:
        print('! ERROR! Unable to make cover item first. '
              'Cover is not properly defined...')
        return None
    manifest = cover_item.getparent()
    if manifest[0] != cover_item:
        print('* Make cover image item first...')
        manifest.remove(cover_item)
        manifest.insert(0, cover_item)


def make_content_src_list(ncxtree):
    contents = etree.XPath('//ncx:content[@src]', namespaces=NCXNS)(ncxtree)
    cont_src_list = []
    for c in contents:
        cont_src_list.append(c.get('src').split('/')[-1])
    return cont_src_list


def fix_display_none(opftree, epub_dir, cont_src_list):
    xhtml_items = etree.XPath(
        '//opf:item[@media-type="application/xhtml+xml"]',
        namespaces=OPFNS
    )(opftree)
    for i in xhtml_items:
        is_updated = False
        xhtml_url = i.get('href')
        try:
            xhtree = etree.parse(os.path.join(epub_dir, xhtml_url),
                                 parser=etree.XMLParser(recover=False))
        except etree.XMLSyntaxError as e:
            print('! ERROR! File skipped: ' + os.path.basename(xhtml_url) +
                  '. NOT well formed: "' + str(e) + '"')
            return []
        styles = etree.XPath('//*[@style]',
                             namespaces=XHTMLNS)(xhtree)
        for s in styles:
            if (
                (
                    ('display: none' in s.get('style')) or
                    ('display:none' in s.get('style'))
                ) and (os.path.basename(
                       xhtml_url) + '#' + str(s.get('id'))) in cont_src_list
            ):
                print('* Replacing problematic style: none with '
                      'visibility: hidden...')
                stylestr = re.sub(r'display\s*:\s*none',
                                  'visibility: hidden; height: 0',
                                  s.get('style'))
                s.set('style', stylestr)
                is_updated = True
        if is_updated:
            write_file_changes_back(xhtree, os.path.join(epub_dir, xhtml_url))


def beautify_book(root, f):
    from .epubqfix import pack_epub
    from .epubqfix import unpack_epub
    from .epubqfix import clean_temp
    from .epubqfix import find_roots
    # same name as in qfix (also for '.EPUB' or '.epub' inside the name)
    f = os.path.splitext(f)[0] + '_moh.epub'
    print('START beautify for: ' + f)
    tempdir = unpack_epub(os.path.join(root, f))
    opf_dir, opf_file, is_fixed = find_roots(tempdir)
    epub_dir = os.path.join(tempdir, opf_dir)
    opf_path = os.path.join(tempdir, opf_file)
    parser = etree.XMLParser(remove_blank_text=True, encoding='utf-8')
    opftree = etree.parse(opf_path, parser)
    ncxfile = etree.XPath(
        '//opf:item[@media-type="application/x-dtbncx+xml"]',
        namespaces=OPFNS
    )(opftree)[0].get('href')
    ncx_path = os.path.join(epub_dir, ncxfile)
    ncxtree = etree.parse(ncx_path, parser)

    rename_calibre_cover(opftree, ncxtree, epub_dir)
    rename_cover_img(opftree, ncxtree, epub_dir)
    fix_body_id_links(opftree, epub_dir, ncxtree)
    make_cover_item_first(opftree)
    cont_src_list = make_content_src_list(ncxtree)
    fix_display_none(opftree, epub_dir, cont_src_list)

    clean_meta_tags(opftree)

    write_file_changes_back(opftree, opf_path)
    write_file_changes_back(ncxtree, ncx_path)
    pack_epub(os.path.join(root, f), tempdir)
    clean_temp(tempdir)
    print('FINISH beautify for: ' + f)
