# -*- coding: utf-8 -*-
#
# This file is part of epubQTools, licensed under GNU Affero GPLv3 or later.
# Copyright © Robert Błaut. See NOTICE for more information.
#

"""Check on GitHub whether a newer version of the plugin was released.
Plain Python (no calibre imports), so it can be tested without calibre."""

import json
import re
import urllib.request

LATEST_URL = ('https://api.github.com/repos/quiris11/epubQTools/releases/'
              'latest')
PLUGIN_ZIP = re.compile(r'^epubQTools-calibre-.+\.zip$')
CHECK_EVERY = 24 * 60 * 60          # seconds: once a day
TIMEOUT = 15                        # seconds


def parse_version(text):
    """'v1.2' or '1.2.0' -> (1, 2, 0); None when it is not a version."""
    text = (text or '').strip()
    if text[:1] in ('v', 'V'):
        text = text[1:]
    if not re.match(r'^\d+(\.\d+)*$', text):
        return None
    numbers = [int(n) for n in text.split('.')]
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def version_text(version):
    """(1, 2, 0) -> '1.2', (1, 2, 1) -> '1.2.1'."""
    numbers = list(version)
    while len(numbers) > 2 and numbers[-1] == 0:
        numbers.pop()
    return '.'.join(str(n) for n in numbers)


def is_newer(version, current):
    """True when the text version is newer than the tuple current."""
    found = parse_version(version)
    return found is not None and found > parse_version(
        '.'.join(str(n) for n in current))


def newer_release(release, current):
    """{'version': '1.1', 'url': <page of the release>} when release (the
    answer of GitHub) is newer than current (tuple) and has the zip of the
    plugin; None otherwise."""
    if not isinstance(release, dict):
        return None
    if release.get('draft') or release.get('prerelease'):
        return None
    version = parse_version(release.get('tag_name'))
    url = release.get('html_url')
    if (version is None or not isinstance(url, str) or
            not url.startswith('https://github.com/')):
        return None
    assets = release.get('assets')
    if not isinstance(assets, list) or not any(
            isinstance(a, dict) and PLUGIN_ZIP.match(str(a.get('name')))
            for a in assets):
        return None
    text = version_text(version)
    if not is_newer(text, current):
        return None
    return {'version': text, 'url': url}


def check_due(last_check, now):
    """True when the last check (seconds, or None) was a day ago or more
    (or the clock was moved back)."""
    if not isinstance(last_check, (int, float)):
        return True
    return now - last_check >= CHECK_EVERY or now < last_check


def fetch_latest(current, timeout=TIMEOUT):
    """The newer release on GitHub (as newer_release) or None. Raises an
    exception when GitHub cannot be asked (no internet etc.)."""
    request = urllib.request.Request(LATEST_URL, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'epubQTools-calibre-plugin'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        release = json.loads(response.read().decode('utf-8'))
    return newer_release(release, current)
