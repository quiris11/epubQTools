# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Window with the Send to Kindle page of Amazon in the browser built into
calibre. The user logs in there (calibre remembers it) and when the page
asks for files, it gets the prepared books without the window for choosing
files; the user only clicks Send. Nothing is sent by the plugin itself.

For safety the window shows only secure Amazon pages: the address with a
lock is always visible, other addresses open in the web browser of the
system, the books are given only to Amazon pages. "Forget the saved login"
removes the remembered login, "Send via my browser…" is for those who
prefer to log in in their own browser.

Without the built-in browser (some Linux packages of calibre) the page is
opened in the web browser of the system and the folder with the books in
the file manager, the books are dragged to the page by the user."""

import os
import re
import shutil

from qt.core import (QApplication, QHBoxLayout, QIcon, QLabel, QPushButton,
                     Qt, QTimer, QUrl, QVBoxLayout, QWidget)

from calibre.constants import config_dir
from calibre.gui2 import open_local_file, open_url

from .options import is_amazon_url
from .translations import tr

try:
    from qt.webengine import (QWebEnginePage, QWebEngineProfile,
                              QWebEngineView)
except ImportError:
    QWebEngineView = None

# the login to Amazon is kept here, separately from calibre's own browser
PROFILE_DIR = os.path.join(config_dir, 'plugins', 'epubQTools Send to Kindle')

_profile = None


def has_browser():
    return QWebEngineView is not None


def profile():
    """One profile for the whole calibre session (cookies kept on disk)."""
    global _profile
    if _profile is None:
        _profile = QWebEngineProfile('epubQTools-sendtokindle',
                                     QApplication.instance())
        _profile.setPersistentStoragePath(PROFILE_DIR)
        _profile.setCachePath(os.path.join(PROFILE_DIR, 'cache'))
        _profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        # without "QtWebEngine/x.y": Amazon sees the usual Chrome
        _profile.setHttpUserAgent(re.sub(r' QtWebEngine/\S+', '',
                                         _profile.httpUserAgent()))
    return _profile


def titles_text(paths):
    return ', '.join(os.path.basename(p)[:-len('.epub')] for p in paths)


def open_outside(url):
    """An address in the web browser of the system (only http and https)."""
    if url.scheme() in ('http', 'https'):
        open_url(url)


if QWebEngineView is not None:

    class Page(QWebEnginePage):
        """Only Amazon pages; gives the books to the page instead of the
        window for choosing files."""

        def __init__(self, parent):
            QWebEnginePage.__init__(self, profile(), parent)
            self.files = []
            self.certificate_error = False
            self.certificateError.connect(self.reject_certificate)
            self.loadStarted.connect(self.load_started)

        def load_started(self):
            self.certificate_error = False

        def reject_certificate(self, error):
            # the default too, but the address then shows a warning
            self.certificate_error = True
            error.rejectCertificate()

        def acceptNavigationRequest(self, url, navigation_type,
                                    is_main_frame):
            if not is_main_frame or is_amazon_url(url.toString()):
                return True
            open_outside(url)
            return False

        def createWindow(self, window_type):
            # links opening a new window
            return OutsidePage(self)

        def chooseFiles(self, mode, old_files, accepted_mime_types):
            if not is_amazon_url(self.url().toString()):
                return []
            modes = QWebEnginePage.FileSelectionMode
            if mode == modes.FileSelectOpenMultiple:
                return list(self.files)
            if mode == modes.FileSelectOpen:
                return self.files[:1]
            return QWebEnginePage.chooseFiles(self, mode, old_files,
                                              accepted_mime_types)

    class OutsidePage(QWebEnginePage):
        """A new window asked by the page: its address goes to the web
        browser of the system."""

        def __init__(self, parent):
            QWebEnginePage.__init__(self, profile(), parent)

        def acceptNavigationRequest(self, url, navigation_type,
                                    is_main_frame):
            open_outside(url)
            self.deleteLater()
            return False

    class SendToKindleWindow(QWidget):

        def __init__(self, parent, url):
            QWidget.__init__(self, parent, Qt.WindowType.Window)
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.setWindowTitle('Send to Kindle – epubQTools')
            self.dirs = []
            self.opened_dirs = set()
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            bar = QHBoxLayout()
            bar.setContentsMargins(10, 8, 10, 0)
            self.lock = QLabel(self)
            bar.addWidget(self.lock)
            self.address = QLabel(self)
            self.address.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            bar.addWidget(self.address, 1)
            button = QPushButton(tr('Send via my browser…'), self)
            button.setToolTip(tr(
                'For sending without logging in here: opens the page in your '
                'web browser and the folder with the books next to it – drag '
                'the books to the page.'))
            button.clicked.connect(self.open_in_my_browser)
            bar.addWidget(button)
            button = QPushButton(tr('Forget the saved login'), self)
            button.setToolTip(tr(
                'Removes the Amazon login remembered on this computer.'))
            button.clicked.connect(self.forget_login)
            bar.addWidget(button)
            layout.addLayout(bar)

            self.info = QLabel(self)
            self.info.setWordWrap(True)
            self.info.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            self.info.setContentsMargins(10, 8, 10, 8)
            layout.addWidget(self.info)
            self.view = QWebEngineView(self)
            self.page = Page(self.view)
            self.view.setPage(self.page)
            self.view.urlChanged.connect(self.show_address)
            self.page.loadStarted.connect(self.show_address)
            self.page.loadFinished.connect(self.show_address)
            layout.addWidget(self.view, 1)
            self.books_lines = []
            self.notice = ''
            self.resize(1100, 850)
            self.load(url)

        def load(self, url):
            self.url = url
            self.view.load(QUrl(url))
            self.show_address()

        def current_url(self):
            url = self.view.url()
            return url if not url.isEmpty() else QUrl(self.url)

        def show_address(self, *args):
            url = self.current_url()
            host = url.host() or url.toString()
            if (is_amazon_url(url.toString()) and
                    not self.page.certificate_error):
                icon = 'drm-locked.png'
                self.address.setStyleSheet('font-weight: bold')
                self.address.setText(tr('Secure connection: %s') % host)
            else:
                icon = 'dialog_warning.png'
                self.address.setStyleSheet('font-weight: bold; color: red')
                self.address.setText(tr(
                    '%s – not a secure Amazon page, do not log in '
                    'here') % host)
            self.lock.setPixmap(QIcon.ic(icon).pixmap(20, 20))
            self.secure = icon == 'drm-locked.png'

        def show_info(self):
            lines = [tr('You log in directly on the Amazon page. The plugin '
                        'does not read your password and sends nothing by '
                        'itself – its code is open.') + ' ' +
                     tr('Prefer not to log in here? Use “Send via my '
                        'browser…”.')]
            lines += self.books_lines
            if self.notice:
                lines += ['', self.notice]
            self.info.setText('\n'.join(lines))

        def set_books(self, work_dir, paths, skipped):
            """Books given to the page from now on; the folders of the
            earlier ones are removed when the window is closed (an upload
            may still read them)."""
            self.dirs.append(work_dir)
            self.page.files = list(paths)
            lines = [tr('Ready to send (%d): %s') % (len(paths),
                                                     titles_text(paths))]
            if skipped:
                lines.append(tr('Skipped – not fixed by epubQTools (%d): '
                                '%s') % (len(skipped), ', '.join(skipped)))
            lines.append(tr('Click the button for choosing files on the '
                            'page – the books are added by themselves – '
                            'and then the button for sending.'))
            self.books_lines = lines
            self.notice = ''
            self.show_info()

        def open_in_my_browser(self):
            """The Amazon page in the web browser of the system and the
            folder with the books in the file manager; that folder is kept
            until calibre is closed."""
            url = self.current_url()
            if not is_amazon_url(url.toString()):
                url = QUrl(self.url)
            open_outside(url)
            if self.dirs:
                open_local_file(self.dirs[-1])
                self.opened_dirs.add(self.dirs[-1])
            self.notice = tr(
                'The page was opened in your web browser and the folder with '
                'the books next to it. Drag the books to the page and click '
                'the button for sending. The folder is removed when calibre '
                'is closed.')
            self.show_info()

        def forget_login(self):
            """Remove the cookies (the login), the cache and the history
            of the window, then show the page again."""
            p = profile()
            p.cookieStore().deleteAllCookies()
            p.clearHttpCache()
            p.clearAllVisitedLinks()
            self.page.history().clear()
            self.notice = tr('The Amazon login remembered on this computer '
                             'was removed.')
            self.show_info()
            # the cookies are removed in the background
            QTimer.singleShot(1000, lambda: self.view.load(QUrl(self.url)))

        def closeEvent(self, event):
            for d in self.dirs:
                if d not in self.opened_dirs:
                    shutil.rmtree(d, ignore_errors=True)
            self.dirs = []
            QWidget.closeEvent(self, event)


def open_in_system_browser(url, work_dir):
    """Without the built-in browser: the page in the system browser and
    the folder with the books in the file manager (the folder is removed
    when calibre is closed)."""
    open_url(QUrl(url))
    open_local_file(work_dir)
