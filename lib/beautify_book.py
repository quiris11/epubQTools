#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

from __future__ import print_function
import os
import sys
import re
import shutil
import logging
from lib.epubqcheck import list_font_basic_properties
from urllib import unquote

SFENC = sys.getfilesystemencoding()
try:
    from lxml import etree
    import cssutils
except ImportError as e:
    sys.exit('! CRITICAL! ' + str(e).decode(SFENC))

HOME = os.path.expanduser("~")
DCNS = {'dc': 'http://purl.org/dc/elements/1.1/'}
OPFNS = {'opf': 'http://www.idpf.org/2007/opf'}
XHTMLNS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
NCXNS = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
XLXHTNS = {'xhtml': 'http://www.w3.org/1999/xhtml',
           'xlink': 'http://www.w3.org/1999/xlink'}

cssutils.log.setLevel(logging.CRITICAL)
cssutils.ser.prefs.omitLastSemicolon = False


def clean_meta_tags(opftree):

    def clean_meta_tag(meta):
        from HTMLParser import HTMLParser
        h = HTMLParser()
        if meta.text is None:
            return None
        meta.text = meta.text.replace('\r', ' ').replace('\n', ' ').strip()
        meta.text = h.unescape(meta.text)
        tree = etree.HTML(meta.text)
        clean_text = etree.tostring(tree, method="text", encoding="utf-8")
        meta.text = clean_text.decode('utf-8')

    tags = ['creator', 'title', 'description']
    for t in tags:
        dcs = opftree.xpath('//dc:' + t, namespaces=DCNS)
        for dc in dcs:
            clean_meta_tag(dc)


def change_font_family_value(cssvalue, new_name):
    cssvalue.value = new_name
    cssvalue._type = 'STRING'


def fix_property(prop, old_name, new_name, is_url):
    changed = False
    ff = prop.propertyValue
    for i in xrange(ff.length):
        val = ff.item(i)
        if (hasattr(val.value, 'lower') and
                val.value.lower() == old_name.lower()):
            if is_url:
                val.value = new_name
            else:
                change_font_family_value(val, new_name)
            changed = True
    return changed


def fix_declaration(style, old_name, new_name, is_url):
    changed = False
    if is_url:
        prop_list = ('src',)
    else:
        prop_list = ('font-family', 'font')
    for x in prop_list:
        prop = style.getProperty(x)
        if prop is not None:
            changed |= fix_property(prop, old_name, new_name, is_url)
    return changed


def fix_sheet(sheet, old_name, new_name, is_url):
    changed = False
    if is_url:
        rules_list = (cssutils.css.CSSRule.FONT_FACE_RULE,)
    else:
        rules_list = (cssutils.css.CSSRule.FONT_FACE_RULE,
                      cssutils.css.CSSRule.STYLE_RULE)
    for rule in sheet.cssRules:
        if rule.type in rules_list:
            if fix_declaration(rule.style, old_name, new_name, is_url):
                changed = True
    return changed


def replace_file(epub_dir, old_path, new_absolute_path):
    font_replaced = False
    old_absolute_path = os.path.join(epub_dir, old_path)
    if os.path.exists(old_absolute_path):
        os.remove(old_absolute_path)
        shutil.copyfile(new_absolute_path, os.path.join(
            os.path.dirname(old_absolute_path),
            os.path.basename(new_absolute_path)
        ))
        font_replaced = True
    if font_replaced:
        print('* File "%s" was replaced with "%s"...' % (
            os.path.basename(old_absolute_path),
            os.path.basename(new_absolute_path)
        ))


