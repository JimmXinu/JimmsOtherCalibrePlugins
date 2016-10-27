#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import pprint
pp = pprint.PrettyPrinter(indent=4)

import sys
from collections import OrderedDict
from functools import partial
try:
    from PyQt5.Qt import QMenu, QToolButton, QInputDialog
except ImportError as e:
    from PyQt4.Qt import QMenu, QToolButton, QInputDialog

from calibre.gui2.actions import InterfaceAction
from calibre.constants import numeric_version as calibre_version

from calibre.gui2 import error_dialog
import calibre_plugins.view_manager.config as cfg
from calibre_plugins.view_manager.common_utils import (set_plugin_icon_resources, get_icon,
                                        create_menu_action_unique)

PLUGIN_ICONS = ['images/view_manager.png', 'images/sort_asc.png', 'images/sort_desc.png']

class ViewManagerAction(InterfaceAction):

    name = 'View Manager'
    # Create our top-level menu/toolbar action (text, icon_path, tooltip, keyboard shortcut)
    action_spec = ('View Manager', None, None, None)
    popup_type = QToolButton.InstantPopup
    action_type = 'current'

    def genesis(self):
        self.menu = QMenu(self.gui)

        self.menu_actions = []
        #self.old_actions_unique_map = {}

        # Read the plugin icons and store for potential sharing with the config widget
        icon_resources = self.load_resources(PLUGIN_ICONS)
        set_plugin_icon_resources(self.name, icon_resources)

        # Assign our menu to this action and an icon
        self.qaction.setMenu(self.menu)
        self.qaction.setIcon(get_icon(PLUGIN_ICONS[0]))

    def initialization_complete(self):
        self.current_view = None
        if not self.check_switch_to_last_view_for_library():
            self.rebuild_menus()

    def library_changed(self, db):
        # We need to rebuild out menus when the library is changed, as each library
        # will have it's own set of views
        self.initialization_complete()

    def rebuild_menus(self):
        views = cfg.get_library_config(self.gui.current_db)[cfg.KEY_VIEWS]
        m = self.menu
        m.clear()

        #self.actions_unique_map = {}
        for action in self.menu_actions:
            self.gui.keyboard.unregister_shortcut(action.calibre_shortcut_unique_name)
            # starting in calibre 2.10.0, actions are registers at
            # the top gui level for OSX' benefit.
            if calibre_version >= (2,10,0):
                self.gui.removeAction(action)
        self.menu_actions = []

        if len(views) > 0:
            has_checked_view = False
            for key in sorted(views.keys()):
                is_checked = self.current_view == key
                shortcut_name = 'Apply View: ' + key
                ac = create_menu_action_unique(self, m, key, shortcut_name=shortcut_name,
                                               triggered=partial(self.switch_view, key),
                                               is_checked=is_checked)
                #self.actions_unique_map[ac.calibre_shortcut_unique_name] = ac.calibre_shortcut_unique_name
                self.menu_actions.append(ac)
                if is_checked:
                    has_checked_view = True
            m.addSeparator()
            save_ac = create_menu_action_unique(self, m, '&Save columns, widths and sorts', 'column.png',
                                                  triggered=self.save_column_widths)
            #self.actions_unique_map[save_ac.calibre_shortcut_unique_name] = save_ac.calibre_shortcut_unique_name
            self.menu_actions.append(save_ac)
            if not has_checked_view:
                save_ac.setEnabled(False)

        new_ac = create_menu_action_unique(self, m, '&Create new View', 'plus.png',
                                                  triggered=partial(self.save_column_widths,create=True))
        self.menu_actions.append(new_ac)
        m.addSeparator()

        create_menu_action_unique(self, m, _('&Customize plugin')+'...', 'config.png',
                                  shortcut=False, triggered=self.show_configuration)
        # for menu_id, unique_name in self.old_actions_unique_map.iteritems():
        #     if menu_id not in self.actions_unique_map:
        #         self.gui.keyboard.unregister_shortcut(unique_name)
        # self.old_actions_unique_map = self.actions_unique_map
        self.gui.keyboard.finalize()

    def check_switch_to_last_view_for_library(self):
        library_config = cfg.get_library_config(self.gui.current_db)
        if library_config.get(cfg.KEY_AUTO_APPLY_VIEW, False):
            view_to_apply = library_config.get(cfg.KEY_VIEW_TO_APPLY, cfg.LAST_VIEW_ITEM)
            if view_to_apply == cfg.LAST_VIEW_ITEM:
                last_view = library_config.get(cfg.KEY_LAST_VIEW, '')
                if last_view:
                    self.switch_view(library_config[cfg.KEY_LAST_VIEW])
                    return True
            else:
                self.switch_view(view_to_apply)
                return True
        return False

    def save_column_widths(self,create=False):
        if self.current_view is None and not create:
            return

        library_config = cfg.get_library_config(self.gui.current_db)
        views = library_config[cfg.KEY_VIEWS]
        new_view_name = None
        if create:
            ## code
            new_view_name, ok = QInputDialog.getText(self.gui, 'Add new view',
                                                     'Enter a unique display name for this view:', text='Default')
            if not ok:
                # Operation cancelled
                return
            new_view_name = unicode(new_view_name).strip()
            # Verify it does not clash with any other views in the list
            for view_name in views.keys():
                if view_name.lower() == new_view_name.lower():
                    return error_dialog(self.gui, 'Add Failed', 'A view with the same name already exists', show=True)

            view_info = { cfg.KEY_COLUMNS: [], cfg.KEY_SORT: [],
                          cfg.KEY_APPLY_RESTRICTION: False, cfg.KEY_RESTRICTION: '',
                          cfg.KEY_APPLY_SEARCH: False, cfg.KEY_SEARCH: '' }
            views[new_view_name] = view_info
        else:
            view_info = views[self.current_view]

        # Now need to identify the column widths for each column
        state = self.gui.library_view.get_state()
        pp.pprint(state)
        pp.pprint(view_info)
        sizes = state['column_sizes']
        new_config_cols = []

        prev_col_sizes = dict(view_info[cfg.KEY_COLUMNS])
        # ordered columns list from col_id->position map.
        ordered_cols = sorted(state['column_positions'], key=state['column_positions'].get)# state['column_positions'].items().sort(key=lambda x: x[1])
        # filter out hidden columns.
        ordered_cols = filter(lambda x : x not in state['hidden_columns'], ordered_cols)
        for col in ordered_cols:
            # I'm not sure under what circumstances the saved col size
            # would be needed, but the previous code fell back to it.
            # JM
            prev_size = prev_col_sizes.get(col,-1)
            new_config_cols.append((col, sizes.get(col, prev_size)))

        new_config_sort = []
        already_sorted = {}
        TF_map = { True:0, False:1 } # no idea why VM records asc/desc that way...
        for col, direct in state['sort_history']:
            if col not in already_sorted:
                already_sorted[col] = direct
                new_config_sort.append([unicode(col),TF_map[direct]])

        ## Not used--config only handles saved/named searches.  Also
        ## needs to deal with saved from 'current search'.  Similar
        ## issue with saving search.
        # Save search restriction
        # search_restrict = unicode(self.gui.search_restriction.currentText())
        # print("search_restrict:%s"%search_restrict)
        # if search_restrict:
        #     view_info[cfg.KEY_APPLY_RESTRICTION] = True
        #     view_info[cfg.KEY_RESTRICTION] = search_restrict
        # else:
        #     view_info[cfg.KEY_APPLY_RESTRICTION] = False
        #     view_info[cfg.KEY_RESTRICTION] = ''

        # Persist the updated view column info
        view_info[cfg.KEY_COLUMNS] = new_config_cols
        pp.pprint(new_config_sort)
        view_info[cfg.KEY_SORT] = new_config_sort
        library_config[cfg.KEY_VIEWS] = views
        cfg.set_library_config(self.gui.current_db, library_config)
        if create:
            self.rebuild_menus()
            self.switch_view(new_view_name)

    def switch_view(self, key):
        library_config = cfg.get_library_config(self.gui.current_db)
        view_info = library_config[cfg.KEY_VIEWS][key]
        selected_ids = self.gui.library_view.get_selected_ids()
        # Persist this as the last selected view
        if library_config.get(cfg.KEY_LAST_VIEW, None) != key:
            library_config[cfg.KEY_LAST_VIEW] = key
            cfg.set_library_config(self.gui.current_db, library_config)

        if view_info[cfg.KEY_APPLY_RESTRICTION]:
            self.apply_restriction(view_info[cfg.KEY_RESTRICTION])
        if view_info[cfg.KEY_APPLY_SEARCH]:
            self.apply_search(view_info[cfg.KEY_SEARCH])
        self.apply_column_and_sort(view_info)

        self.gui.library_view.select_rows(selected_ids)
        self.current_view = key
        self.rebuild_menus()

    def apply_restriction(self, restriction_name):
        current = unicode(self.gui.search_restriction.currentText())
        if current == restriction_name:
            return
        self.gui.apply_named_search_restriction(restriction_name)

    def apply_search(self, search_name):
        if len(search_name) == 0:
            self.gui.search.clear()
        else:
            idx = self.gui.saved_search.findText(search_name)
            if idx != -1:
                self.gui.saved_search.setCurrentIndex(idx)
                self.gui.saved_search.saved_search_selected(search_name)

    def apply_column_and_sort(self, view_info):
        model = self.gui.library_view.model()
        colmap = list(model.column_map)
        config_cols = view_info[cfg.KEY_COLUMNS]
        # Make sure our config contains only valid columns
        valid_cols = OrderedDict([(cname,width) for cname, width in config_cols if cname in colmap])
        if not valid_cols:
            valid_cols = OrderedDict([('title', -1)])
        config_cols = [cname for cname in valid_cols.keys()]
        hidden_cols = [c for c in colmap if c not in config_cols]
        if 'ondevice' in hidden_cols:
            hidden_cols.remove('ondevice')
        def col_pos(x, y):
            xidx = config_cols.index(x) if x in config_cols else sys.maxint
            yidx = config_cols.index(y) if y in config_cols else sys.maxint
            return cmp(xidx, yidx)
        positions = {}
        for i, col in enumerate((sorted(model.column_map, cmp=col_pos))):
            positions[col] = i

        # Now setup the sorting
        sort_cols = view_info[cfg.KEY_SORT]
        # Make sure our config contains only valid columns
        sort_cols = [(c, asc) for c, asc in sort_cols if c in colmap]
        sh = []
        for col, asc in sort_cols:
            sh.append((col, asc==0))

        print("set sort history:")
        pp.pprint(sh)
        resize_cols = dict([(cname, width) for cname, width in valid_cols.iteritems() if width > 0])
        state = {'hidden_columns': hidden_cols,
                 'column_positions': positions,
                 'sort_history': sh,
                 'column_sizes': resize_cols}

        self.gui.library_view.apply_state(state)
        self.gui.library_view.save_state()

    def show_configuration(self):
        self.interface_action_base_plugin.do_user_config(self.gui)
