# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""epubQTools as a calibre plugin: fixes the selected EPUB books like
'epubQTools -e'. The fixed book becomes the EPUB format, the original is
kept as a data file of the book. Build the plugin with
build_calibre_plugin.py."""

from calibre.customize import InterfaceActionBase

from .translations import tr


class EpubQToolsPlugin(InterfaceActionBase):

    name = 'epubQTools'
    description = tr('Fixes the selected EPUB books like “epubQTools -e”. '
                     'The fixed version becomes the EPUB format, the '
                     'original is kept in the data files of the book.')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Robert Błaut'
    version = (1, 0, 0)
    minimum_calibre_version = (6, 17, 0)   # data files of books
    actual_plugin = 'calibre_plugins.epubqtools.action:EpubQToolsAction'

    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre_plugins.epubqtools.config import ConfigWidget
        return ConfigWidget()

    def save_settings(self, config_widget):
        config_widget.save_settings()
