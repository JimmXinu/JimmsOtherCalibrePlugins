# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__docformat__ = 'restructuredtext en'

from qt.core import ( QAction, QMenu, QDialog, QIcon, QPixmap,
                      QVBoxLayout, QLabel, QLineEdit, QCheckBox,
                      QDialogButtonBox
                       )

import os

# The base class that all tools must inherit from
from calibre.gui2.tweak_book.plugin import Tool

from calibre.gui2.tweak_book import current_container, tprefs
from calibre.gui2.tweak_book.templates import template_for
#from calibre.gui2.tweak_book.file_list import FILE_COPY_MIME, NewFileDialog

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.css import add_stylesheet_links
from calibre.ebooks.oeb.polish.container import get_container as _gc
from calibre.ebooks.oeb.polish.utils import OEB_FONTS, guess_type
from calibre.ebooks.oeb.polish.toc import (
    TOC, get_toc, commit_toc
)

from calibre.ptempfile import TemporaryDirectory
from calibre.gui2.tweak_book.file_list import NAME_ROLE, name_is_ok
from calibre.gui2 import error_dialog
from calibre.gui2.widgets import BusyCursor

from polyglot.builtins import unicode_type

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

        self.request_delete(self.boss.gui.file_list.file_list)

    # inspired by calibre.gui2.tweak_book.file_list.request_delete()
    def request_delete(self,file_list):

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

'''
## works perfectly well, just didn't do what I wanted exactly.
class CompareOriginal(Tool):
    name = 'Compare Original Loaded'

    #: If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    #: If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True

    def create_action(self, for_toolbar=True):
        # Create an action, this will be added to the plugins toolbar and
        # the plugins menu
        ac = QAction(get_icon('diff.png'), _('Compare Original Loaded'), self.gui)
        if not for_toolbar:
            # Register a keyboard shortcut for this toolbar action. We only
            # register it for the action created for the menu, not the toolbar,
            # to avoid a double trigger
            self.register_shortcut(ac, 'compare-original', default_keys=('Alt+F6',))
        ac.triggered.connect(self.compare_original)
        return ac

    def compare_original(self):
        # print(self.boss.gui.checkpoints)
        m = self.boss.gui.checkpoints.view.model()
        self.boss.gui.checkpoints.view.setCurrentIndex(m.index(0))
        self.boss.gui.checkpoints.compare_clicked()
'''

class CompareOriginalFile(Tool):
    name = 'Compare Original File'

    #: If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    #: If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True

    def create_action(self, for_toolbar=True):
        # Create an action, this will be added to the plugins toolbar and
        # the plugins menu
        ac = QAction(get_icon('diff.png'), _('Compare Original File'), self.gui)
        if not for_toolbar:
            # Register a keyboard shortcut for this toolbar action. We only
            # register it for the action created for the menu, not the toolbar,
            # to avoid a double trigger
            self.register_shortcut(ac, 'compare-original-file', default_keys=('F6',))
        ac.triggered.connect(self.compare_original)
        return ac

    def compare_original(self):
        self.boss.commit_all_editors_to_container()

        c = current_container()
        # path = choose_files(self.gui, 'select-book-for-comparison', _('Choose book'), filters=[
        #     (_('%s books') % c.book_type.upper(), (c.book_type,))], select_only_single_file=True, all_files=False)
        # if path and path[0]:
        path = os.path.abspath(c.path_to_ebook)
        with TemporaryDirectory('_compare') as tdir:
            other = _gc(path, tdir=tdir, tweak_mode=True)
            d = self.boss.create_diff_dialog(revert_msg=None)
            d.container_diff(other, c,
                             names=(_('Original File'), _('Current book')))

