#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Hyphenation dictionaries for the language of a book.

The Polish dictionary is part of epubQTools (lib/resources). Dictionaries
of the other languages are read from an installed calibre
(resources/hyphenation/dictionaries.tar.xz and locales.json): in the
calibre plugin from the running calibre, in a terminal from calibre
installed in one of the usual places. Without calibre only Polish books
are hyphenated."""

import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import unicodedata

from .hyphenator import Hyphenator
from .resource_data import read_resource

POLISH = 'pl'
POLISH_DIC = 'hyph_pl_PL.dic'

# three-letter language codes (ISO 639-2, bibliographic and terminology
# ones) of the languages with a calibre dictionary
ISO639_2 = {
    'afr': 'af', 'alb': 'sq', 'asm': 'as', 'bel': 'be', 'bul': 'bg',
    'ces': 'cs', 'cze': 'cs', 'dan': 'da', 'deu': 'de', 'dut': 'nl',
    'ell': 'el', 'eng': 'en', 'epo': 'eo', 'est': 'et', 'ger': 'de',
    'glg': 'gl', 'gre': 'el', 'hrv': 'hr', 'hun': 'hu', 'ice': 'is',
    'ind': 'id', 'isl': 'is', 'ita': 'it', 'kan': 'kn', 'lav': 'lv',
    'lit': 'lt', 'mar': 'mr', 'mon': 'mn', 'nld': 'nl', 'nno': 'nn',
    'nob': 'nb', 'ori': 'or', 'pan': 'pa', 'pol': 'pl', 'por': 'pt',
    'ron': 'ro', 'rum': 'ro', 'rus': 'ru', 'san': 'sa', 'slk': 'sk',
    'slo': 'sk', 'slv': 'sl', 'spa': 'es', 'sqi': 'sq', 'srp': 'sr',
    'swe': 'sv', 'tel': 'te', 'ukr': 'uk', 'zul': 'zu',
}
# the dictionary for a language code without a country, when locales.json
# has no entry for the language alone and not "xx_XX" (as in calibre)
DEFAULT_LOCALES = {'en': 'en_US'}
# codes meaning "no language"
NO_LANGUAGE = ('', 'und', 'zxx', 'mul')

# Polish letters rarely used together in other languages: their share
# among all letters is 5-9% in a Polish text and about 1% at most in
# the other languages that have some of them
POLISH_LETTERS = set('ąęłśżźćńĄĘŁŚŻŹĆŃ')
POLISH_LETTERS_SHARE = 0.02
POLISH_MIN_LETTERS = 500

# combining marks (e.g. Indic vowel signs) are parts of words although
# "\w" does not match them
_MARKS = ''.join(
    chr(c) for c in range(0x300, 0x10000)
    if unicodedata.category(chr(c)) in ('Mn', 'Mc', 'Me'))
WORD_RE = re.compile(r'[\w%s]+|[^\w%s]' % (re.escape(_MARKS),
                                           re.escape(_MARKS)))


def language_parts(code):
    """Split a language code into (language, script, region), e.g.
    "sr-Latn-RS" -> ("sr", "Latn", "RS"), "pol" -> ("pl", None, None)."""
    parts = [p for p in re.split(r'[-_]', (code or '').strip()) if p]
    if not parts:
        return '', None, None
    lang = parts[0].lower()
    lang = ISO639_2.get(lang, lang)
    script = region = None
    for p in parts[1:]:
        if len(p) == 4 and p.isalpha() and script is None and \
                region is None:
            script = p.title()
        elif (len(p) == 2 and p.isalpha()) or \
                (len(p) == 3 and p.isdigit()):
            region = p.upper()
            break
        else:
            break
    return lang, script, region


def primary_language(code):
    """The language of a code, lowercased, as a two-letter code when
    known: "pl-PL", "PL" and "pol" -> "pl"."""
    return language_parts(code)[0]


def is_no_language(code):
    return primary_language(code) in NO_LANGUAGE


def is_polish(code):
    return primary_language(code) == POLISH


def dictionary_name(locales, code):
    """The name of the dictionary in calibre's locales.json (a map like
    {"pl_PL": "hyph_pl_PL.dic"}) for a language code, or None."""
    lang, script, region = language_parts(code)
    if lang in NO_LANGUAGE:
        return None
    tries = []
    if script and region:
        tries.append('%s_%s_%s' % (lang, script, region))
    if region:
        tries.append('%s_%s' % (lang, region))
    if script:
        tries += sorted(k for k in locales
                        if k.startswith('%s_%s_' % (lang, script)))
    tries += [lang, DEFAULT_LOCALES.get(lang, ''),
              '%s_%s' % (lang, lang.upper())]
    same_lang = sorted(k for k in locales if k.startswith(lang + '_'))
    # locales without a script first ("sr_RS" before "sr_Latn_RS")
    tries += [k for k in same_lang if len(k.split('_')[1]) != 4]
    tries += same_lang
    for t in tries:
        if t in locales:
            return locales[t]
    return None


def calibre_dirs():
    """Folders where calibre may keep its hyphenation dictionaries."""
    dirs = []
    try:
        # the calibre plugin (or calibre-debug): the running calibre
        from calibre.utils.resources import get_path
        dirs.append(os.path.dirname(get_path('hyphenation/locales.json')))
    except Exception:
        pass
    exe = shutil.which('calibre')
    if exe:
        bindir = os.path.dirname(os.path.realpath(exe))
        dirs += [os.path.join(bindir, 'resources'),            # Linux
                 os.path.join(bindir, os.pardir, 'Resources',  # macOS
                              'resources'),
                 os.path.join(bindir, 'app', 'resources'),     # Windows
                 os.path.join(bindir, os.pardir, 'share', 'calibre')]
    dirs += [os.path.join(d, 'calibre.app', 'Contents', 'Resources',
                          'resources')
             for d in ('/Applications', os.path.expanduser('~/Applications'))]
    dirs += ['/opt/calibre/resources', '/usr/share/calibre',
             '/usr/local/share/calibre']
    for var in ('ProgramFiles', 'ProgramFiles(x86)', 'ProgramW6432'):
        if os.environ.get(var):
            dirs.append(os.path.join(os.environ[var], 'Calibre2', 'app',
                                     'resources'))
    return [os.path.join(d, 'hyphenation') for d in dirs]


def find_calibre_hyphenation():
    """The folder with calibre's dictionaries.tar.xz and locales.json, or
    None when calibre is not found."""
    for d in calibre_dirs():
        if os.path.isfile(os.path.join(d, 'dictionaries.tar.xz')) and \
                os.path.isfile(os.path.join(d, 'locales.json')):
            return os.path.normpath(d)
    return None


def hyphenator_from_bytes(data):
    """A Hyphenator for the bytes of a hyph_*.dic file, with the shortest
    first and last parts given in the file (LEFTHYPHENMIN etc.)."""
    def header(name, default):
        m = re.search(rb'^%s[ \t]+(\d+)' % name, data, re.M)
        return int(m.group(1)) if m else default

    tmp_dir = tempfile.mkdtemp(prefix='epubQTools-tmp-')
    try:
        dic = os.path.join(tmp_dir, 'hyph.dic')
        with open(dic, 'wb') as f:
            f.write(data)
        return Hyphenator(dic, header(b'LEFTHYPHENMIN', 2),
                          header(b'RIGHTHYPHENMIN', 2))
    finally:
        shutil.rmtree(tmp_dir)


_polish = []
_cache = {}


def polish_hyphenator():
    if not _polish:
        _polish.append(hyphenator_from_bytes(
            read_resource('dictionaries/' + POLISH_DIC)))
    return _polish[0]


def calibre_hyphenator(code, hyph_dir=None):
    """(Hyphenator, dictionary name) for a language code from calibre's
    dictionaries; (None, reason) when there is no such dictionary."""
    hyph_dir = hyph_dir or find_calibre_hyphenation()
    if hyph_dir is None:
        return None, 'calibre not found'
    key = (hyph_dir, code)
    if key not in _cache:
        with open(os.path.join(hyph_dir, 'locales.json'), 'rb') as f:
            name = dictionary_name(json.loads(f.read()), code)
        if name is None:
            _cache[key] = None, 'no dictionary in calibre'
        else:
            try:
                with tarfile.open(os.path.join(
                        hyph_dir, 'dictionaries.tar.xz'), 'r:xz') as tf:
                    data = tf.extractfile(tf.getmember(name)).read()
                _cache[key] = hyphenator_from_bytes(data), name
            except Exception as e:
                _cache[key] = None, 'cannot read %s (%s)' % (name, e)
    return _cache[key]


def hyphenator_for(code):
    """(Hyphenator, dictionary name) for the language of a book; (None,
    reason) when the language cannot be hyphenated."""
    if is_polish(code):
        return polish_hyphenator(), POLISH_DIC
    if is_no_language(code):
        return None, 'no language'
    return calibre_hyphenator(code)


def looks_polish(texts):
    """True when the texts have enough letters typical of Polish."""
    letters = polish = 0
    for t in texts:
        for c in t:
            if c.isalpha():
                letters += 1
                if c in POLISH_LETTERS:
                    polish += 1
    return letters >= POLISH_MIN_LETTERS and \
        polish >= POLISH_LETTERS_SHARE * letters


if __name__ == '__main__':
    # python3 -m lib.hyphenation CODE WORD...: hyphenate words for a test
    h, name = hyphenator_for(sys.argv[1])
    print(name)
    if h:
        print(' '.join(h.inserted(w, '-') for w in sys.argv[2:]))
