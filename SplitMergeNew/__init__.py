#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2020, Jim Miller'
__docformat__ = 'restructuredtext en'

# The class that all Interface Action plugin wrappers must inherit from
from calibre.customize import InterfaceActionBase

import sys, os
if sys.version_info >= (2, 7):
    import logging
    logger = logging.getLogger(__name__)
    loghandler=logging.StreamHandler()
    loghandler.setFormatter(logging.Formatter("SplitMergeNew: %(levelname)s: %(asctime)s: %(filename)s(%(lineno)d): %(message)s"))
    logger.addHandler(loghandler)

    from calibre.constants import DEBUG
    if os.environ.get('CALIBRE_WORKER', None) is not None or DEBUG:
        loghandler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        loghandler.setLevel(logging.CRITICAL)
        logger.setLevel(logging.CRITICAL)

## Apparently the name for this class doesn't matter.
class SplitMergeNewBase(InterfaceActionBase):
    '''
    This class is a simple wrapper that provides information about the
    actual plugin class. The actual interface plugin class is called
    SplitMergeNewPlugin and is defined in the splitmergenew_plugin.py file, as
    specified in the actual_plugin field below.

    The reason for having two classes is that it allows the command line
    calibre utilities to run without needing to load the GUI libraries.
    '''
    name                = 'SplitMergeNew'
    description         = _('UI plugin to split "(new)" chapters from selected FFF books and merge them into one new book.')
    supported_platforms = ['windows', 'osx', 'linux']
    author              = 'Jim Miller'
    version             = (0, 6, 0)
    minimum_calibre_version = (2, 85, 1)

    #: This field defines the GUI plugin class that contains all the code
    #: that actually does something. Its format is module_path:class_name
    #: The specified class must be defined in the specified module.
    actual_plugin       = 'calibre_plugins.splitmergenew.splitmergenew_plugin:SplitMergeNewPlugin'

