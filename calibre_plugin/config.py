# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Settings window of the plugin (Preferences > Plugins > Customize, or
the menu of the toolbar button)."""

from qt.core import (QButtonGroup, QCheckBox, QGroupBox, QHBoxLayout,
                     QLabel, QPushButton, QRadioButton, QSpinBox,
                     QVBoxLayout, QWidget)

from calibre.utils.config import JSONConfig

from .options import (ALIGN_JUSTIFY, ALIGN_KEEP, ALIGN_LEFT, DEFAULTS,
                      with_defaults)
from .translations import tr

# stored in the calibre configuration folder (plugins/epubQTools.json),
# separately on every computer
prefs = JSONConfig('plugins/epubQTools')


def current_settings():
    return with_defaults(prefs.get('settings'))


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        layout = QVBoxLayout(self)

        box = QGroupBox(tr('Hyphenation'), self)
        bl = QVBoxLayout(box)
        self.hyphenate = QCheckBox(tr('Hyphenate words'), box)
        self.hyphenate_headers = QCheckBox(
            tr('Hyphenate also words in headings (h1, h2, h3…)'), box)
        self.hyphenate.toggled.connect(self.hyphenate_headers.setEnabled)
        bl.addWidget(self.hyphenate)
        bl.addWidget(self.hyphenate_headers)
        layout.addWidget(box)

        box = QGroupBox(tr('Text appearance'), self)
        bl = QVBoxLayout(box)
        self.reset_css = QCheckBox(tr('Add a CSS reset'), box)
        self.reset_css.setToolTip(
            tr('Without this option a hyphenated book gets only the CSS '
               '“hyphens: manual”.'))
        bl.addWidget(self.reset_css)
        bl.addWidget(QLabel(tr('Text alignment:'), box))
        self.align = QButtonGroup(box)
        self.align_buttons = {}
        for value, text in (
                (ALIGN_JUSTIFY, tr('Justify text aligned to the left')),
                (ALIGN_LEFT, tr('Align justified text to the left')),
                (ALIGN_KEEP, tr('No change'))):
            button = QRadioButton(text, box)
            self.align.addButton(button)
            self.align_buttons[value] = button
            bl.addWidget(button)
        self.remove_colors = QCheckBox(tr('Remove colors'), box)
        self.remove_colors.setToolTip(
            tr('Colors are removed when the alignment is changed, so this '
               'option works only when the alignment is not “No change”.'))
        self.align_buttons[ALIGN_KEEP].toggled.connect(
            lambda keep: self.remove_colors.setEnabled(not keep))
        bl.addWidget(self.remove_colors)
        row = QHBoxLayout()
        self.use_margin = QCheckBox(tr('Left and right margin:'), box)
        self.margin = QSpinBox(box)
        self.margin.setRange(0, 200)
        self.margin.setSuffix(' px')
        self.use_margin.setToolTip(
            tr('The margin is written to the CSS reset, so this option '
               'works only with “Add a CSS reset”.'))
        self.reset_css.toggled.connect(self.update_margin)
        self.use_margin.toggled.connect(self.update_margin)
        row.addWidget(self.use_margin)
        row.addWidget(self.margin)
        row.addStretch(1)
        bl.addLayout(row)
        layout.addWidget(box)

        box = QGroupBox(tr('Fonts'), self)
        bl = QVBoxLayout(box)
        self.remove_fonts = QCheckBox(tr('Remove embedded fonts'), box)
        bl.addWidget(self.remove_fonts)
        layout.addWidget(box)

        box = QGroupBox(tr('Other'), self)
        bl = QVBoxLayout(box)
        self.page_list = QCheckBox(
            tr('Add an approximate page list (in books without one)'), box)
        bl.addWidget(self.page_list)
        layout.addWidget(box)

        row = QHBoxLayout()
        row.addStretch(1)
        defaults = QPushButton(tr('Restore defaults'), self)
        defaults.setToolTip(tr('Settings like “-c -r -e” in the terminal.'))
        defaults.clicked.connect(lambda: self.show_settings(DEFAULTS))
        row.addWidget(defaults)
        layout.addLayout(row)
        layout.addStretch(1)

        self.show_settings(current_settings())

    def show_settings(self, settings):
        s = with_defaults(settings)
        self.hyphenate.setChecked(s['hyphenate'])
        self.hyphenate_headers.setChecked(s['hyphenate_headers'])
        self.hyphenate_headers.setEnabled(s['hyphenate'])
        self.reset_css.setChecked(s['reset_css'])
        self.align_buttons[s['align']].setChecked(True)
        self.remove_colors.setChecked(s['remove_colors'])
        self.remove_colors.setEnabled(s['align'] != ALIGN_KEEP)
        self.use_margin.setChecked(s['book_margin'] is not None)
        self.margin.setValue(s['book_margin'] or 0)
        self.update_margin()
        self.remove_fonts.setChecked(s['remove_fonts'])
        self.page_list.setChecked(s['page_list'])

    def update_margin(self):
        """The margin only with the CSS reset (qfix writes it there)."""
        reset = self.reset_css.isChecked()
        self.use_margin.setEnabled(reset)
        self.margin.setEnabled(reset and self.use_margin.isChecked())

    def settings(self):
        align = next(value for value, button in self.align_buttons.items()
                     if button.isChecked())
        return with_defaults({
            'hyphenate': self.hyphenate.isChecked(),
            'hyphenate_headers': self.hyphenate_headers.isChecked(),
            'reset_css': self.reset_css.isChecked(),
            'align': align,
            'remove_colors': self.remove_colors.isChecked(),
            'remove_fonts': self.remove_fonts.isChecked(),
            'book_margin': (self.margin.value()
                            if self.use_margin.isChecked() else None),
            'page_list': self.page_list.isChecked(),
        })

    def save_settings(self):
        prefs['settings'] = self.settings()
