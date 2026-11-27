# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Settings of the calibre plugin and their translation to the options of
qfix. Plain Python (no calibre imports), so it can be tested without
calibre."""

# alignment of the text in CSS files
ALIGN_JUSTIFY = 'justify'           # "text-align: left" -> justify (as -e)
ALIGN_LEFT = 'left'                 # "text-align: justify" -> left (--left)
ALIGN_KEEP = 'keep'                 # no change (--skip-justify)

# the defaults give the same result as -e in the terminal
DEFAULTS = {
    'hyphenate': True,              # -s turns it off
    'hyphenate_headers': True,      # -r turns it off
    'reset_css': True,              # -c turns it off
    'align': ALIGN_JUSTIFY,
    'remove_colors': False,         # --remove-colors (only with alignment)
    'remove_fonts': False,          # --remove-fonts
    'book_margin': None,            # --book-margin, pixels or None
    'page_list': True,              # --skip-page-list turns it off
}


def with_defaults(settings):
    """Settings completed with the defaults (keys of older versions or
    unknown values are ignored)."""
    result = dict(DEFAULTS)
    for key, value in (settings or {}).items():
        if key in DEFAULTS:
            result[key] = value
    if result['align'] not in (ALIGN_JUSTIFY, ALIGN_LEFT, ALIGN_KEEP):
        result['align'] = DEFAULTS['align']
    margin = result['book_margin']
    if margin is not None:
        try:
            margin = int(margin)
        except (TypeError, ValueError):
            margin = None
        if margin is not None and margin < 0:
            margin = None
    result['book_margin'] = margin
    return result


def qfix_options(settings):
    """Keyword arguments of epubqfix.qfix for the given plugin settings."""
    s = with_defaults(settings)
    return {
        '_forced': True,            # the book is fixed in a new temp dir
        '_resetmargins': s['reset_css'],
        'zbf': None,                # not used by qfix
        'skip_hyph': not s['hyphenate'],
        'arg_justify': s['align'] == ALIGN_JUSTIFY,
        'arg_left': s['align'] == ALIGN_LEFT,
        'del_colors': s['remove_colors'],
        'del_fonts': s['remove_fonts'],
        'fix_container_only': False,
        'html_margin': (None if s['book_margin'] is None
                        else str(s['book_margin'])),
        'dont_hyph_headers': not s['hyphenate_headers'],
        'skip_pages': not s['page_list'],
    }
