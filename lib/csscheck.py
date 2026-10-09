#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
"""
CSS check for the internal check tool (-q), based on tinycss2 (CSS Syntax
Level 3). It reports problems that matter in e-book readers instead of
validating against CSS 2.1:

ERROR! - the declaration (or the rule) is dropped by a reader:
    syntax errors, unknown property names (typos), non-breaking or other
    unusual spaces in a value, a missing semicolon (':' inside a value),
    more than 4 values in margin/padding
WARNING! - may cause problems in some readers:
    !important on font-size/font-family/line-height/color/background-color
    (overrides reader settings), position: fixed/absolute, display: flex/grid,
    vh/vw/vmin/vmax units, color or background on body/html (night mode),
    @import
"""

import sys
from pkgutil import get_data

try:
    import tinycss2
    from tinycss2.ast import (AtRule, Declaration, DimensionToken,
                              LiteralToken, ParseError, QualifiedRule)
except ImportError as e:
    sys.exit('! CRITICAL! ' + str(e) + ' (install with: '
             'python -m pip install tinycss2)')

# property names known to browsers (MDN) and used in e-books
KNOWN_PROPERTIES = {
    line.strip() for line in
    get_data('lib', 'resources/css_properties.txt').decode('utf-8')
    .splitlines() if line.strip() and not line.startswith('#')
} | {'adobe-hyphenate', 'adobe-text-layout', 'oeb-column-number'}
# descriptors allowed only inside @font-face and @page
FONT_FACE_DESCRIPTORS = {
    'src', 'font-family', 'font-style', 'font-weight', 'font-stretch',
    'unicode-range', 'font-display', 'font-feature-settings',
    'font-variation-settings', 'font-variant', 'ascent-override',
    'descent-override', 'line-gap-override', 'size-adjust'
}
PAGE_DESCRIPTORS = {'size', 'marks', 'bleed', 'page-orientation'}

UNUSUAL_SPACES = {
    ' ': 'non-breaking space', ' ': 'figure space',
    ' ': 'thin space', ' ': 'narrow non-breaking space',
    '​': 'zero width space', '　': 'ideographic space'
}
# values that do not set any color
NO_COLOR_VALUES = {'none', 'transparent', 'inherit', 'initial', 'unset',
                   'revert', 'currentcolor'}
IMPORTANT_PROPERTIES = {'font-size', 'font-family', 'line-height', 'color',
                        'background-color'}


def serialize_without_strings(tokens):
    """Value text with quoted strings left out (an unusual space inside
    a string, e.g. in a font name, is valid)."""
    parts = []
    for t in tokens:
        if t.type == 'string':
            parts.append('""')
        elif t.type == 'function':
            parts.append(t.name + '(' +
                         serialize_without_strings(t.arguments) + ')')
        else:
            parts.append(tinycss2.serialize([t]))
    return ''.join(parts)


