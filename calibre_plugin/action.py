# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Toolbar button of the plugin: fix the selected books (default action),
restore the originals, settings."""

import shutil

from qt.core import QMenu, QModelIndex, QToolButton

from calibre.gui2 import (Dispatcher, error_dialog, info_dialog,
                          question_dialog, warning_dialog)
from calibre.gui2.actions import InterfaceAction
from calibre.ptempfile import PersistentTemporaryDirectory

from .config import current_settings
from .library import copy_books, has_original, restore_original, store_fixed
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

    def genesis(self):
        self.menu = QMenu(self.gui)
        self.create_menu_action(
            self.menu, 'epubqtools-fix', tr('Fix the selected books'),
            icon='beautify.png', triggered=self.fix_selected)
        self.create_menu_action(
            self.menu, 'epubqtools-restore', tr('Restore the original'),
            icon='edit-undo.png', triggered=self.restore_selected)
        self.menu.addSeparator()
        self.create_menu_action(
            self.menu, 'epubqtools-settings', tr('Settings…'),
            icon='config.png', triggered=self.show_settings)
        self.qaction.setMenu(self.menu)
        self.qaction.triggered.connect(self.fix_selected)

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

    def fix_selected(self):
        book_ids = self.selected_ids()
        if not book_ids:
            return error_dialog(self.gui, TITLE,
                                tr('No book is selected.'), show=True)
        db = self.gui.current_db.new_api
        work_dir = PersistentTemporaryDirectory('_epubqtools')
        books, skipped = copy_books(db, book_ids, work_dir)
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
                   current_settings())],
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
