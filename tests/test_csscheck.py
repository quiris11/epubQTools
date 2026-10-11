# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#
import contextlib
import io
import unittest

from lib.csscheck import (check_css, class_rules, fix_unusual_spaces,
                          remove_class_rules)

NBSP = ' '
ZWSP = '​'


def check(css):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        check_css(css, 'test.css', '* ')
    return out.getvalue()


class FixUnusualSpacesTest(unittest.TestCase):

    def fix(self, css):
        return fix_unusual_spaces(css)[0]

    def test_value(self):
        self.assertEqual(self.fix('p { margin: 0' + NBSP + '1em; }'),
                         'p { margin: 0 1em; }')

    def test_strings_urls_comments_and_selectors_untouched(self):
        css = ('p' + NBSP + 'a { font-family: "A' + NBSP + 'B"; '
               'background: url(a' + NBSP + 'b.png); '
               'color: red /*' + NBSP + '*/; }')
        self.assertEqual(fix_unusual_spaces(css), (css, 0))

    def test_zero_width_space(self):
        self.assertEqual(
            self.fix('p { font-weight: bo' + ZWSP + 'ld; '
                     'margin: 1em' + ZWSP + '2em; padding:' + ZWSP + ' 0 }'),
            'p { font-weight: bold; margin: 1em 2em; padding: 0 }')

    def test_zero_width_space_between_letters(self):
        for value, fixed in (('#fff' + ZWSP + 'solid', '#fff solid'),
                             ('red' + ZWSP + 'solid', 'red solid'),
                             ('#fff' + ZWSP + 'fff', '#ffffff'),
                             ('10p' + ZWSP + 'x', '10px'),
                             ('sol' + ZWSP + 'id red', 'solid red'),
                             ('fo' + ZWSP + 'o', 'foo')):
            with self.subTest(value):
                self.assertEqual(self.fix('p { border: 1px %s }' % value),
                                 'p { border: 1px %s }' % fixed)

    def test_escaped_property_name(self):
        self.assertEqual(self.fix('p { col\\6f r: red' + NBSP + '; }'),
                         'p { col\\6f r: red ; }')

    def test_nested_rules(self):
        self.assertEqual(
            self.fix('.a { .b { margin: 0' + NBSP + '1em } '
                     '@media print { margin: 0' + NBSP + '1em } }'),
            '.a { .b { margin: 0 1em } @media print { margin: 0 1em } }')

    def test_media_and_line_endings(self):
        self.assertEqual(
            self.fix('@media print {\r\n  p { margin: 0' + NBSP + '1em }\r\n}'),
            '@media print {\r\n  p { margin: 0 1em }\r\n}')

    def test_fixed_css_has_no_errors(self):
        css = ('.a { margin: 1em' + NBSP + '2em; .b { padding:' + NBSP +
               '0 } }')
        self.assertIn('ERROR', check(css))
        self.assertEqual(check(self.fix(css)), '')


class CheckCssTest(unittest.TestCase):

    def test_nested_rule(self):
        self.assertIn('.b { margin: 1em[U+00A0]2em }',
                      check('.a { .b { margin: 1em' + NBSP + '2em } }'))

    def test_leading_unusual_space_shown(self):
        self.assertIn('margin: [U+00A0]1em',
                      check('p { margin:' + NBSP + '1em }'))

    def test_unknown_property(self):
        self.assertIn('unknown property "colr"', check('p { colr: red }'))


class RemoveClassRulesTest(unittest.TestCase):
    NAMES = {'QUJD'}

    def remove(self, css):
        return remove_class_rules(css, self.NAMES)

    def test_simple_rule(self):
        self.assertEqual(self.remove('p { }\n.QUJD { a: b }\n.x { }\n'),
                         ('p { }\n.x { }\n', ['QUJD']))

    def test_compound_selectors(self):
        self.assertEqual(
            self.remove('div.QUJD { }\n.a .QUJD { }\n.QUJD:hover { }\n'),
            ('', ['QUJD']))

    def test_selector_list(self):
        self.assertEqual(self.remove('p, .QUJD,\n.x { a: b }'),
                         ('p, .x { a: b }', ['QUJD']))

    def test_empty_media_removed(self):
        self.assertEqual(
            self.remove('@media print {\n  .QUJD { a: b }\n}\n'
                        '@media screen {\n  .QUJD { a: b }\n  .x { }\n}\n'),
            ('@media screen {\n  .x { }\n}\n', ['QUJD']))

    def test_other_classes_untouched(self):
        css = '.QUJDx { }\n/* .QUJD { } */\n[title=".QUJD"] { }\n'
        self.assertEqual(self.remove(css), (css, []))

    def test_crlf_kept(self):
        self.assertEqual(self.remove('.QUJD { }\r\np { }\r\n'),
                         ('p { }\r\n', ['QUJD']))


class ClassRulesTest(unittest.TestCase):

    def test_compound_selectors(self):
        self.assertEqual(
            class_rules('.a { font-size: 1px !important } '
                        'div.b, p .c, .d:hover, .e.F { display:none }'
                        ' span.g /* x */ { color: red; .x { a: b } }'),
            ([(None, {'a'}, [('font-size', '1px', True)]),
              ('div', {'b'}, [('display', 'none', False)]),
              (None, {'e', 'F'}, [('display', 'none', False)]),
              ('span', {'g'}, [('color', 'red', False)])],
             {'c', 'd'}))

    def test_uncertain(self):
        self.assertEqual(
            class_rules('@media print { .a { display: none } .b { color: '
                        'red } } .c { & .d { font: 0/0 a } } '
                        '@supports (x: y) { @media all { .e { all: unset '
                        '} } }'),
            ([(None, {'c'}, [])], {'a', 'c', 'd', 'e'}))


if __name__ == '__main__':
    unittest.main()
