# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Settings window of the plugin (Preferences > Plugins > Customize, or
the menu of the toolbar button)."""

from qt.core import (QButtonGroup, QCheckBox, QComboBox, QGroupBox,
                     QHBoxLayout, QLabel, QPoint, QPushButton, QRadioButton,
                     QSpinBox, QTimer, QVBoxLayout, QWidget)

from calibre.utils.config import JSONConfig

from .options import (ALIGN_JUSTIFY, ALIGN_KEEP, ALIGN_LEFT, DEFAULTS,
                      KINDLE_SITES, with_defaults)
from .options import kindle_site as valid_kindle_site
from .translations import tr

# stored in the calibre configuration folder (plugins/epubQTools.json),
# separately on every computer
prefs = JSONConfig('plugins/epubQTools')

# layout of the settings window: 2 = two columns; calibre remembers the size
# of the window, so the size saved for an earlier layout is changed once
SETTINGS_LAYOUT = 2


def current_settings():
    return with_defaults(prefs.get('settings'))


def check_updates():
    """Check on GitHub for a new version of the plugin (on by default)."""
    return prefs.get('check_updates', True) is not False


def kindle_site():
    """Amazon site with the Send to Kindle page (amazon.com by default)."""
    return valid_kindle_site(prefs.get('kindle_site'))


def update_state():
    """What the last check for a new version found: 'last_check' (seconds),
    'found' (newer release or None), 'notified' (version shown in the
    window)."""
    state = prefs.get('update')
    return dict(state) if isinstance(state, dict) else {}


def save_update_state(state):
    prefs['update'] = state


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        # two columns, so the window fits on the screen of a small laptop:
        # the text of the book on the left, the rest on the right
        columns = QHBoxLayout(self)
        layout = QVBoxLayout()
        right = QVBoxLayout()
        columns.addLayout(layout)
        columns.addLayout(right)

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
        layout.addStretch(1)

        box = QGroupBox(tr('Other'), self)
        bl = QVBoxLayout(box)
        self.remove_fonts = QCheckBox(tr('Remove embedded fonts'), box)
        bl.addWidget(self.remove_fonts)
        self.page_list = QCheckBox(
            tr('Add an approximate page list (in books without one)'), box)
        bl.addWidget(self.page_list)
        right.addWidget(box)

        box = QGroupBox(tr('Passing to Send to Kindle'), self)
        bl = QHBoxLayout(box)
        bl.addWidget(QLabel(tr('Amazon site:'), box))
        self.kindle_site = QComboBox(box)
        self.kindle_site.addItems(KINDLE_SITES)
        self.kindle_site.setCurrentText(kindle_site())
        self.kindle_site.setToolTip(
            tr('The site of your Amazon account, where “Pass to Send to '
               'Kindle…” opens the Send to Kindle page.'))
        bl.addWidget(self.kindle_site)
        bl.addStretch(1)
        right.addWidget(box)

        box = QGroupBox(tr('New versions'), self)
        bl = QVBoxLayout(box)
        self.check_updates = QCheckBox(
            tr('Check for a new version of the plugin on GitHub (once a '
               'day)'), box)
        self.check_updates.setToolTip(
            tr('calibre asks GitHub once a day whether a newer version of '
               'epubQTools was released. Nothing about your books is '
               'sent.'))
        self.check_updates.setChecked(check_updates())
        bl.addWidget(self.check_updates)
        right.addWidget(box)
        right.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        defaults = QPushButton(tr('Restore defaults'), self)
        defaults.setToolTip(tr('Settings like “-c -r -e” in the terminal.'))
        defaults.clicked.connect(lambda: self.show_settings(DEFAULTS))
        row.addWidget(defaults)
        right.addLayout(row)

        self.show_settings(current_settings())
        self.window_fitted = False

    def showEvent(self, event):
        QWidget.showEvent(self, event)
        if not self.window_fitted:
            self.window_fitted = True
            # after calibre has restored the size saved last time
            QTimer.singleShot(0, self.fit_window)

    def fit_window(self):
        """The window of calibre with the settings big enough to show them
        without scrolling: once fitted to a new layout, later only made
        bigger when too small (the size set by the user is kept)."""
        window = self.window()
        if window is self:
            return
        hint = window.sizeHint()
        if prefs.get('settings_layout') != SETTINGS_LAYOUT:
            prefs['settings_layout'] = SETTINGS_LAYOUT
            size = hint
        else:
            size = window.size().expandedTo(hint)
        screen = window.screen().availableGeometry()
        size = size.boundedTo(screen.size())
        if size == window.size():
            return
        window.resize(size)
        frame = window.frameGeometry()
        x = max(screen.left(), min(frame.left(),
                                   screen.right() + 1 - frame.width()))
        y = max(screen.top(), min(frame.top(),
                                  screen.bottom() + 1 - frame.height()))
        if (x, y) != (frame.left(), frame.top()):
            window.move(window.pos() + QPoint(x - frame.left(),
                                              y - frame.top()))

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
        prefs['check_updates'] = self.check_updates.isChecked()
        prefs['kindle_site'] = self.kindle_site.currentText()
