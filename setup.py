from distutils.core import setup
import py2exe
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))

sys.argv.append('py2exe')
setup(
    options={
        'py2exe': {
            'compressed': 1,
            'optimize': 2,
            'bundle_files': 1,
            'dist_dir': 'dist',
            'xref': False,
            'skip_archive': False,
            'ascii': False,
            'dll_excludes': ['w9xpopen.exe'],
            'includes': ['lxml.etree', 'lxml._elementpath', 'gzip'],
        }
    },
    zipfile=None,
    console=[{'script': '__main__.py', 'dest_base': 'epubQTools'}],
    packages=['lib'],
    data_files=[('resources', [
        'lib/resources/cover.xhtml',
        'lib/resources/ncx2end-0.2.xsl'
    ]), ('resources/dictionaries', [
        'lib/resources/dictionaries/hyph_pl_PL.dic',
        'lib/resources/dictionaries/README_hyph_pl.txt'
    ])],
)