def check_css(css_text, css_name, file_dec, skip_warnings=False):
    """Print problems found in one CSS file; returns their number. With
    skip_warnings only errors are reported."""
    found = []

    def report(level, line, message):
        if skip_warnings and level == 'WARNING':
            return
        found.append(1)
        print('%sCSS %s! Problem in "%s" (line %s): %s'
              % (file_dec, level, css_name, line, ' '.join(message.split())))

    def check_declarations(content, selector, known):
        for d in tinycss2.parse_blocks_contents(
                content, skip_whitespace=True, skip_comments=True):
            if isinstance(d, ParseError):
                if 'Stop token reached before {} block' in d.message:
                    # tinycss2 (CSS nesting) reads "font-weight bold;" as
                    # an unfinished nested rule
                    report('ERROR', d.source_line, 'invalid declaration '
                           '(missing ":"?) in: ' + selector)
                else:
                    report('ERROR', d.source_line,
                           'syntax error: ' + d.message)
                continue
            if not isinstance(d, Declaration):
                continue
            name = d.lower_name
            value = tinycss2.serialize(d.value).strip()
            tokens = [t for t in d.value
                      if t.type not in ('whitespace', 'comment')]
            text = '%s { %s: %s%s }' % (selector, d.name, value,
                                        ' !important' if d.important else '')
            if not name.startswith('-') and name not in known:
                report('ERROR', d.source_line,
                       'unknown property "%s" (typo?): %s' % (d.name, text))
            unquoted = serialize_without_strings(d.value)
            for ch, desc in UNUSUAL_SPACES.items():
                if ch in unquoted:
                    report('ERROR', d.source_line,
                           '%s (U+%04X) in a value - the declaration is '
                           'dropped: %s' % (desc, ord(ch), text.replace(
                               ch, '[U+%04X]' % ord(ch))))
            if any(isinstance(t, LiteralToken) and t.value == ':'
                   for t in tokens):
                report('ERROR', d.source_line,
                       'missing semicolon (":" inside a value): ' + text)
            if name in ('margin', 'padding') and len(tokens) > 4:
                report('ERROR', d.source_line,
                       'more than 4 values: ' + text)
            if d.important and name in IMPORTANT_PROPERTIES:
                report('WARNING', d.source_line,
                       '!important overrides reader settings: ' + text)
            if name == 'position' and value.lower() in ('fixed', 'absolute'):
                report('WARNING', d.source_line,
                       'position is not supported by many readers: ' + text)
            if name == 'display' and value.lower() in (
                    'flex', 'inline-flex', 'grid', 'inline-grid'):
                report('WARNING', d.source_line,
                       'flex/grid layout is not supported by older '
                       'readers: ' + text)
            if any(isinstance(t, DimensionToken) and
                   t.lower_unit in ('vh', 'vw', 'vmin', 'vmax')
                   for t in tokens):
                report('WARNING', d.source_line,
                       'viewport units are not supported by older '
                       'readers: ' + text)
            if (name in ('color', 'background-color', 'background') and
                    value.lower() not in NO_COLOR_VALUES and
                    {s.strip().lower() for s in selector.split(',')} &
                    {'body', 'html'}):
                report('WARNING', d.source_line,
                       'color on body/html may break night mode: ' + text)

    for rule in tinycss2.parse_stylesheet(css_text, skip_whitespace=True,
                                          skip_comments=True):
        if isinstance(rule, ParseError):
            report('ERROR', rule.source_line, 'syntax error: ' + rule.message)
        elif isinstance(rule, QualifiedRule):
            if any(isinstance(t, ParseError) for t in rule.prelude):
                report('ERROR', rule.source_line,
                       'unexpected "}" before the rule - the rule is dropped: '
                       + tinycss2.serialize(rule.prelude).strip())
            check_declarations(rule.content,
                               tinycss2.serialize(rule.prelude).strip(),
                               KNOWN_PROPERTIES)
        elif isinstance(rule, AtRule):
            keyword = rule.lower_at_keyword
            if keyword == 'import':
                report('WARNING', rule.source_line,
                       '@import is ignored by some readers: @import %s'
                       % tinycss2.serialize(rule.prelude).strip())
            elif keyword == 'font-face' and rule.content is not None:
                check_declarations(rule.content, '@font-face',
                                   FONT_FACE_DESCRIPTORS)
            elif keyword == 'page' and rule.content is not None:
                check_declarations(rule.content, '@page',
                                   KNOWN_PROPERTIES | PAGE_DESCRIPTORS)
            elif keyword in ('media', 'supports') and rule.content:
                # rules nested in @media/@supports
                for nested in tinycss2.parse_rule_list(
                        rule.content, skip_whitespace=True,
                        skip_comments=True):
                    if isinstance(nested, ParseError):
                        report('ERROR', nested.source_line,
                               'syntax error: ' + nested.message)
                    elif isinstance(nested, QualifiedRule):
                        check_declarations(
                            nested.content,
                            tinycss2.serialize(nested.prelude).strip(),
                            KNOWN_PROPERTIES)
    return len(found)
