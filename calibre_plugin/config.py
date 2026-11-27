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

# stored in the calibre configuration folder (plugins/epubQTools.json),
# separately on every computer
prefs = JSONConfig('plugins/epubQTools')


def current_settings():
    return with_defaults(prefs.get('settings'))


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        layout = QVBoxLayout(self)

        box = QGroupBox('Dzielenie wyrazów', self)
        bl = QVBoxLayout(box)
        self.hyphenate = QCheckBox('Dziel wyrazy', box)
        self.hyphenate_headers = QCheckBox(
            'Dziel też wyrazy w nagłówkach (h1, h2, h3…)', box)
        self.hyphenate.toggled.connect(self.hyphenate_headers.setEnabled)
        bl.addWidget(self.hyphenate)
        bl.addWidget(self.hyphenate_headers)
        layout.addWidget(box)

        box = QGroupBox('Wygląd tekstu', self)
        bl = QVBoxLayout(box)
        self.reset_css = QCheckBox('Dołącz reset CSS', box)
        self.reset_css.setToolTip(
            'Bez tej opcji książka dzielona dostaje tylko CSS '
            '„hyphens: manual”.')
        bl.addWidget(self.reset_css)
        bl.addWidget(QLabel('Wyrównanie tekstu:', box))
        self.align = QButtonGroup(box)
        self.align_buttons = {}
        for value, text in (
                (ALIGN_JUSTIFY, 'Wyjustuj tekst wyrównany do lewej'),
                (ALIGN_LEFT, 'Wyrównaj do lewej tekst wyjustowany'),
                (ALIGN_KEEP, 'Bez zmian')):
            button = QRadioButton(text, box)
            self.align.addButton(button)
            self.align_buttons[value] = button
            bl.addWidget(button)
        self.remove_colors = QCheckBox('Usuń kolory', box)
        self.remove_colors.setToolTip(
            'Kolory są usuwane przy zmianie wyrównania, więc ta opcja '
            'działa tylko wtedy, gdy wyrównanie nie jest „Bez zmian”.')
        self.align_buttons[ALIGN_KEEP].toggled.connect(
            lambda keep: self.remove_colors.setEnabled(not keep))
        bl.addWidget(self.remove_colors)
        row = QHBoxLayout()
        self.use_margin = QCheckBox('Margines lewy i prawy:', box)
        self.margin = QSpinBox(box)
        self.margin.setRange(0, 200)
        self.margin.setSuffix(' px')
        self.use_margin.toggled.connect(self.margin.setEnabled)
        row.addWidget(self.use_margin)
        row.addWidget(self.margin)
        row.addStretch(1)
        bl.addLayout(row)
        layout.addWidget(box)

        box = QGroupBox('Fonty', self)
        bl = QVBoxLayout(box)
        self.remove_fonts = QCheckBox('Usuń wbudowane fonty', box)
        bl.addWidget(self.remove_fonts)
        layout.addWidget(box)

        box = QGroupBox('Inne', self)
        bl = QVBoxLayout(box)
        self.page_list = QCheckBox(
            'Dodaj przybliżoną listę stron (w książkach bez niej)', box)
        bl.addWidget(self.page_list)
        layout.addWidget(box)

        row = QHBoxLayout()
        row.addStretch(1)
        defaults = QPushButton('Przywróć domyślne', self)
        defaults.setToolTip('Ustawienia jak „-e” w terminalu.')
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
        self.margin.setEnabled(s['book_margin'] is not None)
        self.remove_fonts.setChecked(s['remove_fonts'])
        self.page_list.setChecked(s['page_list'])

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
