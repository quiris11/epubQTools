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

import re
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
    """Value text with quoted strings and unquoted URLs left out (an unusual
    space inside a string, e.g. in a font name, or in a file name is
    valid)."""
    parts = []
    for t in tokens:
        if t.type == 'string':
            parts.append('""')
        elif t.type == 'url':
            parts.append('url()')
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
            if isinstance(d, QualifiedRule):
                # CSS nesting: a rule inside a rule
                check_declarations(d.content,
                                   tinycss2.serialize(d.prelude).strip(),
                                   KNOWN_PROPERTIES)
                continue
            if isinstance(d, AtRule):
                if (d.lower_at_keyword in ('media', 'supports') and
                        d.content is not None):
                    check_declarations(d.content, selector, known)
                continue
            if not isinstance(d, Declaration):
                continue
            name = d.lower_name
            value = tinycss2.serialize(d.value).strip(' \t\r\n\f')
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


URL_START_RE = re.compile(r'(?<![\w\\-])url\(\s*(?!["\'])', re.IGNORECASE)


def _unusual_spaces_in_value(text, start):
    """Positions of unusual spaces in the value of a declaration that
    starts at text[start], outside strings, comments, escapes and unquoted
    URLs. The value ends at ";" or at the end of the enclosing block."""
    found = []
    depth = 0
    in_value = False
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if text.startswith('/*', i):
            end = text.find('*/', i + 2)
            i = n if end == -1 else end + 2
            continue
        if ch in '"\'':
            i += 1
            while i < n and text[i] not in (ch, '\n', '\r', '\f'):
                i += 2 if text[i] == '\\' else 1
            i += 1
            continue
        if ch == '\\':
            i += 2
            continue
        url = URL_START_RE.match(text, i)
        if url:
            end = text.find(')', url.end())
            i = n if end == -1 else end + 1
            continue
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
            if depth < 0:
                break
        elif ch == ';' and depth == 0:
            break
        elif ch == ':' and depth == 0:
            in_value = True
        elif ch in UNUSUAL_SPACES and in_value:
            found.append(i)
        i += 1
    return found


# a property name, possibly with escapes
NAME_RE = re.compile(r'(?:[\w-]|\\(?:[0-9a-fA-F]{1,6}(?:\r\n|[ \t\r\n\f])?|'
                     r'[^\r\n\f0-9a-fA-F]))+')
ZERO_WIDTH_SPACE = '​'
# keywords allowed in values (colors, border styles, font weights etc.)
VALUE_KEYWORDS = {
    line.strip() for line in
    get_data('lib', 'resources/css_value_keywords.txt').decode('utf-8')
    .splitlines() if line.strip() and not line.startswith('#')
}
VALUE_WORD_RE = re.compile(
    r'#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})|'
    r'[+-]?(?:\d+\.?\d*|\.\d+)(?:%|[a-z]+)?', re.IGNORECASE)


def _is_separator(c):
    return c.isspace() or c in ':;,()!{}/' or c in UNUSUAL_SPACES


def _is_value_word(word):
    """A keyword, a hex color or a number (with a unit)."""
    return (word.lower() in VALUE_KEYWORDS or
            VALUE_WORD_RE.fullmatch(word) is not None)


def _normalized_name(name):
    return ' '.join(name.replace(ZERO_WIDTH_SPACE, '').split()).lower()


def font_face_families(css_text):
    """Font family names (normalized) of the @font-face rules."""
    families = set()
    for rule in tinycss2.parse_stylesheet(css_text, skip_whitespace=True,
                                          skip_comments=True):
        if (isinstance(rule, AtRule) and rule.content is not None and
                rule.lower_at_keyword == 'font-face'):
            for prop, value, important in _declarations(rule.content):
                if prop == 'font-family':
                    families.add(_normalized_name(value.strip('"\'')))
    return families


def _font_family_replacement(text, i, families):
    """For a zero width space in a font family name: ' ' if only the name
    with a space is one of families, '' if the name without it is, None if
    neither. The name is the end of the list item ("12px Linux Libertine"
    in the font shorthand)."""
    start = i
    while start > 0 and text[start - 1] not in ',:;{}()':
        start -= 1
    end = i + 1
    while end < len(text) and text[end] not in ',;{}()!':
        end += 1

    def known(name):
        name = _normalized_name(name)
        return any(name == f or name.endswith(' ' + f) for f in families)

    left, right = text[start:i], text[i + 1:end]
    if known(left + right):
        return ''
    if known(left + ' ' + right):
        return ' '
    return None


