# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__docformat__ = 'restructuredtext en'


from calibre.customize import EditBookToolPlugin

class JimmsEditorAddons(EditBookToolPlugin):

    name = 'Jimms Editor Addons'
    version = (0,0,0)
    author = ''
    supported_platforms = ['windows', 'osx', 'linux']
    description = 'Jimms Editor Addons'
    minimum_calibre_version = (5, 6, 0)
