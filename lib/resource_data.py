#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Reading the files of lib/resources wherever the code runs: from a folder,
from a zip file (python epubQTools.zip), as a calibre plugin or as
a standalone application."""

import os
import sys


def read_resource(name):
    """Return the bytes of lib/resources/<name>; name uses "/" between
    folders (e.g. "dictionaries/hyph_pl_PL.dic")."""
    rel = 'resources/' + name
    loader = __loader__
    try:
        if hasattr(loader, 'get_data'):
            # a folder or a zip file
            return loader.get_data(os.path.join(
                os.path.dirname(__file__), *rel.split('/')))
        if hasattr(loader, 'open_resource'):
            # a calibre plugin: paths are relative to this module's package
            with loader.open_resource(rel) as f:
                return f.read()
        raise OSError('Cannot read the resource: ' + name)
    except OSError:
        if not getattr(sys, 'frozen', False):
            raise
    # a standalone application with resources next to its executable
    with open(os.path.join(os.path.dirname(sys.executable), 'resources',
                           *name.split('/')), 'rb') as f:
        return f.read()