class AddNewFileTOC(Tool):
    name = 'Add New File and TOC'

    #: If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    #: If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True

    def create_action(self, for_toolbar=True):
        # Create an action, this will be added to the plugins toolbar and
        # the plugins menu
        ac = QAction(get_icon('document-new.png'), _('Add New File to book and TOC'), self.gui)
        if not for_toolbar:
            # Register a keyboard shortcut for this toolbar action. We only
            # register it for the action created for the menu, not the toolbar,
            # to avoid a double trigger
            self.register_shortcut(ac, 'add-file-and-toc-file', default_keys=('Ctrl+Num++',))
        ac.triggered.connect(self.add_file_and_toc)
        return ac

    def add_file_and_toc(self):
        if not self.boss.ensure_book(_('You must first open a book to edit, before trying to create new files in it.')):
            return
        self.boss.commit_dirty_opf()
        d = NewFileDialog(self.boss.gui)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        added_name = self.boss.do_add_file(d.file_name, d.file_data, using_template=d.using_template, edit_file=True)
        if d.file_name.rpartition('.')[2].lower() in ('ttf', 'otf', 'woff'):
            from calibre.gui2.tweak_book.manage_fonts import (
                show_font_face_rule_for_font_file,
            )
            show_font_face_rule_for_font_file(d.file_data, added_name, self.boss.gui)
        if d.title.text():
            # frag = add_id(self.ebook, name, *frag)
            # container, name, loc
            with BusyCursor():
                toc = get_toc(current_container())
                print(toc)
                toc.add(d.title.text(), d.file_name)
                print(toc)
                commit_toc(current_container(),
                           toc,
                           lang=toc.lang,
                           uid=toc.uid)
                current_container().commit()
                self.boss.set_modified()
                self.boss.update_editors_from_container()
                self.boss.gui.toc_view.update_if_visible()
                self.boss.gui.file_list.build(current_container())

class NewFileDialog(QDialog):  # {{{

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel(_(
            'Choose a name for the new (blank) file. To place the file in a'
            ' specific folder in the book, include the folder name, for example: <i>text/chapter1.html'))
        la.setWordWrap(True)
        self.setWindowTitle(_('Choose file'))
        l.addWidget(la)
        self.name = n = QLineEdit(self)
        n.textChanged.connect(self.update_ok)
        l.addWidget(n)
        self.la = la = QLabel(_(
            'Choose a chapter title (replaces %CHAPTER% in template) and for ToC for example: <i>Chapter 1</i>'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.title = t = QLineEdit(self)
        l.addWidget(t)
        self.link_css = lc = QCheckBox(_('Automatically add style-sheet links into new HTML files'))
        lc.setChecked(tprefs['auto_link_stylesheets'])
        l.addWidget(lc)
        self.err_label = la = QLabel('')
        la.setWordWrap(True)
        l.addWidget(la)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.imp_button = b = bb.addButton(_('Import resource file (image/font/etc.)'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('view-image.png'))
        b.setToolTip(_('Import a file from your computer as a new'
                       ' file into the book.'))
        b.clicked.connect(self.import_file)

        self.ok_button = bb.button(QDialogButtonBox.StandardButton.Ok)

        self.file_data = b''
        self.using_template = False
        self.setMinimumWidth(350)

    def show_error(self, msg):
        self.err_label.setText('<p style="color:red">' + msg)
        return False

    def import_file(self):
        path = choose_files(self, 'tweak-book-new-resource-file', _('Choose file'), select_only_single_file=True)
        if path:
            self.do_import_file(path[0])

    def do_import_file(self, path, hide_button=False):
        self.link_css.setVisible(False)
        with open(path, 'rb') as f:
            self.file_data = f.read()
        name = os.path.basename(path)
        fmap = get_recommended_folders(current_container(), (name,))
        if fmap[name]:
            name = '/'.join((fmap[name], name))
        self.name.setText(name)
        self.la.setText(_('Choose a name for the imported file'))
        if hide_button:
            self.imp_button.setVisible(False)

    @property
    def name_is_ok(self):
        return name_is_ok(str(self.name.text()), self.show_error)

    def update_ok(self, *args):
        self.ok_button.setEnabled(self.name_is_ok)

    def accept(self):
        if not self.name_is_ok:
            return error_dialog(self, _('No name specified'), _(
                'You must specify a name for the new file, with an extension, for example, chapter1.html'), show=True)
        tprefs['auto_link_stylesheets'] = self.link_css.isChecked()
        print("title:%s"%self.title.text())
        name = str(self.name.text())
        name, ext = name.rpartition('.')[0::2]
        name = (name + '.' + ext.lower()).replace('\\', '/')
        mt = guess_type(name)
        if not self.file_data:
            if mt in OEB_DOCS:
                self.file_data = template_for('html').replace('%CHAPTER%',self.title.text()).encode('utf-8')
                if tprefs['auto_link_stylesheets']:
                    data = add_stylesheet_links(current_container(), name, self.file_data)
                    if data is not None:
                        self.file_data = data
                self.using_template = True
            elif mt in OEB_STYLES:
                self.file_data = template_for('css').encode('utf-8')
                self.using_template = True
        self.file_name = name
        QDialog.accept(self)
# }}}
