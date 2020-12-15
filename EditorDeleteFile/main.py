# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__docformat__ = 'restructuredtext en'

try:
    from PyQt5.Qt import QAction, QMenu, QDialog, QIcon, QPixmap
except ImportError:
    from PyQt4.Qt import QAction, QMenu, QDialog, QIcon, QPixmap

import os

# The base class that all tools must inherit from
from calibre.gui2.tweak_book.plugin import Tool

def get_icon(icon_name):
    return QIcon(I(icon_name))

class DeleteFile(Tool):
    name = 'Delete File'

    #: If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    #: If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True

    def create_action(self, for_toolbar=True):

        # Create an action, this will be added to the plugins toolbar and
        # the plugins menu
        ac = QAction(get_icon('trash.png'), _('Delete Open File'), self.gui)
        if not for_toolbar:
            # Register a keyboard shortcut for this toolbar action. We only
            # register it for the action created for the menu, not the toolbar,
            # to avoid a double trigger
            self.register_shortcut(ac, 'delete-this-file', default_keys=('Alt+Delete',))
        ac.triggered.connect(self.delete_file)
        return ac

    def delete_file(self):
        print(self.boss.gui.file_list.file_list.current_edited_name)
        
        # self.boss.delete_requested([self.boss.gui.file_list.file_list.current_edited_name],{})
        self.request_delete(self.boss.gui.file_list.file_list)

    # inspired by calibre.gui2.tweak_book.file_list.request_delete()
    def request_delete(self,file_list):
        from calibre.gui2.tweak_book.file_list import NAME_ROLE
        from calibre.gui2.tweak_book import current_container
        from calibre.gui2 import error_dialog
        from polyglot.builtins import unicode_type

        # names = set([file_list.current_edited_name])
        name = file_list.current_edited_name
        if name in current_container().names_that_must_not_be_removed:
            return error_dialog(file_list, _('Cannot delete'),
                         _('The file(s) %s cannot be deleted.') % ('<b>%s</b>' % name), show=True)

        spine_removals = []
        other_removals = set()
        
        found = False
        treetext = file_list.categories['text']
        for i in range(treetext.childCount()):
            item = treetext.child(i)
            namerole = unicode_type(item.data(0, NAME_ROLE) or '')
            spine_removals.append((namerole,namerole==name))
            if spine_removals[-1][1]:
                found = True
        if not found:
            ## if it's not a spine object, assume 'other'
            other_removals.add(name)
            
        print(spine_removals)
        print(other_removals)
        self.boss.delete_requested(spine_removals, other_removals)

    def other(self):
        children = (text.child(i) for i in range(text.childCount()))
        spine_removals = [(unicode_type(item.data(0, NAME_ROLE) or ''), unicode_type(item.data(0, NAME_ROLE) or '')==name) for item in children]
        other_removals = set()
        if not spine_removals:
            ## if it's not a spine object, assume 'other'
            other_removals.add(name)
            
        print(spine_removals)
        print(other_removals)
        self.boss.delete_requested(spine_removals, other_removals)
