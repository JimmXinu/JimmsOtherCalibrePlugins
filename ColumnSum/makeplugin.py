#!/usr/bin/python
# -*- coding: utf-8 -*-


__license__   = 'GPL v3'
__copyright__ = '2019, Jim Miller'
__docformat__ = 'restructuredtext en'

import os
from glob import glob

import makezip

if __name__=="__main__":
    
    filename="ColumnSum.zip"
    exclude=['*.pyc','*~','*.xcf','makezip.py','makeplugin.py','*.po','*.pot','*.notes','*default.mo']
    # from top dir. 'w' for overwrite
    #from calibre-plugin dir. 'a' for append
    files=['translations',]
    files.extend(glob('*.py'))
    files.extend(glob('plugin-import-name-*.txt'))
    makezip.createZipFile(filename,"w",
                          files,exclude=exclude)
    