def update_css_font_families(epub_dir, opftree):

    def find_css_font_file_families(epub_dir, opftree):
        font_families = []
        css_items = etree.XPath(
            '//opf:item[@media-type="text/css"]',
            namespaces=OPFNS
        )(opftree)
        for c in css_items:
            css_file_path = os.path.join(epub_dir, c.get('href'))
            sheet = cssutils.parseFile(css_file_path,
                                       validate=True)
            for rule in sheet:
                if rule.type == rule.FONT_FACE_RULE:
                    css_font_family = None
                    font_file_family = None
                    for p in rule.style:
                        if p.name == 'font-family' and css_font_family is None:
                            try:
                                css_font_family = p.value.split(
                                    ',')[0].strip().strip('"').strip("'")
                            except:
                                continue
                            continue
                        if p.name == 'src' and font_file_family is None:
                            ffs = rule.style.getProperty(p.name).propertyValue
                            ff_url = ffs.item(0).value
                            with open(os.path.join(
                                os.path.dirname(css_file_path), ff_url
                            ), 'rb') as f:
                                lfp = list_font_basic_properties(f.read())
                                lfp = list(lfp)
                                if 'subset of' in lfp[0]:
                                    lfp[0] = re.sub(
                                        r'\w+?\s-\ssubset\sof\s', '',
                                        lfp[0]
                                    )
                                font_file_family = lfp[0]
                                continue
                    font_families.append([css_font_family, font_file_family])
            return font_families

    print('* Updating font-family in all CSS files...')
    ff_list = find_css_font_file_families(epub_dir, opftree)
    css_items = etree.XPath('//opf:item[@media-type="text/css"]',
                            namespaces=OPFNS)(opftree)
    for c in css_items:
        css_file_path = os.path.join(epub_dir, c.get('href'))
        sheet = cssutils.parseFile(css_file_path, validate=True)

        for ff in ff_list:
            fix_sheet(sheet, ff[0], ff[1], False)

        with open(os.path.join(epub_dir, c.get('href')), 'w') as f:
            f.write(sheet.cssText)


def replace_fonts(user_font_dir, epub_dir, ncxtree, opftree, pair_family):

    # TODO: replace also family-name in CSS

    def find_old_family_fonts(epub_dir, opftree, family_name):
        font_items = etree.XPath(
            '//opf:item[@media-type="application/vnd.ms-opentype"]',
            namespaces=OPFNS
        )(opftree)
        family_font_list = []
        for f in font_items:
            furl = f.get('href')
            with open(os.path.join(epub_dir, furl), 'rb') as f:
                lfp = list_font_basic_properties(f.read())
                lfp = list(lfp)
                if 'subset of' in lfp[0]:
                    lfp[0] = re.sub(r'\w+?\s-\ssubset\sof\s', '', lfp[0])
                if lfp[0] == family_name:
                    family_font_list.append([furl] + lfp)
        return family_font_list

    def find_new_family_fonts(user_font_dir, epub_dir, opftree, family_name,
                              is_all):
        family_font_list = []
        for root, dirs, files in os.walk(user_font_dir):
            for f in files:
                furl = os.path.join(root, f)
                if (
                    furl.lower().endswith('.ttf') or
                    furl.lower().endswith('.otf')
                ):
                    with open(os.path.join(furl), 'rb') as f:
                        try:
                            lfp = list_font_basic_properties(f.read())
                        except:
                            continue
                        if is_all:
                            family_font_list.append([furl] + list(lfp))
                        elif lfp[0] == family_name:
                            family_font_list.append([furl] + list(lfp))
        return family_font_list

    if pair_family is not None and user_font_dir is not None:
        if ',' in pair_family:
            of = pair_family.split(',')[0].strip("'")
            nf = pair_family.split(',')[1].strip("'")
            print('* Replacing old font family "%s" with '
                  'new font family "%s"...' % (of, nf))
        else:
            print('! Font replacing FAILED! You should provide pair of font '
                  'families comma separated: "old,new"')
            return None
    else:
        return None
    new_font_files = find_new_family_fonts(user_font_dir, epub_dir, opftree,
                                           nf, False)
    old_font_files = find_old_family_fonts(epub_dir, opftree, of)
    if old_font_files == []:
        print('! No font with family name "%s" was found in EPUB file'
              '...' % (of))
    if new_font_files == []:
        print('! No font with family name "%s" was found in provided '
              'directory "%s"...' % (nf, user_font_dir))
        print('* Choose from the below list of font family names:')
        for i in find_new_family_fonts(user_font_dir, epub_dir, opftree,
                                       nf, True):
            print(
                '* Font info for %s, Family name: "%s", '
                'isRegular: %s, isBold: %s, isItalic: %s' %
                (
                    os.path.basename(i[0]), i[1], i[2], i[3], i[4]
                )
            )
    for o in old_font_files:
        for n in new_font_files:
            if o[2] == n[2] and o[3] == n[3] and o[4] == n[4]:
                nfp = os.path.join(os.path.dirname(o[0]),
                                   os.path.basename(n[0]))
                rename_replace_files(opftree, ncxtree, epub_dir, o[0], nfp,
                                     n[0])


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
            xhtree = etree.parse(os.path.join(epub_dir, xhtml_url),
                                 parser=etree.XMLParser(recover=False))
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


