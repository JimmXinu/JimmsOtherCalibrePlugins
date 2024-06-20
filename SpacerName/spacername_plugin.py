#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2022, Jim Miller'
__docformat__ = 'restructuredtext en'

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

class SpacerNamePlugin(InterfaceAction):

    name = 'name var ========================================='

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (_('SpacerName'),
                   None,
                   _('A spacer for main toolbar.  That is all.'),
                   ())
    # None for keyboard shortcut doesn't allow shortcut.  () does, there just isn't one yet

    action_type = 'global'

    def genesis(self):

        # This method is called once per plugin, do initial setup here

        base = self.interface_action_base_plugin
        self.version = base.name+" v%d.%d.%d"%base.version

        self.qaction.setText('---==========================---')
        # Call function when plugin triggered.
        # self.qaction.triggered.connect(self.plugin_button)

