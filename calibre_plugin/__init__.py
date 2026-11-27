# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""epubQTools as a calibre plugin: fixes the selected EPUB books like
'epubQTools -e'. The fixed book becomes the EPUB format, the original is
kept as ORIGINAL_EPUB. Build the plugin with build_calibre_plugin.py."""

from calibre.customize import InterfaceActionBase


class EpubQToolsPlugin(InterfaceActionBase):

    name = 'epubQTools'
    description = ('Poprawia zaznaczone książki EPUB tak jak '
                   '„epubQTools -e”. Poprawiona wersja staje się formatem '
                   'EPUB, oryginał zostaje jako ORIGINAL_EPUB.')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Robert Błaut'
    version = (1, 0, 0)
    minimum_calibre_version = (6, 0, 0)
    actual_plugin = 'calibre_plugins.epubqtools.action:EpubQToolsAction'

    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre_plugins.epubqtools.config import ConfigWidget
        return ConfigWidget()

    def save_settings(self, config_widget):
        config_widget.save_settings()