def _space_replacement(text, i, families=frozenset()):
    """A zero width space inside a word (e.g. "bo[U+200B]ld") or next to a
    space or a separator is removed, between two words (e.g. "1em" and
    "2em", "#fff" and "solid", "Linux" and "Libertine" with "Linux
    Libertine" in families) it is replaced with a space. Other unusual
    spaces are replaced with a space."""
    if text[i] != ZERO_WIDTH_SPACE:
        return ' '
    before = text[i - 1] if i > 0 else ' '
    after = text[i + 1] if i + 1 < len(text) else ' '
    if _is_separator(before) or _is_separator(after):
        return ''
    if before.isalpha() and after.isalpha():
        replacement = _font_family_replacement(text, i, families)
        if replacement is not None:
            return replacement
        start = i
        while start > 0 and not _is_separator(text[start - 1]):
            start -= 1
        end = i + 1
        while end < len(text) and not _is_separator(text[end]):
            end += 1
        left, right = text[start:i], text[i + 1:end]
        if (not _is_value_word(left + right) and _is_value_word(left) and
                _is_value_word(right)):
            return ' '
        return ''
    return ' '


def fix_unusual_spaces(css_text, font_families=frozenset()):
    """Replace unusual spaces (e.g. U+00A0) with normal spaces in the values
    of the declarations reported by check_css (the declarations dropped by
    readers), also in nested rules. Strings, comments, unquoted URLs and
    selectors are not touched, the rest of the text stays as it is.
    font_families: font_face_families of the other CSS files of the book
    (the ones of css_text are added). Returns the new text and the number
    of replaced characters."""
    # offsets of line starts as counted by tinycss2
    line_starts = [0] + [m.end() for m in
                         re.finditer(r'\r\n|[\r\n\f]', css_text)]
    positions = set()

    def name_at(start):
        """The property name (with escapes resolved) at text[start]."""
        m = NAME_RE.match(css_text, start)
        if not m:
            return None
        token = tinycss2.parse_one_component_value(m.group())
        return token.value if token.type == 'ident' else None

    def fix_declarations(content):
        for d in tinycss2.parse_blocks_contents(
                content, skip_whitespace=True, skip_comments=True):
            if isinstance(d, QualifiedRule):
                fix_declarations(d.content)
                continue
            if isinstance(d, AtRule):
                if (d.lower_at_keyword in ('media', 'supports') and
                        d.content is not None):
                    fix_declarations(d.content)
                continue
            if not isinstance(d, Declaration):
                continue
            unquoted = serialize_without_strings(d.value)
            if not any(ch in unquoted for ch in UNUSUAL_SPACES):
                continue
            start = line_starts[d.source_line - 1] + d.source_column - 1
            # make sure the position is right
            if name_at(start) != d.name:
                continue
            positions.update(_unusual_spaces_in_value(css_text, start))

    def fix_rules(rules):
        for rule in rules:
            if isinstance(rule, QualifiedRule):
                fix_declarations(rule.content)
            elif isinstance(rule, AtRule) and rule.content is not None:
                keyword = rule.lower_at_keyword
                if keyword in ('font-face', 'page'):
                    fix_declarations(rule.content)
                elif keyword in ('media', 'supports'):
                    fix_rules(tinycss2.parse_rule_list(
                        rule.content, skip_whitespace=True,
                        skip_comments=True))

    fix_rules(tinycss2.parse_stylesheet(css_text, skip_whitespace=True,
                                        skip_comments=True))
    if not positions:
        return css_text, 0
    families = set(font_families) | font_face_families(css_text)
    chars = list(css_text)
    for i in positions:
        chars[i] = _space_replacement(css_text, i, families)
    return ''.join(chars), len(positions)


