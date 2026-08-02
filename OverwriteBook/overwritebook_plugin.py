#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2026, Jim Miller'
__docformat__ = 'restructuredtext en'

import logging
logger = logging.getLogger(__name__)

from functools import partial
import string, os
import copy
import six
from six import text_type as unicode

from PyQt5.Qt import ( QProgressDialog, QTimer, QDialog, QToolButton, QMenu )

from calibre.gui2 import error_dialog

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction
from calibre.ptempfile import PersistentTemporaryFile, PersistentTemporaryDirectory, remove_dir
from calibre.ebooks.metadata import MetaInformation, authors_to_string

from calibre.constants import ismacos
from calibre.gui2.dialogs.message_box import ViewLog
from calibre_plugins.overwritebook.common_utils import (get_icon, create_menu_action_unique)
from calibre_plugins.overwritebook.config import prefs
from calibre_plugins.overwritebook.dialogs import OfferSwapDialog
from calibre.gui2.actions.choose_library import library_qicon
from calibre.gui2.dialogs.confirm_delete import confirm

from calibre.gui2.actions.copy_to_library import ChooseLibrary

load_translations()

class OverwriteBookPlugin(InterfaceAction):

    name = 'OverwriteBook'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (_('OverwriteBook'),
                   'save.png',
                   _('Split out (new) Chapters from FFF books and merge together into one book.'),
                   ())
    # None for keyboard shortcut doesn't allow shortcut.  () does, there just isn't one yet

    action_type = 'global'

    # disable when not in library. (main,carda,cardb)
    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        # self.menuless_qaction.setEnabled(enabled)

    def genesis(self):

        # This method is called once per plugin, do initial setup here

        base = self.interface_action_base_plugin
        self.version = base.name+" v%d.%d.%d"%base.version

        # # Set the icon for this interface action
        # # The get_icons function is a builtin function defined for all your
        # # plugin code. It loads icons from the plugin zip file. It returns
        # # QIcon objects, if you want the actual data, use the analogous
        # # get_resources builtin function.

        # # Note that if you are loading more than one icon, for performance, you
        # # should pass a list of names to get_icons. In this case, get_icons
        # # will return a dictionary mapping names to QIcons. Names that
        # # are not found in the zip file will result in null QIcons.
        # icon = get_icon('catalog.png')

        # self.qaction.setText(_('OverwriteBook'))
        # # The qaction is automatically created from the action_spec defined
        # # above
        # self.qaction.setIcon(icon)

        # Call function when plugin triggered.
        self.qaction.triggered.connect(self.plugin_button)

    def do_error(self,msg):
        d = error_dialog(self.gui,
                         _('Cannot OverwriteBook'),
                         msg,
                         show_copy_button=False)
        d.exec_()

    def is_library_view(self):
        # 0 = library, 1 = main, 2 = card_a, 3 = card_b
        return self.gui.stack.currentIndex() == 0

    def plugin_button(self):

        if len(self.gui.library_view.get_selected_ids()) != 2:
            d = error_dialog(self.gui,
                             _('Select Two Books'),
                             _('Please select exactly two books, target first.'),
                             show_copy_button=False)
            d.exec_()
        else:
            if self.gui.content_server:
                self.do_error(_("OverwriteBook doesn't work while Content Server is running due to possible conflicts"))
                return
    
            if not self.gui.current_view().selectionModel().selectedRows() :
                self.do_error(_('No Selected Books for OverwriteBook'))
                return
    
            if not self.is_library_view():
                # device view, get from epubs on device.
                self.do_error(_('OverwriteBook only works in libary'))
                return

            (src_id, dest_id) = self.gui.library_view.get_selected_ids()

            src_mi = self.gui.current_db.get_metadata(src_id, index_is_id=True,
                                     get_cover=True, cover_as_data=True)
            dest_mi = self.gui.current_db.get_metadata(dest_id, index_is_id=True,
                                     get_cover=True, cover_as_data=True)

            done = False
            while not done:
                d = OfferSwapDialog(self.gui,_("Overwrite Book"),
                                    src_mi, dest_mi)
                d.exec_()
                if d.status == False:
                    done = True
                    return
                if d.status == "swap":
                    t_mi = src_mi
                    src_mi = dest_mi
                    dest_mi = t_mi
                    t_id = src_id
                    src_id = dest_id
                    dest_id = t_id
                if d.status == True:
                    self._do_overwrite(src_id,dest_id)
                    if confirm(_('Do you want to remove the source book from the list?'),
                               'overwritebook_delete_source', self.gui):
                        self.gui.iactions['Remove Books'].do_library_delete([src_id])
                    done = True
                    return
            
    def _do_overwrite(self,
                      src_id, dest_id=None,
                      src_db=None, dest_db=None):

        if not src_db:
            src_db = self.gui.current_db

        if not dest_db:
            dest_db = self.gui.current_db

        src_mi = src_db.get_metadata(src_id, index_is_id=True,
                                     get_cover=True, cover_as_data=True)

        if 'url' not in src_mi.get_identifiers():
            src_mi.set_identifiers({'url':"http://fake.url?uuid=%s"%src_mi.uuid})

        if dest_id is None:
            dest_ids = dest_db.search_getting_ids(r'identifiers:"=url:=%s"'%src_mi.get_identifiers()['url'],
                                                None,use_virtual_library=False)
            dest_id = None
            if len(dest_ids) > 1:
                logger.debug("Skipping %s -- too many matching identifiers (%s)"%(src_mi.get_identifiers()['url'],dest_ids))
                return
            if not dest_ids:
                ## make new if none found.
                dest_id = dest_db.create_book_entry(src_mi)
                logger.debug("Adding to dest library(%s)"%dest_id)
            else:
                dest_id = dest_ids[0]

        dest_mi = dest_db.get_metadata(dest_id, index_is_id=True)
        logger.debug(dest_mi.title)
        # overwrite Calibre columns.
        dest_db.set_metadata(dest_id,src_mi)

        ## =========== formats
        fmts = src_db.formats(src_id, index_is_id=True)
        fmts = fmts.split(',') if fmts else []
        logger.debug(fmts)
        dest_fmts = dest_db.formats(dest_id, index_is_id=True)
        dest_fmts = dest_fmts.split(',') if dest_fmts else []
        for fmt in fmts:
            logger.debug("Copying format(%s)"%fmt)
            dest_db.add_format_with_hooks(dest_id,
                                          fmt,
                                          src_db.format_abspath(src_id,
                                                            fmt,
                                                            index_is_id=True),
                                          index_is_id=True)
            if fmt in dest_fmts:
                dest_fmts.remove(fmt)
        # remove any formats not copied.
        for fmt in dest_fmts:
            logger.debug("Remove outdated dest format(%s)"%fmt)
            dest_db.remove_format(dest_id, fmt, index_is_id=True)

        # ============= cover
        if src_mi.cover_data and src_mi.cover_data[1]:
            logger.debug("Copy cover")
            dest_db.set_cover(dest_id,src_mi.cover_data[1])


        ## copy custom columns
        from_cols = src_db.field_metadata.custom_field_metadata()
        import pprint

        # logger.debug(pprint.pformat(from_cols))
        dest_cols = dest_db.field_metadata.custom_field_metadata()
        # logger.debug(dest_cols)

        for name, settings in from_cols.items():
            label=settings['label']
            # logger.debug(name)
            if name in dest_cols and settings['datatype'] == dest_cols[name]['datatype'] \
                    and dest_cols[name]['datatype'] != 'composite':
                val = src_db.get_custom(src_id,label=label,index_is_id=True)
                l = "Set (%s) = (%s)"%(label,val)
                logger.debug(l[:100]) # 100 max.

                self.set_custom(dest_db,dest_id,val,label,commit=True)
            # else:
            #     logger.debug("DON'T try to set")

    def set_custom(self,db,book_id,val,label,commit=True):
        def raise_exception(val,label,e):
            errmsg="Trying to set entry value(%s) to column (%s) failed (%s)"%(val,label,e)
            logger.warn(errmsg)
            raise Exception(errmsg)
        try:
            db.set_custom(book_id, val, label=label, commit=commit)
        except ValueError as ve:
            # editable flag off throws ValueError
            data = db.backend.custom_field_metadata(label)
            if not data['editable']:
                logger.debug("Skipping custom column(%s) update, column is set editable=False"%label)
            else:
                raise_exception(val,label,ve)
        except Exception as e:
            raise_exception(val,label,e)

