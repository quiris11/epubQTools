# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Settings of the calibre plugin and their translation to the options of
qfix. Plain Python (no calibre imports), so it can be tested without
calibre."""

from urllib.parse import urlsplit

# alignment of the text in CSS files
ALIGN_JUSTIFY = 'justify'           # "text-align: left" -> justify (as -e)
ALIGN_LEFT = 'left'                 # "text-align: justify" -> left (--left)
ALIGN_KEEP = 'keep'                 # no change (--skip-justify)

# the defaults give the same result as -c -r -e in the terminal
DEFAULTS = {
    'hyphenate': True,              # -s turns it off
    'hyphenate_headers': False,     # off as -r; on without -r
    'reset_css': False,             # off as -c; on without -c
    'align': ALIGN_JUSTIFY,
    'remove_colors': False,         # --remove-colors (only with alignment)
    'remove_fonts': False,          # --remove-fonts
    'book_margin': None,            # --book-margin, pixels or None (only
                                    # with reset_css)
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


# Amazon sites with the Send to Kindle page (www.<site>/sendtokindle,
# checked 2026-11-28; amazon.se and amazon.pl have none)
KINDLE_SITES = ('amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr',
                'amazon.it', 'amazon.es', 'amazon.nl', 'amazon.ca',
                'amazon.com.au', 'amazon.co.jp', 'amazon.in',
                'amazon.com.br', 'amazon.com.mx')


def kindle_site(value):
    """A site from KINDLE_SITES (amazon.com for unknown values)."""
    return value if value in KINDLE_SITES else KINDLE_SITES[0]


def send_to_kindle_url(site):
    return 'https://www.%s/sendtokindle' % kindle_site(site)


def is_amazon_url(url):
    """True for a secure (https) address on one of KINDLE_SITES or on its
    subdomain, e.g. https://www.amazon.de/ap/signin; not for
    amazon.com.example.org or https://amazon.com@example.org."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or '').lower().rstrip('.')
    except ValueError:
        return False
    return parts.scheme == 'https' and any(
        host == site or host.endswith('.' + site) for site in KINDLE_SITES)