def fix_missing_semicolons(css_text):
    """Insert the missing semicolon before a known property name followed
    by ':' inside a value ("border: 0 solid border-collapse: collapse" ->
    "border: 0 solid; border-collapse: collapse"), also in nested rules.
    Returns the new text and the number of inserted semicolons."""
    line_starts = [0] + [m.end() for m in
                         re.finditer(r'\r\n|[\r\n\f]', css_text)]
    positions = set()

    def fix_declarations(content):
        for d in tinycss2.parse_blocks_contents(
                content, skip_whitespace=True, skip_comments=True):
            if isinstance(d, QualifiedRule):
                fix_declarations(d.content)
                continue
            if isinstance(d, AtRule):
                if (d.lower_at_keyword in ('media', 'supports') and
                        d.content is not None):
                    fix_declarations(d.content)
                continue
            if not isinstance(d, Declaration):
                continue
            tokens = [t for t in d.value
                      if t.type not in ('whitespace', 'comment')]
            # the name follows at least one value token
            for name, colon in zip(tokens[1:], tokens[2:]):
                if not (name.type == 'ident' and
                        name.lower_value in KNOWN_PROPERTIES and
                        isinstance(colon, LiteralToken) and
                        colon.value == ':'):
                    continue
                start = (line_starts[name.source_line - 1] +
                         name.source_column - 1)
                # make sure the position is right
                if not css_text.startswith(name.value, start):
                    continue
                # the semicolon goes just after the previous value
                while start > 0 and css_text[start - 1] in ' \t\r\n\f':
                    start -= 1
                positions.add(start)

    for rule in tinycss2.parse_stylesheet(css_text, skip_whitespace=True,
                                          skip_comments=True):
        if isinstance(rule, QualifiedRule):
            fix_declarations(rule.content)
        elif (isinstance(rule, AtRule) and rule.content is not None and
              rule.lower_at_keyword in ('media', 'supports')):
            fix_declarations(rule.content)
    if not positions:
        return css_text, 0
    for i in sorted(positions, reverse=True):
        css_text = css_text[:i] + ';' + css_text[i:]
    return css_text, len(positions)


def remove_page_descriptors(css_text):
    """Remove the @page descriptors (e.g. "size: 2px") used outside @page,
    where they are not properties and readers ignore them, also in nested
    rules. Returns the new text and the number of removed declarations."""
    line_starts = [0] + [m.end() for m in
                         re.finditer(r'\r\n|[\r\n\f]', css_text)]
    edits = []

    def declaration_end(i):
        """Offset just after the ";" ending the declaration that starts at
        text[i] (or of the "}" closing its block)."""
        n = len(css_text)
        depth = 0
        while i < n:
            skip = _skip_special(css_text, i)
            if skip is not None:
                i = skip
                continue
            ch = css_text[i]
            if ch in '([':
                depth += 1
            elif ch in ')]':
                depth -= 1
            elif ch == ';' and depth <= 0:
                return i + 1
            elif ch == '}' and depth <= 0:
                return i
            i += 1
        return n

    def remove_declarations(content):
        for d in tinycss2.parse_blocks_contents(
                content, skip_whitespace=True, skip_comments=True):
            if isinstance(d, QualifiedRule):
                remove_declarations(d.content)
                continue
            if isinstance(d, AtRule):
                if (d.lower_at_keyword in ('media', 'supports') and
                        d.content is not None):
                    remove_declarations(d.content)
                continue
            if (not isinstance(d, Declaration) or
                    d.lower_name not in PAGE_DESCRIPTORS):
                continue
            start = line_starts[d.source_line - 1] + d.source_column - 1
            # make sure the position is right
            if not css_text.startswith(d.name, start):
                continue
            end = declaration_end(start)
            line_start = start
            while line_start > 0 and css_text[line_start - 1] in ' \t':
                line_start -= 1
            spaces_end = end
            while (spaces_end < len(css_text) and
                   css_text[spaces_end] in ' \t'):
                spaces_end += 1
            after = SPACES_AND_LINE_BREAK_RE.match(css_text, end).end()
            if (after > spaces_end and
                    css_text[line_start - 1:line_start] in ('', '\n', '\r',
                                                            '\f')):
                # a declaration in its own line: the whole line goes
                edits.append((line_start, after))
            else:
                edits.append((start, spaces_end))

    for rule in tinycss2.parse_stylesheet(css_text, skip_whitespace=True,
                                          skip_comments=True):
        if isinstance(rule, QualifiedRule):
            remove_declarations(rule.content)
        elif (isinstance(rule, AtRule) and rule.content is not None and
              rule.lower_at_keyword in ('media', 'supports')):
            remove_declarations(rule.content)
    for start, end in sorted(edits, reverse=True):
        css_text = css_text[:start] + css_text[end:]
    return css_text, len(edits)


