#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division,
                        print_function)

import logging
logger = logging.getLogger(__name__)

__license__   = 'GPL v3'
__copyright__ = '2026, Jim Miller'
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

from calibre_plugins.overwritebook.common_utils import (
    SizePersistedDialog)

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

class OfferSwapDialog(SizePersistedDialog):
    '''
    Show src -> dest books, offer OK/Cancel/Swap
    '''
    def __init__(self, gui, title, src_mi, dest_mi):
        SizePersistedDialog.__init__(self, gui, 'overwritebook:offer swap')
        self.status=False

        self.setMinimumWidth(300)

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.setWindowTitle(title)

        horz = QHBoxLayout()
        self.l.addLayout(horz)

        template = '''
<h3>{0.title}</h3>
<p>{0.authors}</p>
<p>Date:{0.timestamp}<br>
ID:{0.id}<br>
UUID:{0.uuid}</p>
'''

        label = QLabel("<h2>Source</h2>"+template.format(src_mi))
        horz.addWidget(label)

        label = QLabel("<h2>Destination</h2>"+template.format(dest_mi))
        horz.addWidget(label)

        self.swap_button = QPushButton(_('Swap'), self)
        self.swap_button.setToolTip(_('Switch Source and Destination.'))
        self.swap_button.clicked.connect(self.swap)
        self.l.addWidget(self.swap_button)

        horz = QHBoxLayout()
        self.l.addLayout(horz)

        self.overwrite_button = QPushButton(_('Overwrite'), self)
        self.overwrite_button.clicked.connect(self.overwrite)
        horz.addWidget(self.overwrite_button)

        self.cancel_button = QPushButton(_('Cancel'), self)
        self.cancel_button.clicked.connect(self.cancel)
        horz.addWidget(self.cancel_button)

        # restore saved size.
        self.resize_dialog()

    def swap(self):
        self.status="swap"
        self.accept()

    def overwrite(self):
        self.status=True
        self.accept()

    def cancel(self):
        self.status=False
        self.reject()

