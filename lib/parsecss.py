#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

from __future__ import print_function
import os
import cssutils


def rename_font_family(old_name, new_name, sheet):
    for r in sheet:
        for p in r.style:
            if p.name == 'font-family' and (old_name in p.value):
                print('1', p.name, p.value)
                p.value = p.value.replace(old_name, new_name)
                print('2', p.name, p.value)


with open(os.path.join(os.path.expanduser('~'), 'style.css')) as f:
    content = f.read()
sheet = cssutils.parseString(content, validate=True)
rename_font_family('Alegreya', 'test', sheet)
for rule in sheet:
    if rule.type == rule.FONT_FACE_RULE:
        for p in rule.style:
            if p.name == 'font-family':
                fname = p.value
            if p.name == 'font-weight':
                fbold = p.value
            if p.name == 'font-style':
                fitalic = p.value
            if p.name == 'src':
                furl = p.value
        print(fname, fbold, fitalic, furl)
