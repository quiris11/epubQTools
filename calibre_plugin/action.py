# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Toolbar button of the plugin: fix the selected books (default action),
restore the originals, pass the fixed books to Send to Kindle, settings,
a new version on GitHub."""

import shutil
import threading
import time

from qt.core import (QMenu, QModelIndex, QTimer, QToolButton, QUrl,
                     pyqtSignal)

from calibre.gui2 import (Dispatcher, error_dialog, info_dialog, open_url,
                          question_dialog, warning_dialog)
from calibre.gui2.actions import InterfaceAction
from calibre.ptempfile import PersistentTemporaryDirectory

from . import update
from .config import (check_updates, current_settings, kindle_site,
                     save_update_state, update_state)
from .library import (copy_books, copy_fixed_books, has_original,
                      restore_original, store_fixed)
from .options import send_to_kindle_url
from .translations import tr

TITLE = 'epubQTools'


def titles(results):
    return '\n'.join('  • ' + r['title'] for r in results)


class EpubQToolsAction(InterfaceAction):

    name = 'epubQTools'
    action_spec = ('epubQTools', 'beautify.png',
                   tr('Fix the selected EPUB books (like epubQTools -e)'),
                   None)
    popup_type = QToolButton.ToolButtonPopupMode.MenuButtonPopup
    action_type = 'current'
    dont_add_to = frozenset(['context-menu-device', 'toolbar-device'])

    # sent from the thread of the check: (time of the check, newer release
    # or None)
    update_checked = pyqtSignal(object, object)

    def genesis(self):
        self.menu = QMenu(self.gui)
        self.create_menu_action(
            self.menu, 'epubqtools-fix', tr('Fix the selected books'),
            icon='beautify.png', triggered=self.fix_selected)
        self.create_menu_action(
            self.menu, 'epubqtools-restore', tr('Restore the original'),
            icon='edit-undo.png', triggered=self.restore_selected)
        self.create_menu_action(
            self.menu, 'epubqtools-send-to-kindle',
            tr('Pass to Send to Kindle…'), icon='send.png',
            triggered=self.send_to_kindle)
        self.send_window = None
        self.menu.addSeparator()
        self.create_menu_action(
            self.menu, 'epubqtools-settings', tr('Settings…'),
            icon='config.png', triggered=self.show_settings)
        self.update_action = self.create_menu_action(
            self.menu, 'epubqtools-update', tr('Download the new version…'),
            icon='plugins/plugin_updater_updates.png',
            triggered=self.open_update_page)
        self.update_action.setVisible(False)
        self.update_found = None
        self.qaction.setMenu(self.menu)
        self.qaction.triggered.connect(self.fix_selected)
        self.update_checked.connect(self.update_check_done)

    def initialization_complete(self):
        self.show_update(update_state().get('found'))
        # a moment after the start, so calibre is not slowed down
        QTimer.singleShot(5000, self.start_update_check)

    def selected_ids(self):
        return list(self.gui.library_view.get_selected_ids())

    def refresh(self, book_ids):
        model = self.gui.library_view.model()
        model.refresh_ids(book_ids)
        current = self.gui.library_view.currentIndex()
        if current.isValid():
            model.current_changed(current, QModelIndex())

    def show_settings(self):
        self.interface_action_base_plugin.do_user_config(self.gui)
        self.show_update(self.update_found)

    def plugin_version(self):
        return self.interface_action_base_plugin.version

    def show_update(self, found):
        """Menu item for a newer version found on GitHub (hidden when the
        check is turned off or the plugin was updated)."""
        if not (isinstance(found, dict) and check_updates() and
                str(found.get('url')).startswith('https://github.com/') and
                update.is_newer(found.get('version'),
                                self.plugin_version())):
            found = None
        self.update_found = found
        if found:
            self.update_action.setText(
                tr('New version %s – download…') % found['version'])
        self.update_action.setVisible(bool(found))

    def open_update_page(self):
        if self.update_found:
            open_url(QUrl(self.update_found['url']))

    def start_update_check(self):
        """Ask GitHub in the background, at most once a day; without the
        internet nothing is shown and the next start tries again."""
        if not check_updates():
            return
        now = time.time()
        if not update.check_due(update_state().get('last_check'), now):
            return
        current = self.plugin_version()

        def run():
            try:
                found = update.fetch_latest(current)
            except Exception:
                return
            self.update_checked.emit(now, found)

        threading.Thread(target=run, name='epubQTools: new version',
                         daemon=True).start()

    def update_check_done(self, when, found):
        state = update_state()
        state['last_check'] = when
        state['found'] = found
        notify = bool(found) and state.get('notified') != found['version']
        if notify:
            state['notified'] = found['version']
        save_update_state(state)
        self.show_update(found)
        if notify and self.update_found and question_dialog(
                self.gui, TITLE,
                tr('A new version of epubQTools is available: %s (you have '
                   '%s). Open the download page?') % (
                    found['version'],
                    update.version_text(self.plugin_version()))):
            self.open_update_page()

    def fix_selected(self):
        book_ids = self.selected_ids()
        if not book_ids:
            return error_dialog(self.gui, TITLE,
                                tr('No book is selected.'), show=True)
        db = self.gui.current_db.new_api
        work_dir = PersistentTemporaryDirectory('_epubqtools')
        settings = current_settings()
        books, skipped = copy_books(
            db, book_ids, work_dir,
            with_pages=settings['page_list'] and settings['description_pages'])
        if not books:
            shutil.rmtree(work_dir, ignore_errors=True)
            return error_dialog(
                self.gui, TITLE,
                tr('None of the selected books has the EPUB format.'),
                show=True)
        job = self.gui.job_manager.run_job(
            Dispatcher(self.fix_done), 'arbitrary_n',
            args=['calibre_plugins.epubqtools.worker', 'fix_books',
                  (self.interface_action_base_plugin.plugin_path, books,
                   settings)],
            description=tr('epubQTools: fixing books (%d)') % len(books))
        job.epubqtools = {'library_id': self.gui.current_db.library_id,
                          'work_dir': work_dir, 'skipped': skipped}
        self.gui.status_bar.show_message(
            tr('epubQTools: fixing books (%d)…') % len(books), 3000)

    def fix_done(self, job):
        info = job.epubqtools
        try:
            if job.failed:
                return self.gui.job_exception(
                    job, dialog_title=tr('epubQTools: unexpected error'))
            if self.gui.current_db.library_id != info['library_id']:
                return error_dialog(
                    self.gui, TITLE,
                    tr('Another library was opened while working – the '
                       'fixed books were not saved.'), show=True)
            self.store_results(job.result, info['skipped'])
        finally:
            shutil.rmtree(info['work_dir'], ignore_errors=True)

    def store_results(self, results, skipped):
        db = self.gui.current_db.new_api
        saved, failed, gone = [], [], []
        for r in results:
            if not r['fixed']:
                failed.append(r)
            elif store_fixed(db, r['id'], r['fixed']):
                saved.append(r)
            else:
                gone.append(r)
        if saved:
            self.refresh([r['id'] for r in saved])
        problems = [r for r in saved if r['problems']]
        lines = [tr('Fixed: %d of %d') % (len(saved),
                                          len(results) + len(skipped))]
        if problems:
            lines += ['', tr('Saved, but with problems (see details):'),
                      titles(problems)]
        if failed:
            lines += ['',
                      tr('Could not be fixed (no changes in the library):'),
                      titles(failed)]
        if gone:
            lines += ['', tr('Removed from the library while working:'),
                      titles(gone)]
        if skipped:
            lines += ['', tr('Without the EPUB format (skipped):'),
                      '\n'.join('  • ' + t for t in skipped)]
        details = '\n\n'.join('=== %s ===\n%s' % (r['title'], r['log'].strip())
                              for r in results)
        dialog = (warning_dialog if problems or failed or gone or skipped
                  else info_dialog)
        dialog(self.gui, TITLE, '\n'.join(lines), det_msg=details,
               show=True, show_copy_button=True)

    def restore_selected(self):
        book_ids = self.selected_ids()
        db = self.gui.current_db.new_api
        with_original = [i for i in book_ids if has_original(db, i)]
        if not with_original:
            return info_dialog(
                self.gui, TITLE,
                tr('The selected books have no original saved by '
                   'epubQTools.'), show=True)
        if not question_dialog(
                self.gui, TITLE,
                tr('Restore the original in the selected books (%d)? The '
                   'fixed EPUB will be replaced with the original saved '
                   'by epubQTools.') % len(with_original)):
            return
        work_dir = PersistentTemporaryDirectory('_epubqtools')
        try:
            restored = [i for i in with_original
                        if restore_original(db, i, work_dir)]
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        if restored:
            self.refresh(restored)
        self.gui.status_bar.show_message(
            tr('epubQTools: original restored (%d)') % len(restored), 3000)

    def send_to_kindle(self):
        """Open the Send to Kindle page with the EPUB of the selected books
        fixed by epubQTools (the other ones are skipped)."""
        from . import sendtokindle
        book_ids = self.selected_ids()
        if not book_ids:
            return error_dialog(self.gui, TITLE,
                                tr('No book is selected.'), show=True)
        db = self.gui.current_db.new_api
        work_dir = PersistentTemporaryDirectory('_epubqtools_kindle')
        paths, skipped = copy_fixed_books(db, book_ids, work_dir)
        if not paths:
            shutil.rmtree(work_dir, ignore_errors=True)
            return error_dialog(
                self.gui, TITLE,
                tr('None of the selected books was fixed by epubQTools – '
                   'fix them first.'), show=True)
        url = send_to_kindle_url(kindle_site())
        if not sendtokindle.has_browser():
            sendtokindle.open_in_system_browser(url, work_dir)
            lines = [tr('calibre has no built-in browser, so the page was '
                        'opened in your web browser and the folder with '
                        'the books (%d) next to it. Drag the books to the '
                        'page and click the button for sending.') % len(paths)]
            if skipped:
                lines += ['', tr('Skipped – not fixed by epubQTools:'),
                          '\n'.join('  • ' + t for t in skipped)]
            return info_dialog(self.gui, TITLE, '\n'.join(lines), show=True)
        window = self.send_window
        if window is None:
            window = sendtokindle.SendToKindleWindow(self.gui, url)
            window.destroyed.connect(self.send_window_closed)
            self.send_window = window
        elif window.url != url:         # another site in the settings
            window.load(url)
        window.set_books(work_dir, paths, skipped)
        window.show()
        window.raise_()
        window.activateWindow()

    def send_window_closed(self):
        self.send_window = None
