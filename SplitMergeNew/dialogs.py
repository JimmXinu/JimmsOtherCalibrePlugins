#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division,
                        print_function)

import logging
logger = logging.getLogger(__name__)

__license__   = 'GPL v3'
__copyright__ = '2020, Jim Miller'
__docformat__ = 'restructuredtext en'

import traceback
from functools import partial

from six import text_type as unicode
from six.moves import range

from PyQt5.Qt import (QDialog, QTableWidget, QMessageBox, QVBoxLayout, QHBoxLayout, QGridLayout,
                      QPushButton, QProgressDialog, QLabel, QCheckBox, QIcon, QTextCursor,
                      QTextEdit, QLineEdit, QInputDialog, QComboBox, QClipboard,
                      QProgressDialog, QTimer, QDialogButtonBox, QPixmap, Qt,QAbstractItemView )
    
from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.ebooks.metadata import fmt_sidx

from calibre import confirm_config_name
from calibre.gui2 import dynamic

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

def LoopProgressDialog(gui,
                       book_list,
                       foreach_function,
                       finish_function,
                       init_label=_("Starting..."),
                       win_title=_("Working"),
                       status_prefix=_("Completed so far")):
    ld = _LoopProgressDialog(gui,
                             book_list,
                             foreach_function,
                             init_label,
                             win_title,
                             status_prefix)
    # Mac OS X gets upset if the finish_function is called from inside
    # the real _LoopProgressDialog class.

    # reflect old behavior.
    if not ld.wasCanceled():
        finish_function(book_list)
        
class _LoopProgressDialog(QProgressDialog):
    '''
    ProgressDialog displayed while fetching metadata for each story.
    '''
    def __init__(self,
                 gui,
                 book_list,
                 foreach_function,
                 init_label=_("Starting..."),
                 win_title=_("Working"),
                 status_prefix=_("Completed so far")):
        QProgressDialog.__init__(self,
                                 init_label,
                                 _('Cancel'), 0, len(book_list), gui)
        self.setWindowTitle(win_title)
        self.setMinimumWidth(500)
        self.book_list = book_list
        self.foreach_function = foreach_function
        self.status_prefix = status_prefix
        self.i = 0

        ## self.do_loop does QTimer.singleShot on self.do_loop also.
        ## A weird way to do a loop, but that was the example I had.
        QTimer.singleShot(0, self.do_loop)
        self.exec_()

    def updateStatus(self):
        self.setLabelText("%s %d of %d"%(self.status_prefix,self.i+1,len(self.book_list)))
        self.setValue(self.i+1)

    def do_loop(self):

        if self.i == 0:
            self.setValue(0)

        book = self.book_list[self.i]
        try:
            self.foreach_function(book)

        except Exception as e:
            book['good']=False
            book['comment']=unicode(e)
            logger.error("Exception: %s:%s"%(book,unicode(e)),exc_info=True)

        self.updateStatus()
        self.i += 1

        if self.i >= len(self.book_list) or self.wasCanceled():
            return self.do_when_finished()
        else:
            QTimer.singleShot(0, self.do_loop)

    def do_when_finished(self):
        # Queues a job to process these books in the background.
        self.setLabelText(_("Starting Merge..."))
        self.setValue(self.i+1)

        self.hide()
