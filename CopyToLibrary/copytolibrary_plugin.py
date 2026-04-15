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
from calibre_plugins.copytolibrary.common_utils import (get_icon, create_menu_action_unique)
from calibre_plugins.copytolibrary.config import prefs
from calibre_plugins.copytolibrary.dialogs import (
    LoopProgressDialog
    )
from calibre.gui2.actions.choose_library import library_qicon

from calibre.gui2.actions.copy_to_library import ChooseLibrary

load_translations()

class CopyToLibraryPlugin(InterfaceAction):

    name = 'CopyToLibrary'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (_('CopyToLibrary'),
                   'copy-to-library.png',
                   _('Split out (new) Chapters from FFF books and merge together into one book.'),
                   ())
    # None for keyboard shortcut doesn't allow shortcut.  () does, there just isn't one yet

    action_type = 'global'
    popup_type = QToolButton.InstantPopup

    def genesis(self):

        # This method is called once per plugin, do initial setup here

        base = self.interface_action_base_plugin
        self.version = base.name+" v%d.%d.%d"%base.version

        # Assign our menu to this action
        self.menu = QMenu()
        self.qaction.setMenu(self.menu)


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

        # self.qaction.setText(_('CopyToLibrary'))
        # # The qaction is automatically created from the action_spec defined
        # # above
        # self.qaction.setIcon(icon)

        # # Call function when plugin triggered.
        # self.qaction.triggered.connect(self.plugin_button)

    def library_changed(self, db):
        self.build_menus()

    def initialization_complete(self):
        self.library_changed(self.gui.library_view.model().db)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        # self.menuless_qaction.setEnabled(enabled)

    def build_menus(self):
        self.menu.clear()
        if os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH', None):
            self.menu.addAction('disabled', self.cannot_do_dialog)
            return
        db = self.gui.library_view.model().db
        locations = list(self.gui.iactions['Choose Library'].stats.locations(db))
        for name, path in locations:
            ic = library_qicon(name)
            name = name.replace('&', '&&')
            ac = create_menu_action_unique(self,self.menu,
                                           name, None, _('CopyToLibrary: {}').format(name),
                                           shortcut=(), shortcut_name='CopyToLibrary: {}'.format(name),
                                           unique_name='CopyToLibrary: {}'.format(path),
                                           triggered=partial(self.copy_to_library, path))
            ac.setIcon(ic)

        self.qaction.setVisible(bool(locations))
        if ismacos:
            # The cloned action has to have its menu updated
            self.qaction.changed.emit()

    def do_error(self,msg):
        d = error_dialog(self.gui,
                         _('Cannot CopyToLibrary'),
                         msg,
                         show_copy_button=False)
        d.exec_()

    def copy_to_library(self, path):
        logger.debug("copy_to_library(%s)"%path)
        if not self.gui.current_view().selectionModel().selectedRows() :
            self.do_error(_('No Selected Books for CopyToLibrary'))
            return

        if not self.is_library_view():
            # device view, get from epubs on device.
            self.do_error(_('CopyToLibrary only works in libary'))
            return

        book_list = [ self._convert_id_to_book(x, self.gui.current_db, good=False) for x in self.gui.library_view.get_selected_ids() ]

        if not book_list:
            # device view, get from epubs on device.
            self.gui.status_bar.show_message(_('CopyToLibrary operates on selected books'))
            return

        db = self.gui.current_db
        current = os.path.normcase(os.path.abspath(db.library_path))
        if current == os.path.normcase(os.path.abspath(path)):
            self.do_error(_('Cannot copy to current library.'))
            return

        if not db.exists_at(path):
            self.do_error(_('No library found at %s')%path)
            return

        from calibre.db.legacy import LibraryDatabase
        dest_db = LibraryDatabase(path, is_second_db=True)
        logger.debug("dest_db.library_id: %s"%dest_db.library_id)

        logger.debug("before LoopProgressDialog!")
        LoopProgressDialog(self.gui,
                           book_list,
                           partial(self._do_loop,
                                   db=db,
                                   dest_db=dest_db),
                           partial(self._finish_loop,
                                   db=db,
                                   dest_db=dest_db),
                           init_label=_("Collecting books..."),
                           win_title=_("Get books"),
                           status_prefix=_("books collected"))

    ## XXX dead code - switched to menu based.
    def plugin_button(self):
        if not self.gui.current_view().selectionModel().selectedRows() :
            self.do_error(_('No Selected Books for CopyToLibrary'))
            return

        if not self.is_library_view():
            # device view, get from epubs on device.
            self.do_error(_('CopyToLibrary only works in libary'))
            return

        book_list = [ self._convert_id_to_book(x, self.gui.current_db, good=False) for x in self.gui.library_view.get_selected_ids() ]

        if not book_list:
            # device view, get from epubs on device.
            self.do_error(_('CopyToLibrary operates on selected books'))
            return

        ## choose destination library
        # self.gui.iactions['Copy to library'].

        path = ''
        delete_after = False
        db = self.gui.current_db
        locations = list(self.gui.iactions['Choose Library'].stats.locations(db))
        logger.debug(locations)
        d = ChooseLibrary(self.gui, locations)
        if d.exec() == QDialog.DialogCode.Accepted:
            path, delete_after = d.args
            if not path:
                self.do_error(_('Not Destination Library selected.'))
                return
            current = os.path.normcase(os.path.abspath(db.library_path))
            if current == os.path.normcase(os.path.abspath(path)):
                self.do_error(_('Cannot copy to current library.'))
                return
        else:
            return
        logger.debug("\n\n%s %s\n"%(path,delete_after))

        if not db.exists_at(path):
            self.do_error(_('No library found at %s')%path)
            return

        from calibre.db.legacy import LibraryDatabase
        dest_db = LibraryDatabase(path, is_second_db=True)
        logger.debug("dest_db.library_id: %s"%dest_db.library_id)


        logger.debug("before LoopProgressDialog!")
        LoopProgressDialog(self.gui,
                           book_list,
                           partial(self._do_loop,
                                   db=db,
                                   dest_db=dest_db),
                           partial(self._finish_loop,
                                   db=db,
                                   dest_db=dest_db),
                           init_label=_("Collecting books..."),
                           win_title=_("Get books"),
                           status_prefix=_("books collected"))

    def _do_loop(self, book, db=None, dest_db=None):
        # logger.debug(book)

        mi = book['mi']

        dest_ids = dest_db.search_getting_ids(r'identifiers:"=url:=%s"'%mi.get_identifiers()['url'],
                                            None,use_virtual_library=False)

        dest_id = None
        if len(dest_ids) > 1:
            logger.debug("Skipping %s -- too many matching identifiers (%s)"%(mi.get_identifiers()['url'],dest_ids))
            return
        if not dest_ids:
            ## make new if none found.
            dest_id = dest_db.create_book_entry(mi)
            logger.debug("Adding to dest library(%s)"%dest_id)
        else:
            dest_id = dest_ids[0]
            dest_mi = dest_db.get_metadata(dest_id, index_is_id=True)
            logger.debug(dest_mi.title)
            # overwrite Calibre columns.
            dest_db.set_metadata(dest_id,mi)

        ## =========== formats
        fmts = db.formats(book['calibre_id'], index_is_id=True)
        fmts = fmts.split(',') if fmts else []
        logger.debug(fmts)
        dest_fmts = dest_db.formats(dest_id, index_is_id=True)
        dest_fmts = dest_fmts.split(',') if dest_fmts else []
        for fmt in fmts:
            logger.debug("Copying format(%s)"%fmt)
            dest_db.add_format_with_hooks(dest_id,
                                          fmt,
                                          db.format_abspath(book['calibre_id'],
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
        if mi.cover_data and mi.cover_data[1]:
            logger.debug("Copy cover")
            dest_db.set_cover(dest_id,mi.cover_data[1])


        ## copy custom columns
        from_cols = db.field_metadata.custom_field_metadata()
        import pprint

        # logger.debug(pprint.pformat(from_cols))
        dest_cols = dest_db.field_metadata.custom_field_metadata()
        # logger.debug(dest_cols)

        for name, settings in from_cols.items():
            label=settings['label']
            logger.debug(name)
            if name in dest_cols and settings['datatype'] == dest_cols[name]['datatype'] \
                    and dest_cols[name]['datatype'] != 'composite':
                val = db.get_custom(book['calibre_id'],label=label,index_is_id=True)
                l = "Try to set (%s) to (%s)"%(label,val)
                logger.debug(l[:100]) # 100 max.

                self.set_custom(dest_db,dest_id,val,label,commit=True)
            else:
                logger.debug("DON'T try to set")

        return book

    def _finish_loop(self, book_list, db=None, dest_db=None):
        # logger.debug(book_list)
        pass

    def is_library_view(self):
        # 0 = library, 1 = main, 2 = card_a, 3 = card_b
        return self.gui.stack.currentIndex() == 0

    def _convert_id_to_book(self, idval, db, good=True):
        book = {}
        book['good'] = good
        book['calibre_id'] = idval

        mi = db.get_metadata(book['calibre_id'], index_is_id=True,
                             get_cover=True, cover_as_data=True)
        book['mi']=mi

        return book

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