def _skip_special(text, i):
    """If text[i] starts a comment, a string, an escape or an unquoted URL,
    the index just after it, else None."""
    n = len(text)
    ch = text[i]
    if text.startswith('/*', i):
        end = text.find('*/', i + 2)
        return n if end == -1 else end + 2
    if ch in '"\'':
        i += 1
        while i < n and text[i] not in (ch, '\n', '\r', '\f'):
            i += 2 if text[i] == '\\' else 1
        return i + 1
    if ch == '\\':
        return i + 2
    url = URL_START_RE.match(text, i)
    if url:
        end = text.find(')', url.end())
        return n if end == -1 else end + 1
    return None


SPACES_AND_LINE_BREAK_RE = re.compile(r'[ \t]*(?:\r\n|[\r\n\f])?')


def _block_bounds(text, start):
    """Offsets of "{" and of the matching "}" (or the end of the text) of
    the rule that starts at text[start]."""
    n = len(text)
    i = start
    depth = 0
    opening = None
    while i < n:
        skip = _skip_special(text, i)
        if skip is not None:
            i = skip
            continue
        if text[i] == '{':
            if opening is None:
                opening = i
            depth += 1
        elif text[i] == '}' and opening is not None:
            depth -= 1
            if depth == 0:
                return opening, i
        i += 1
    return opening, n - 1


def _split_selectors(prelude):
    """The selectors (lists of tokens) of a selector list."""
    selectors = [[]]
    for t in prelude:
        if isinstance(t, LiteralToken) and t.value == ',':
            selectors.append([])
        else:
            selectors[-1].append(t)
    return selectors


def _selector_classes(tokens):
    """Class names used in a selector."""
    return {b.value for a, b in zip(tokens, tokens[1:])
            if isinstance(a, LiteralToken) and a.value == '.' and
            b.type == 'ident'}


# properties that can hide the text of an element
HIDING_PROPERTIES = {'font-size', 'font', 'display', 'visibility', 'all'}


def _declarations(content):
    """(lowercase property name, value, important) of a block."""
    return [(d.lower_name, tinycss2.serialize(d.value).strip(), d.important)
            for d in tinycss2.parse_blocks_contents(
                content, skip_whitespace=True, skip_comments=True)
            if isinstance(d, Declaration)]


def _compound_selector(tokens):
    """(type or None, classes) of a selector with only a type and classes
    (".a", "div.a", ".a.b"), otherwise None."""
    while tokens and tokens[0].type == 'whitespace':
        tokens = tokens[1:]
    while tokens and tokens[-1].type == 'whitespace':
        tokens = tokens[:-1]
    tag = None
    if tokens and tokens[0].type == 'ident':
        tag, tokens = tokens[0].lower_value, tokens[1:]
    elif tokens and isinstance(tokens[0], LiteralToken) and \
            tokens[0].value == '*':
        tokens = tokens[1:]
    classes = set()
    while len(tokens) >= 2 and isinstance(tokens[0], LiteralToken) and \
            tokens[0].value == '.' and tokens[1].type == 'ident':
        classes.add(tokens[1].value)
        tokens = tokens[2:]
    if tokens or not classes:
        return None
    return tag, frozenset(classes)