def rename_replace_files(opftree, ncxtree, epub_dir, old_name_path,
                         new_name_path, new_absolute_path):

    def fix_references_in_xhtml(opftree, epub_dir, old_name_path,
                                new_name_path):
        xhtml_items = etree.XPath(
            '//opf:item[@media-type="application/xhtml+xml"]',
            namespaces=OPFNS
        )(opftree)

        for i in xhtml_items:
            xhtml_url = i.get('href')
            xhtree = etree.parse(os.path.join(epub_dir, xhtml_url),
                                 parser=etree.XMLParser(recover=False))
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
            sheet = cssutils.parseFile(os.path.join(epub_dir, c.get('href')),
                                       validate=True)
            old_css_path = os.path.relpath(
                old_name_path,
                os.path.dirname(c.get('href'))
            ).replace('\\', '/')
            new_css_path = os.path.relpath(
                new_name_path,
                os.path.dirname(c.get('href'))
            ).replace('\\', '/')

            fix_sheet(sheet, old_css_path, new_css_path, True)

            with open(os.path.join(epub_dir, c.get('href')), 'w') as f:
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
        if new_absolute_path:
            replace_file(epub_dir, old_name_path, new_absolute_path)
        else:
            os.rename(os.path.join(epub_dir, old_name_path),
                      os.path.join(epub_dir, new_name_path))
        ncxtree = update_ncx(ncxtree, old_name_path, new_name_path)
        update_css(opftree, epub_dir, old_name_path, new_name_path)
        fix_references_in_xhtml(opftree, epub_dir, old_name_path,
                                new_name_path)
    return opftree, ncxtree


def most_common(lst):
    return max(set(lst), key=lst.count)


def write_file_changes_back(tree, file_path):
    with open(file_path, 'w') as f:
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
                rename_replace_files(
                    opftree, ncxtree, epub_dir, r.get('href'),
                    os.path.join(most_xthml_dir, 'cover.html'), False
                )


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
                rename_replace_files(opftree, ncxtree, epub_dir, cover_file,
                                     new_name_path, False)
                break


def make_cover_item_first(opftree):
    try:
        meta_cover_id = opftree.xpath('//opf:meta[@name="cover"]',
                                      namespaces=OPFNS)[0].get('content')
    except IndexError:
        print('! ERROR! Unable to make cover item first. '
              'Cover is not properly defined...')
        return None
    cover_item = opftree.xpath('//opf:item[@id="' + meta_cover_id + '"]',
                               namespaces=OPFNS)[0]
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
        xhtree = etree.parse(os.path.join(epub_dir, xhtml_url),
                             parser=etree.XMLParser(recover=False))
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


def beautify_book(root, f, user_font_dir, pair_family):
    from lib.epubqfix import pack_epub
    from lib.epubqfix import unpack_epub
    from lib.epubqfix import clean_temp
    from lib.epubqfix import find_roots
    f = f.replace('.epub', '_moh.epub')
    print('START beautify for: ' + f.decode(SFENC))
    tempdir = unpack_epub(os.path.join(root, f))
    opf_dir, opf_file, is_fixed = find_roots(tempdir)
    epub_dir = os.path.join(tempdir, opf_dir)
    opf_path = os.path.join(tempdir, opf_file)
    parser = etree.XMLParser(remove_blank_text=True)
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
    replace_fonts(user_font_dir, epub_dir, ncxtree, opftree, pair_family)
    clean_meta_tags(opftree)
    # temprorary disabled due critical problems
    # update_css_font_families(epub_dir, opftree)

    write_file_changes_back(opftree, opf_path)
    write_file_changes_back(ncxtree, ncx_path)
    pack_epub(os.path.join(root, f), tempdir)
    clean_temp(tempdir)
    print('FINISH beautify for: ' + f.decode(SFENC))