def class_rules(css_text):
    """Rules for elements with classes, to compute their style. Returns
    (rules, uncertain):
    - rules: (type or None, classes, declarations) of the top-level rules
      for each selector with only a type and classes (".a", "div.a", ".a.b")
      in the order of the text; declarations as in _declarations,
    - uncertain: classes used in the other rules (other selectors, in
      at-rules, nested) that set a property in HIDING_PROPERTIES - the style
      of an element with such a class can't be computed."""
    rules = []
    uncertain = set()

    def mark_uncertain(rule, selector_classes):
        """Rules in an at-rule or nested in a rule."""
        if isinstance(rule, QualifiedRule):
            classes = set(selector_classes)
            for s in _split_selectors(rule.prelude):
                classes |= _selector_classes(s)
            content = tinycss2.parse_blocks_contents(
                rule.content, skip_whitespace=True, skip_comments=True)
        elif isinstance(rule, AtRule) and rule.content is not None:
            classes = selector_classes
            content = tinycss2.parse_blocks_contents(
                rule.content, skip_whitespace=True, skip_comments=True)
        else:
            return
        if any(isinstance(d, Declaration) and
               d.lower_name in HIDING_PROPERTIES for d in content):
            uncertain.update(classes)
        for r in content:
            if not isinstance(r, Declaration):
                mark_uncertain(r, classes)

    for rule in tinycss2.parse_stylesheet(css_text, skip_whitespace=True,
                                          skip_comments=True):
        if isinstance(rule, AtRule):
            if rule.content is not None:
                for r in tinycss2.parse_rule_list(
                        rule.content, skip_whitespace=True,
                        skip_comments=True):
                    mark_uncertain(r, set())
            continue
        if not isinstance(rule, QualifiedRule):
            continue
        declarations = _declarations(rule.content)
        hiding = any(d[0] in HIDING_PROPERTIES for d in declarations)
        selector_classes = set()
        for s in _split_selectors(rule.prelude):
            selector_classes |= _selector_classes(s)
            compound = _compound_selector(s)
            if compound:
                rules.append(compound + (declarations,))
            elif hiding:
                uncertain.update(_selector_classes(s))
        for r in tinycss2.parse_blocks_contents(
                rule.content, skip_whitespace=True, skip_comments=True):
            if not isinstance(r, Declaration):
                mark_uncertain(r, selector_classes)
    return rules, uncertain


def remove_class_rules(css_text, names):
    """Remove the rules whose every selector uses one of the class names
    (e.g. ".NAME", "div.NAME", ".a .NAME", ".NAME, .NAME2 p") and remove
    such selectors from the other rules ("p, .NAME" -> "p"). @media and
    @supports rules left empty are removed too. The rest of the text stays
    as it is. Returns the new text and the removed class names (sorted)."""
    line_starts = [0] + [m.end() for m in
                         re.finditer(r'\r\n|[\r\n\f]', css_text)]
    edits = []
    removed = set()

    def offset(node):
        return line_starts[node.source_line - 1] + node.source_column - 1

    def delete(start, end):
        """Delete text[start:end] with spaces before it and spaces and one
        line break after it."""
        while start > 0 and css_text[start - 1] in ' \t':
            start -= 1
        end = SPACES_AND_LINE_BREAK_RE.match(css_text, end).end()
        edits.append((start, end, ''))

    def process(rules, nested=False):
        """Edit the rules (nested: in a rule); returns True if all of them
        are removed."""
        all_removed = True
        for rule in rules:
            if isinstance(rule, ParseError):
                all_removed = False
            elif isinstance(rule, QualifiedRule):
                selectors = _split_selectors(rule.prelude)
                kept = [s for s in selectors
                        if not _selector_classes(s) & names]
                start = offset(rule)
                if len(kept) == len(selectors):
                    all_removed = False
                    process_nested(rule)
                    continue
                for s in selectors:
                    removed.update(_selector_classes(s) & names)
                opening, closing = _block_bounds(css_text, start)
                if opening is None:
                    all_removed = False
                elif not kept:
                    delete(start, closing + 1)
                else:
                    all_removed = False
                    edits.append((start, opening, ', '.join(
                        tinycss2.serialize(s).strip() for s in kept) + ' '))
                    process_nested(rule)
            elif (isinstance(rule, AtRule) and rule.content is not None and
                    rule.lower_at_keyword in ('media', 'supports')):
                before = len(edits)
                if nested:
                    # declarations and rules
                    inner = tinycss2.parse_blocks_contents(
                        rule.content, skip_whitespace=True,
                        skip_comments=True)
                else:
                    inner = tinycss2.parse_rule_list(
                        rule.content, skip_whitespace=True,
                        skip_comments=True)
                if process(inner, nested) and inner:
                    # replace the edits of the nested rules
                    del edits[before:]
                    start = offset(rule)
                    delete(start, _block_bounds(css_text, start)[1] + 1)
                else:
                    all_removed = False
            else:
                all_removed = False
        return all_removed

    def process_nested(rule):
        """Rules nested in a rule (CSS nesting)."""
        process([r for r in tinycss2.parse_blocks_contents(
            rule.content, skip_whitespace=True, skip_comments=True)
            if not isinstance(r, Declaration)], True)

    process(tinycss2.parse_stylesheet(css_text, skip_whitespace=True,
                                      skip_comments=True))
    if not edits:
        return css_text, []
    for start, end, new in sorted(edits, reverse=True):
        css_text = css_text[:start] + new + css_text[end:]
    return css_text, sorted(removed)
