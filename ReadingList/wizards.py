#!/usr/bin/env python
# vim:fileencoding=utf-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import re, copy, os, csv
from functools import partial

import six
from six import text_type as unicode
from six.moves import range

from PyQt5.Qt import (QWizard, QWizardPage, QApplication, Qt, QTabWidget,
                      QWidget, QTextEdit, QGridLayout, QLabel, QGroupBox,
                      QVBoxLayout, QPushButton, QComboBox, QTableWidget,
                      QHBoxLayout, QAbstractItemView, QLineEdit, QToolButton,
                      QThread, pyqtSignal, QStyle, QMenu, QAction, QRadioButton,
                      QCheckBox, QSpinBox)

from calibre import as_unicode
from calibre.debug import iswindows
from calibre.ebooks.metadata import fmt_sidx
from calibre.gui2 import gprefs, error_dialog, choose_files
from calibre.gui2.dialogs.confirm_delete import confirm

from calibre_plugins.reading_list.common_utils import (ReadOnlyTableWidgetItem,
                                                   get_icon, TextIconWidgetItem)
from calibre_plugins.reading_list.algorithms import (LibraryHashBuilder, authors_to_list,
                                get_title_algorithm_fn, get_author_algorithm_fn,
                                CACHED_ALGORITHMS, get_title_tokens, get_author_tokens)

TEST_BOOKS_TEXT = 'Septimus Heap: The Magykal Papers (Angie Sage)\n' \
                  'Young Samurai: The Way of the Sword (Chris Bradford)'

TEST_BOOKS_TEXT3 = 'Dead Witch Walking / Kim Harrison\n' \
                  'Keeping The Dead (Tess Gerritsen)\n' \
                  'Shall We Tell the President? (Jeffrey Archer)\n' \
                  'L.A. Requiem Foo / Robert Crais\n' \
                  'Warlock (Wilbur A. Smith)\n' \
                  'Angels & Demons (Dan Brown)\n' \
                  'Orcs (Stan Nicholls)\n' \
                  'The Kings of Clonmel: Book 8 (John Flanagan)\n' \
                  'Inferno\n'

TEST_BOOKS_TEXT2 = 'Book Title 1 / Author A\n' \
                  'Book Title 2 / Author B;Author C\n' \
                  'JimmXinu'

DEFAULT_CLIP_PATTERNS = [('Title - Author',  '(?P<title>.*?) \- (?P<author>.*)'),
                         ('Title by Author', '(?P<title>.*?) by (?P<author>.*)'),
                         ('Title / Author',  '(?P<title>.*?) / (?P<author>.*)'),
                         ('Title (Author)',  '(?P<title>.*?) \((?P<author>.*)\)')]


def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]

def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')


class WizardPage(QWizardPage):

    def __init__(self, db, parent):
        QWizardPage.__init__(self, parent)
        self.db = db
        self.info = parent.info
        self.worker = parent.worker
        self.init_controls()

    def init_controls(self):
        pass


class PreviewBookTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setDefaultSectionSize(24)
        self.populate_table([])

    def populate_table(self, books):
        self.clear()
        self.setRowCount(len(books))
        header_labels = ['Title', 'Author']
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.horizontalHeader().setStretchLastSection(True)

        for row, book in enumerate(books):
            self.populate_table_row(row, book)

        self.resizeColumnsToContents()
        self.setMinimumColumnWidth(0, 150)

    def setMinimumColumnWidth(self, col, minimum):
        if self.columnWidth(col) < minimum:
            self.setColumnWidth(col, minimum)

    def populate_table_row(self, row, book):
        self.setItem(row, 0, ReadOnlyTableWidgetItem(book['title']))
        self.setItem(row, 1, ReadOnlyTableWidgetItem(book['author']))


class CSVRowsTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        #self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setDefaultSectionSize(self.verticalHeader().minimumSectionSize())

    def populate_table(self, csv_rows):
        self.clear()
        self.setRowCount(len(csv_rows))
        header_labels = [str(col) for col in range(1, len(csv_rows[0])+1)]
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.horizontalHeader().setStretchLastSection(True)

        for row, csv_row in enumerate(csv_rows):
            self.populate_table_row(row, csv_row)

        self.resizeColumnsToContents()

    def populate_table_row(self, row, csv_row):
        for col, col_data in enumerate(csv_row):
            self.setItem(row, col, ReadOnlyTableWidgetItem(col_data))


class BookListTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setDefaultSectionSize(24)
        self.populate_table([])

    def populate_table(self, books):
        self.books = books
        self.clear()
        self.setRowCount(len(books))
        header_labels = ['List Title', 'List Author', 'Title', 'Author', 'Series', 'Tags']
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)

        for row, book in enumerate(books):
            self.populate_table_row(row, book)

        self.resizeColumnsToContents()
        self.setMinimumColumnWidth(0, 150)
        self.setMinimumColumnWidth(1, 100)
        self.setMinimumColumnWidth(2, 150)
        self.setMinimumColumnWidth(3, 100)
        self.setMinimumColumnWidth(4, 100)
        self.setMinimumColumnWidth(5, 100)

    def setMinimumColumnWidth(self, col, minimum):
        if self.columnWidth(col) < minimum:
            self.setColumnWidth(col, minimum)

    def populate_table_row(self, row, book):
        status = book['status']
        icon_name = 'ok.png'
        tooltip = 'A matching book was found in your calibre library'
        color = None
        if status == 'multiple':
            icon_name = 'edit_input.png'
            tooltip = 'Multiple matches found for this title/author.\n' \
                      'Resolve this by selecting your match below.'
            color = Qt.blue
        elif status == 'unmatched':
            icon_name = 'list_remove.png'
            tooltip = 'No matching book found in your library.\n' \
                      'Add an empty book or search for a match below.'
            color = Qt.red
        elif status == 'empty':
            icon_name = 'add_book.png'
            tooltip = 'An empty book will be added if you save this list'
        elif status == 'added':
            icon_name = 'plus.png'
            tooltip = 'This book was added to your list manually'
        list_title_item = TextIconWidgetItem(book['title'], get_icon(icon_name), tooltip=tooltip, is_read_only=True)
        list_author_item = ReadOnlyTableWidgetItem(book['author'])
        calibre_title_item = ReadOnlyTableWidgetItem(book['calibre_title'])
        if color is not None:
            list_title_item.setForeground(color)
            list_author_item.setForeground(color)
            calibre_title_item.setForeground(color)

        self.setItem(row, 0, list_title_item)
        self.setItem(row, 1, list_author_item)
        self.setItem(row, 2, calibre_title_item)
        self.setItem(row, 3, ReadOnlyTableWidgetItem(book['calibre_author']))
        self.setItem(row, 4, ReadOnlyTableWidgetItem(book['calibre_series']))
        self.setItem(row, 5, ReadOnlyTableWidgetItem(book['calibre_tags']))


class SearchMatchesTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setDefaultSectionSize(24)
        #self.verticalHeader().setDefaultSectionSize(self.verticalHeader().minimumSectionSize())
        self.populate_table([])

    def populate_table(self, books):
        self.books = books
        self.clear()
        self.setRowCount(len(books))
        header_labels = ['Title', 'Author', 'Series', 'Tags']
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.horizontalHeader().setStretchLastSection(True)

        for row, book in enumerate(books):
            self.populate_table_row(row, book)

        self.resizeColumnsToContents()
        self.setMinimumColumnWidth(0, 150)
        self.setMinimumColumnWidth(1, 100)
        self.setMinimumColumnWidth(2, 100)
        self.setMinimumColumnWidth(3, 100)

    def setMinimumColumnWidth(self, col, minimum):
        if self.columnWidth(col) < minimum:
            self.setColumnWidth(col, minimum)

    def populate_table_row(self, row, book):
        self.setItem(row, 0, ReadOnlyTableWidgetItem(book['calibre_title']))
        self.setItem(row, 1, ReadOnlyTableWidgetItem(book['calibre_author']))
        self.setItem(row, 2, ReadOnlyTableWidgetItem(book['calibre_series']))
        self.setItem(row, 3, ReadOnlyTableWidgetItem(book['calibre_tags']))


class StrippedTextEdit(QTextEdit):
    '''
    Override the pasting of data to strip leading and trailing spaces off every line
    '''

    def __init__(self, parent):
        QTextEdit.__init__(self, parent)
        self.setLineWrapMode(QTextEdit.NoWrap)

    def insertFromMimeData(self, source):
        if not source.hasText():
            return
        lines = unicode(source.text()).split('\n')
        new_lines = []
        for line in lines:
            ln = line.strip()
            if ln:
                new_lines.append(ln)
        txt = '\n'.join(new_lines)
        cursor = self.textCursor()
        cursor.insertText(txt)


class ImportClipboardTab(QWidget):

    def __init__(self, parent_dialog):
        self.parent_dialog = parent_dialog
        QWidget.__init__(self)
        self.block_events=False

        l = QGridLayout()
        self.setLayout(l)

        paste_lbl = QLabel('&Paste your book list here:')
        paste_lbl.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        l.addWidget(paste_lbl, 0, 0, 1, 1)
        self.paste_button = QPushButton(get_icon('edit-paste.png'), '&Paste', self)
        self.paste_button.setToolTip('Replace all text above with the contents of your clipboard')
        self.paste_button.clicked.connect(self._paste_text)
        l.addWidget(self.paste_button, 0, 1, 1, 1)

        self.clip_textedit = StrippedTextEdit(self)
        self.clip_textedit.setLineWrapMode(QTextEdit.NoWrap)
        paste_lbl.setBuddy(self.clip_textedit)
        l.addWidget(self.clip_textedit, 1, 0, 1, 2)
        l.setColumnStretch(0,1)
        l.setRowStretch(1,1)

        gb = QGroupBox(' Conversion expression: ', self)
        l.addWidget(gb, 2, 0, 1, 2)

        gbl = QVBoxLayout()
        gb.setLayout(gbl)
        re_lbl = QLabel('Set a <a href="http://manual.calibre-ebook.com/regexp.html">regular expression</a> to use for titles and/or authors.<br/>'
                        'The group names are (?P&lt;title&gt;) and (?P&lt;author&gt;).', self)
        gbl.addWidget(re_lbl)

        rel = QHBoxLayout()
        gbl.addLayout(rel)

        self.pat_combo = QComboBox(self)
        self.pat_combo.setEditable(True)
        self.pat_combo.setMaxCount(25)
        self.pat_combo.setInsertPolicy(QComboBox.InsertAtTop)
        rel.addWidget(self.pat_combo, 1)

        self.standard_pat_button = QToolButton(self)
        self.standard_pat_button.setToolTip('Choose a predefined named pattern')
        self.standard_pat_button.setMenu(self._create_standard_pat_menu())
        self.standard_pat_button.setIcon(get_icon('images/script.png'))
        self.standard_pat_button.setPopupMode(QToolButton.InstantPopup)
        rel.addWidget(self.standard_pat_button)

        self.clear_pat_button = QToolButton(self)
        self.clear_pat_button.setToolTip('Clear the regular expression')
        self.clear_pat_button.setIcon(get_icon('trash.png'))
        self.clear_pat_button.clicked.connect(self._clear_pattern)
        rel.addWidget(self.clear_pat_button)

        self.count_label = QLabel('', self)
        #self.count_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        l.addWidget(self.count_label, 4, 0, 1, 1)

        self.preview_button = QPushButton(get_icon('wizard.png'), '&Preview', self)
        self.preview_button.setToolTip('Preview the results of applying this expression in the grid on the right')
        self.preview_button.clicked.connect(partial(self._preview_rows, update_combo=True))
        l.addWidget(self.preview_button, 4, 1, 1, 1)

        # Setup some data for UI testing purposes
        self.clip_textedit.setPlainText(TEST_BOOKS_TEXT)

        # Wire up our signals at the end to prevent premature raising
        self.pat_combo.currentIndexChanged.connect(partial(self._preview_rows, update_combo=False))
        self.clip_textedit.textChanged.connect(partial(self._preview_rows, update_combo=False))

    def _paste_text(self):
        self.clip_textedit.clear()
        self.clip_textedit.paste()

    def _create_standard_pat_menu(self):
        menu = QMenu(self)
        for name, regex in DEFAULT_CLIP_PATTERNS:
            action = menu.addAction(name)
            action.triggered.connect(partial(self._assign_standard_pattern, regex))
        return menu

    def _assign_standard_pattern(self, regex):
        self.pat_combo.setEditText(regex)
        self._preview_rows(update_combo=True)

    def _preview_rows(self, update_combo=False):
        if self.block_events:
            return
        expression = unicode(self.pat_combo.currentText())
        regex = None
        if expression:
            regex = re.compile(expression, re.UNICODE)
            if update_combo:
                # Update our combo dropdown history if needed
                existing_index = self.pat_combo.findText(expression, Qt.MatchExactly)
                if existing_index:
                    self.block_events = True
                    self.pat_combo.removeItem(existing_index)
                    self.pat_combo.insertItem(0, expression)
                    self.pat_combo.setCurrentIndex(0)
                    self.block_events = False

        books = []
        text = unicode(self.clip_textedit.toPlainText())
        lines = text.split('\n')
        num_lines = 0
        for line in lines:
            if len(line) == 0:
                continue
            num_lines += 1
            title = line
            author = ''
            if regex is not None:
                m = regex.match(line)
                if m is not None:
                    if 'title' in m.groupdict():
                        title = m.group('title').strip()
                    if 'author' in m.groupdict():
                        author = m.group('author').strip()
                        # Attempt to cleanup the author in case multiple authors
                        split_char = ''
                        if ';' in author:
                            split_char = ';'
                        elif '&' in author:
                            split_char = '&'
                        if split_char:
                            authors = [a.strip() for a in author.split(split_char)]
                            author = ' & '.join(authors)
            books.append({'title':title, 'author':author})

        self.count_label.setText('%d books found for list'%(num_lines,))
        self.parent_dialog.refresh_preview_books(books)

    def _clear_pattern(self):
        self.pat_combo.clearEditText()
        self.pat_combo.setCurrentIndex(-1)
        self._preview_rows()

    def restore_settings(self, settings):
        self.block_events = True
        clipboard_regexes = settings.get('clipboard_regexes', [])
        self.pat_combo.clear()
        for regex in clipboard_regexes:
            self.pat_combo.addItem(regex)
        self.block_events = False

    def save_settings(self, settings):
        clipboard_regexes = [unicode(self.pat_combo.itemText(i)).strip()
                             for i in range(0, self.pat_combo.count())]
        settings['clipboard_regexes'] = clipboard_regexes


class ImportCSVTab(QWidget):

    def __init__(self, parent_dialog):
        self.parent_dialog = parent_dialog
        QWidget.__init__(self)
        self.block_events=True

        l = QGridLayout()
        self.setLayout(l)

        paste_lbl = QLabel('&Import from file:')
        paste_lbl.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.file_combo = QComboBox(self)
        self.file_combo.setEditable(True)
        self.file_combo.setMaxCount(10)
        self.file_combo.setInsertPolicy(QComboBox.InsertAtTop)
        paste_lbl.setBuddy(self.file_combo)
        l.addWidget(paste_lbl, 0, 0, 1, 1)
        cfl = QHBoxLayout()
        l.addLayout(cfl, 1, 0, 1, 2)
        cfl.addWidget(self.file_combo, 1)
        self.choose_file_button = QToolButton(self)
        self.choose_file_button.setToolTip('Choose the file to import')
        self.choose_file_button.setIcon(get_icon('document_open.png'))
        self.choose_file_button.clicked.connect(self._choose_file)
        cfl.addWidget(self.choose_file_button)

        contents_lbl = QLabel('&Contents:', self)
        l.addWidget(contents_lbl, 2, 0, 1, 2)

        self.content = CSVRowsTableWidget(self)
        contents_lbl.setBuddy(self.content)
        l.addWidget(self.content, 3, 0, 1, 2)
        l.setColumnStretch(0,1)
        l.setRowStretch(3,1)

        ol1 = QHBoxLayout()
        l.addLayout(ol1, 4, 0, 1, 2)

        dgb = QGroupBox(' &Delimiter: ', self)
        ol1.addWidget(dgb)
        dl = QGridLayout()
        dgb.setLayout(dl)
        self.delimiter_tab_opt = QRadioButton('&Tab', self)
        self.delimiter_other_opt = QRadioButton('&Other:', self)
        self.delimiter_other_ledit = QLineEdit(self)
        self.delimiter_other_ledit.setFixedWidth(30)
        self.delimiter_other_opt.setChecked(True)
        dl.addWidget(self.delimiter_tab_opt, 0, 0, 1, 1)
        dl.addWidget(self.delimiter_other_opt, 1, 0, 1, 1)
        dl.addWidget(self.delimiter_other_ledit, 1, 1, 1, 1)
        dl.setRowStretch(2, 1)

        cgb = QGroupBox(' &Columns: ', self)
        ol1.addWidget(cgb)
        cl = QGridLayout()
        cgb.setLayout(cl)
        col_title_label = QLabel('&Title no:', self)
        col_title_label.setToolTip('Specify the column number for the book title')
        col_author_label = QLabel('&Author no:', self)
        col_author_label.setToolTip('Specify the column number for the book author')
        self.title_col_spin = QSpinBox(self)
        self.title_col_spin.setMinimum(1)
        self.author_col_spin = QSpinBox(self)
        self.author_col_spin.setMinimum(1)
        col_title_label.setBuddy(self.title_col_spin)
        col_author_label.setBuddy(self.author_col_spin)
        cl.addWidget(col_title_label, 0, 0, 1, 1)
        cl.addWidget(self.title_col_spin, 0, 1, 1, 1)
        cl.addWidget(col_author_label, 1, 0, 1, 1)
        cl.addWidget(self.author_col_spin, 1, 1, 1, 1)
        cl.setRowStretch(2, 1)

        pgb = QGroupBox(' Processing: ', self)
        ol1.addWidget(pgb, 1)
        pl = QGridLayout()
        pgb.setLayout(pl)
        self.skip_first_row_chk = QCheckBox('S&kip first row', self)
        self.skip_first_row_chk.setToolTip('Select this option to ignore the first row of column headings')
        self.unquote_chk = QCheckBox('&Unquote', self)
        self.unquote_chk.setToolTip('Remove any quotes around columns of data')
        pl.addWidget(self.skip_first_row_chk, 0, 0, 1, 1)
        pl.addWidget(self.unquote_chk, 1, 0, 1, 1)
        pl.setColumnStretch(1, 1)

        self.count_label = QLabel('', self)
        l.addWidget(self.count_label, 5, 0, 1, 1)

        self.preview_button = QPushButton(get_icon('wizard.png'), '&Preview', self)
        self.preview_button.setToolTip('Preview the results of applying these values in the grid on the right')
        self.preview_button.clicked.connect(partial(self._preview_rows, update_combo=True))
        l.addWidget(self.preview_button, 5, 1, 1, 1)

        self.file_combo.currentIndexChanged.connect(partial(self._preview_rows, update_combo=False))
        self.block_events=False

    def _choose_file(self):
        files = choose_files(None, 'CSV file dialog', 'Select a CSV file to import',
                             all_files=True, select_only_single_file=True)
        if not files:
            return
        csv_file = files[0]
        if iswindows:
            csv_file = os.path.normpath(csv_file)

        self.block_events = True
        existing_index = self.file_combo.findText(csv_file, Qt.MatchExactly)
        if existing_index >= 0:
            self.file_combo.setCurrentIndex(existing_index)
        else:
            self.file_combo.insertItem(0, csv_file)
            self.file_combo.setCurrentIndex(0)
        self.block_events = False
        self._preview_rows()

    def _open_file(self):
        csv_file = unicode(self.file_combo.currentText()).strip()
        if not csv_file:
            error_dialog(self, 'File not specified', 'You have not specified a path to a CSV file',
                         show=True)
            self.file_combo.setFocus()
            return
        if not os.path.exists(csv_file):
            error_dialog(self, 'File not found', 'No file found at this location',
                         show=True)
            return
        # Update our combo dropdown history if needed
        existing_index = self.file_combo.findText(csv_file, Qt.MatchExactly)
        if existing_index:
            self.block_events = True
            self.file_combo.removeItem(existing_index)
            self.file_combo.insertItem(0, csv_file)
            self.file_combo.setCurrentIndex(0)
            self.block_events = False
        return csv_file

    def _preview_rows(self, update_combo=False):
        if self.block_events:
            return
        if self.delimiter_tab_opt.isChecked():
            delim = b'\t'
        else:
            delim = str(self.delimiter_other_ledit.text())
        if not delim:
            error_dialog(self, 'Invalid options', 'You have not specified a delimiter', show=True)
            return
        csv_file = self._open_file()
        if not csv_file:
            self.content.clear()
            self.parent_dialog.refresh_preview_books([])
            return

        skip_first_row = self.skip_first_row_chk.isChecked()
        quoting = csv.QUOTE_MINIMAL
        if not self.unquote_chk.isChecked():
            quoting = csv.QUOTE_NONE
        #strip_title = self.strip_title_chk.isChecked()

        rows = []
        with open(csv_file, 'r') as f:
            reader = unicode_csv_reader(f, delimiter=delim, quoting=quoting)
            #reader = csv.reader(f, delimiter=delim, quoting=quoting)
            for r, row in enumerate(reader):
                if r == 0 and skip_first_row:
                    continue
                rows.append(row)
        self.content.populate_table(rows)

        books = []
        if rows:
            cols = len(rows[0])
            title_col = int(unicode(self.title_col_spin.value())) - 1
            author_col = int(unicode(self.author_col_spin.value())) - 1
            for row in rows:
                title = ''
                author = ''
                if title_col < cols:
                    title = row[title_col].strip()
                    #if strip_title:
                    #    for pat, repl in self.title_patterns:
                    #        title = pat.sub(repl, title)
                if author_col < cols:
                    author = row[author_col].strip()
                books.append({'title':title, 'author':author})

        self.count_label.setText('%d books found for list'%(len(books),))
        self.parent_dialog.refresh_preview_books(books)

    def restore_settings(self, settings):
        self.block_events = True
        csv_files = settings.get('csv_files', [])
        self.file_combo.clear()
        for regex in csv_files:
            self.file_combo.addItem(regex)
        delimiter = settings.get('csv_delimiter',',')
        if delimiter == '\t':
            self.delimiter_tab_opt.setChecked(True)
        else:
            self.delimiter_other_opt.setChecked(True)
            self.delimiter_other_ledit.setText(delimiter)
        self.title_col_spin.setValue(settings.get('csv_title_col', 1))
        self.author_col_spin.setValue(settings.get('csv_author_col', 2))
        self.skip_first_row_chk.setChecked(settings.get('csv_skip_first', True))
        self.unquote_chk.setChecked(settings.get('csv_unquote', True))
        self.block_events = False

    def save_settings(self, settings):
        csv_files = [unicode(self.file_combo.itemText(i)).strip()
                     for i in range(0, self.file_combo.count())]
        settings['csv_files'] = csv_files
        if self.delimiter_tab_opt.isChecked():
            settings['csv_delimiter'] = '\t'
        else:
            settings['csv_delimiter'] = unicode(self.delimiter_other_ledit.text())
        settings['csv_title_col'] = int(unicode(self.title_col_spin.value()))
        settings['csv_author_col'] = int(unicode(self.author_col_spin.value()))
        settings['csv_skip_first'] = self.skip_first_row_chk.isChecked()
        settings['csv_unquote'] = self.unquote_chk.isChecked()


class ImportWebPageTab(QWidget):

    def __init__(self, parent_dialog):
        self.parent_dialog = parent_dialog
        QWidget.__init__(self)


class ImportPage(WizardPage):

    ID = 1

    def init_controls(self):
        self.block_events = True
        self.setTitle('Step 1: Configure a list source')
        l = QHBoxLayout(self)
        self.setLayout(l)

        self.tw = QTabWidget(self)
        l.addWidget(self.tw, 3)

        self.clipboard_tab = ImportClipboardTab(self)
        self.csv_tab = ImportCSVTab(self)
        self.web_page_tab = ImportWebPageTab(self)
        self.tw.addTab(self.clipboard_tab, 'Clipboard')
        self.tw.addTab(self.csv_tab, 'CSV File')
        self.tw.addTab(self.web_page_tab, 'Web Page')

        l.addSpacing(5)
        self.preview_table = PreviewBookTableWidget(self)
        l.addWidget(self.preview_table, 2)
        self.block_events = False

    def refresh_preview_books(self, books):
        if not self.block_events:
            self.info['books'] = books
            self.preview_table.populate_table(books)
        self.completeChanged.emit()

    def isComplete(self):
        '''
        Don't allow the user onto the next wizard page without any rows of data
        or with a row that has no title
        '''
        books = self.info['books']
        if not books:
            return False
        for book in books:
            if book['title'] == '':
                return False
        return True

    def initializePage(self):
        self.clipboard_tab.restore_settings(self.info['settings'])
        self.csv_tab.restore_settings(self.info['settings'])
        self.tw.setCurrentIndex(self.info['settings'].get('last_tab', 0))

    def validatePage(self):
        self.clipboard_tab.save_settings(self.info['settings'])
        self.csv_tab.save_settings(self.info['settings'])
        self.info['settings']['last_tab'] = self.tw.currentIndex()
        return True


class ResolvePage(WizardPage):

    ID = 2

    def init_controls(self):
        self.block_events = True
        self.setTitle('Step 2: Match list of books against your library')
        l = QVBoxLayout(self)
        self.setLayout(l)

        self.list_gb = QGroupBox('List of books:', self)
        self.list_gb.setStyleSheet('QGroupBox { font-weight: bold; }')
        l.addWidget(self.list_gb, 3)
        gbl = QVBoxLayout()
        self.list_gb.setLayout(gbl)

        bll = QGridLayout()
        gbl.addLayout(bll)
        self.book_list_table = BookListTableWidget(self)
        bll.addWidget(self.book_list_table, 0, 0, 1, 1)
        bll.setColumnStretch(0, 1)

        btnl = QVBoxLayout()
        bll.addLayout(btnl, 0, 1, 1, 1)
        self.clear_match_button = QToolButton(self)
        self.clear_match_button.setIcon(get_icon('list_remove.png'))
        self.clear_match_button.setToolTip('Clear the match associated with this book in the list')
        self.clear_match_button.clicked.connect(self._clear_match)
        self.remove_book_button = QToolButton(self)
        self.remove_book_button.setIcon(get_icon('minus.png'))
        self.remove_book_button.setToolTip('Remove this book from the list')
        self.remove_book_button.clicked.connect(self._remove_book)
        self.empty_book_button = QToolButton(self)
        self.empty_book_button.setIcon(get_icon('add_book.png'))
        self.empty_book_button.setToolTip('Create an empty book to match this book in the list')
        self.empty_book_button.clicked.connect(self._match_empty_book)
        btnl.addWidget(self.clear_match_button)
        btnl.addWidget(self.empty_book_button)
        btnl.addWidget(self.remove_book_button)
        btnl.addStretch(1)

        l.addSpacing(5)
        gb = QGroupBox('Possible matches for selected book:', self)
        gb.setStyleSheet('QGroupBox { font-weight: bold; }')
        l.addWidget(gb, 2)
        gl = QVBoxLayout()
        gb.setLayout(gl)

        sl = QHBoxLayout()
        gl.addLayout(sl)
        search_label = QLabel('Search:', self)
        self.search_ledit = QLineEdit(self)
        self.go_button = QPushButton(_('&Go!'), self)
        self.go_button.clicked.connect(partial(self._on_search_click))
        self.clear_button = QToolButton(self)
        self.clear_button.setIcon(get_icon('clear_left.png'))
        self.clear_button.clicked.connect(partial(self._on_clear_search_text))
        sl.addWidget(search_label)
        sl.addWidget(self.search_ledit, 1)
        sl.addWidget(self.go_button)
        sl.addWidget(self.clear_button)

        bll2 = QHBoxLayout()
        gl.addLayout(bll2)
        self.search_matches_table = SearchMatchesTableWidget(self)
        bll2.addWidget(self.search_matches_table, 1)

        btn2 = QVBoxLayout()
        bll2.addLayout(btn2)
        btn2.addStretch(1)
        self.select_book_button = QToolButton(self)
        self.select_book_button.setIcon(get_icon('ok.png'))
        self.select_book_button.setToolTip('Select this book as the match fot this list title')
        self.select_book_button.clicked.connect(self._on_search_matches_select)
        self.next_unmatched_button = QToolButton(self)
        self.next_unmatched_button.setIcon(get_icon('forward.png'))
        self.next_unmatched_button.setToolTip('Move to the next unmatched book on the list')
        self.next_unmatched_button.clicked.connect(self._select_next_unmatched)
        self.previous_unmatched_button = QToolButton(self)
        self.previous_unmatched_button.setIcon(get_icon('back.png'))
        self.previous_unmatched_button.setToolTip('Move to the previous unmatched book on the list')
        self.previous_unmatched_button.clicked.connect(self._select_previous_unmatched)
        self.append_book_button = QToolButton(self)
        self.append_book_button.setIcon(get_icon('plus.png'))
        self.append_book_button.setToolTip('Append this book as a new item on the list')
        self.append_book_button.clicked.connect(self._append_book)
        btn2.addWidget(self.select_book_button)
        btn2.addWidget(self.next_unmatched_button)
        btn2.addWidget(self.previous_unmatched_button)
        btn2.addWidget(self.append_book_button)

        self.book_list_table.selectionModel().currentChanged.connect(self._on_book_list_selection_changed)
        self.book_list_table.doubleClicked.connect(self._on_book_list_double_clicked)
        self.search_matches_table.doubleClicked.connect(self._on_search_matches_double_clicked)

        self.prev_idx = self.next_idx = -1
        self.block_events = False
        self._create_context_menu()

    def initializePage(self):
        if not self.worker.isFinished():
            self.worker.wait()

        books = copy.deepcopy(self.info['books'])
        # Our books dict will only have the title and author from the first page
        # of the wizard. We want to attempt to match each book against your
        # calibre library.
        for book in books:
            self._apply_best_calibre_book_match(book)
        self.book_list_table.populate_table(books)
        self.book_list_table.selectRow(0)
        self._update_book_counts()

    def _create_context_menu(self):
        table = self.book_list_table
        table.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.clear_match_action = QAction(get_icon('list_remove.png'), '&Clear match', table)
        self.clear_match_action.triggered.connect(self._clear_match)
        self.remove_book_action = QAction(get_icon('minus.png'), '&Remove book', table)
        self.remove_book_action.triggered.connect(self._remove_book)
        sep1 = QAction(table)
        sep1.setSeparator(True)
        self.empty_book_action = QAction(get_icon('add_book.png'), '&Match empty book', table)
        self.empty_book_action.triggered.connect(self._match_empty_book)
        sep4 = QAction(table)
        sep4.setSeparator(True)
        self.search_title_author_action = QAction(get_icon('search.png'), '&Search for title/author', table)
        self.search_title_author_action.triggered.connect(partial(self._force_search_book, True, True))
        self.search_title_action = QAction(get_icon('search.png'), '&Search for title', table)
        self.search_title_action.triggered.connect(partial(self._force_search_book, True, False))
        self.search_author_action = QAction(get_icon('search.png'), '&Search for author', table)
        self.search_author_action.triggered.connect(partial(self._force_search_book, False, True))
        table.addAction(self.clear_match_action)
        table.addAction(self.empty_book_action)
        table.addAction(sep1)
        table.addAction(self.remove_book_action)
        table.addAction(sep4)
        table.addAction(self.search_title_author_action)
        table.addAction(self.search_title_action)
        table.addAction(self.search_author_action)

        table = self.search_matches_table
        table.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.select_book_action = QAction(get_icon('ok.png'), '&Select Book', table)
        self.select_book_action.triggered.connect(self._on_search_matches_select)
        sep2 = QAction(table)
        sep2.setSeparator(True)
        self.previous_unmatched_action = QAction(get_icon('back.png'), '&Previous unmatched', table)
        self.previous_unmatched_action.triggered.connect(self._select_previous_unmatched)
        self.next_unmatched_action = QAction(get_icon('forward.png'), '&Next unmatched', table)
        self.next_unmatched_action.triggered.connect(self._select_next_unmatched)
        sep3 = QAction(table)
        sep3.setSeparator(True)
        self.append_book_action = QAction(get_icon('plus.png'), '&Append to list', table)
        self.append_book_action.triggered.connect(self._append_book)
        
        table.addAction(self.select_book_action)
        table.addAction(sep2)
        table.addAction(self.next_unmatched_action)
        table.addAction(self.previous_unmatched_action)
        table.addAction(sep3)
        table.addAction(self.append_book_action)

    def _clear_match(self):
        row = self.book_list_table.currentRow()
        book = self.book_list_table.books[row]
        book['status'] = 'unmatched'
        book['id'] = ''
        book['calibre_title'] = '*** No Match ***'
        book['calibre_author'] = ''
        book['calibre_series'] = ''
        book['calibre_tags'] = ''
        self.book_list_table.populate_table_row(row, book)
        self.book_list_table.selectRow(row)
        self._update_book_counts()

    def _remove_book(self):
        message = '<p>Are you sure you want to remove the selected book from the list?</p>'
        if not confirm(message,'reading_list_import_delete_from_list', self):
            return
        row = self.book_list_table.currentRow()
        self.book_list_table.removeRow(row)
        self.book_list_table.books.pop(row)
        cnt = self.book_list_table.rowCount()
        if row == cnt:
            row = cnt - 1
        if cnt == 0:
            row = -1
        self.book_list_table.selectRow(row)
        self._update_book_counts()

    def _match_empty_book(self):
        row = self.book_list_table.currentRow()
        book = self.book_list_table.books[row]
        book['status'] = 'empty'
        book['id'] = ''
        book['calibre_title'] = book['title']
        book['calibre_author'] = book['author']
        book['calibre_series'] = ''
        book['calibre_tags'] = ''
        self.book_list_table.populate_table_row(row, book)
        self.book_list_table.selectRow(row)
        self._update_book_counts()

    def _append_book(self):
        message = '<p>Are you sure you want to add the selected book to the list?</p>'
        if not confirm(message,'reading_list_import_append_to_list', self):
            return
        match_book = self.search_matches_table.books[self.search_matches_table.currentRow()]
        book = copy.deepcopy(match_book)
        book['id'] = -1
        book['status'] = 'added'
        book['title'] = ''
        book['author'] = ''
        # Going to assume we will insert just after the currently selected row.
        row = self.book_list_table.currentRow() + 1
        self.book_list_table.books.insert(row, book)
        self.book_list_table.insertRow(row)
        self.book_list_table.populate_table_row(row, book)
        self._update_book_counts()
    
    def _force_search_book(self, include_title, include_author):
        book = self.book_list_table.books[self.book_list_table.currentRow()]
        self._on_clear_search_text()
        self._prepare_search_text(book, include_title, include_author)
        self._on_search_click()

    def _apply_best_calibre_book_match(self, book):
        title = book['title']
        author = book['author']

        def get_hashes_for_algorithm(title_alg, author_alg, title, author):
            thash = ''
            ahash = ''
            rev_ahash = ''
            title_fn = get_title_algorithm_fn(title_alg)
            if title_fn is not None:
                thash = title_fn(title)
            author_fn = get_author_algorithm_fn(author_alg)
            if author_fn is not None:
                ahash, rev_ahash = author_fn(author)

            ta_hash = thash + ahash
            rev_ta_hash = None
            if rev_ahash is not None and rev_ahash != ahash:
                rev_ta_hash = thash + rev_ahash
            return ta_hash, rev_ta_hash

        # Determine a progression of which (title, author) algorithms to try
        algs = CACHED_ALGORITHMS
        if not author:
            # Rather than the full set just run the subset that only use title
            algs = [(ta, '') for (ta, aa) in CACHED_ALGORITHMS if aa == '']

        book['status'] = 'unmatched'
        book['id'] = ''
        book['calibre_title'] = '*** No Match ***'
        book['calibre_author'] = ''
        book['calibre_series'] = ''
        book['calibre_tags'] = ''

        #print('HASH MAPS:', self.info['hash_maps'])
        for title_alg, author_alg in algs:
            alg_hash, rev_alg_hash = get_hashes_for_algorithm(title_alg, author_alg, title, author)
            #print('Alg_hash', alg_hash, 'Rev alg hash', rev_alg_hash)
            hash_map = self.info['hash_maps'][(title_alg, author_alg)]
            #print('Hash Map=', hash_map)
            matching_book_ids = []
            #print(title, author, 'alg_hash:"%s"'%alg_hash)
            if alg_hash in hash_map:
                matching_book_ids = hash_map[alg_hash]
            if rev_alg_hash is not None and rev_alg_hash in hash_map:
                matching_book_ids = hash_map[rev_alg_hash]
            if len(matching_book_ids) == 1:
                book['status'] = 'matched'
                book['id'] = iter(matching_book_ids).next()
                self._populate_calibre_info_for_book(book)
                break
            elif len(matching_book_ids) > 1:
                book['status'] = 'multiple'
                book['id'] = matching_book_ids
                book['calibre_title'] = '*** Multiple Matches ***'
                break

    def _populate_calibre_info_for_book(self, book):
        book_id = book['id']
        book['calibre_title'] = self.db.title(book_id, index_is_id=True)
        book['calibre_author_sort'] = self.db.author_sort_from_book(book_id, index_is_id=True)
        book['calibre_author'] = ' & '.join(authors_to_list(self.db, book_id))
        series = self.db.series(book_id, index_is_id=True)
        if series is not None:
            series_index = self.db.series_index(book_id, index_is_id=True)
            book['calibre_series'] = '%s [%s]'%(series, fmt_sidx(series_index))
        else:
            book['calibre_series'] = ''
        tags = self.db.tags(book_id, index_is_id=True)
        if tags is not None:
            book['calibre_tags'] = tags.replace(',',', ')
        else:
            book['calibre_tags'] = ''

    def _on_book_list_selection_changed(self, row, old_row):
        if self.block_events:
            return
        book = self.book_list_table.books[row.row()]
        self.search_ledit.setText('')
        self._clear_match_list()

        book_status = book['status']
        if book_status == 'multiple':
            self.search_ledit.setPlaceholderText('Displaying all similar matches for this book')
            self._display_multiple_matches(book['id'])
        else:
            self._on_clear_search_text()
            self._prepare_search_text(book)
        self._update_book_list_buttons()
    
    def _update_book_list_buttons(self):
        self.previous_unmatched_button.setEnabled(self.prev_idx != -1)
        is_row_selected = self.book_list_table.currentRow() != -1
        book_status = ''
        book = None
        if is_row_selected:
            book = self.book_list_table.books[self.book_list_table.currentRow()]
            book_status = book['status']
        self.clear_match_button.setEnabled(book_status in ['matched','empty'])
        self.clear_match_action.setEnabled(is_row_selected and self.clear_match_button.isEnabled())
        self.remove_book_button.setEnabled(self.book_list_table.rowCount() > 0)
        self.remove_book_action.setEnabled(is_row_selected and self.remove_book_button.isEnabled())
        self.empty_book_button.setEnabled(book_status in ['unmatched','multiple'])
        self.empty_book_action.setEnabled(is_row_selected and self.empty_book_button.isEnabled())
        self.search_title_action.setEnabled(is_row_selected)
        self.search_author_action.setEnabled(is_row_selected)

    def _on_book_list_double_clicked(self, row):
        book = self.book_list_table.books[row.row()]
        if book['status'] == 'unmatched' or book['status'] == 'matched':
            self._on_search_click()

    def _on_clear_search_text(self):
        self.search_ledit.setPlaceholderText('Search for a book in your library')
        self.search_ledit.clear()

    def _prepare_search_text(self, book, include_title=True, include_author=True):
        query = ''
        if include_title:
            title = book['title']
            query = ' '.join(get_title_tokens(title, strip_subtitle=False))
        if include_author:
            author = book['author']
            if author:
                author = author.partition('&')[0].strip()
            author_tokens = [t for t in get_author_tokens(author) if len(t) > 1]
            query += ' ' +  ' '.join(author_tokens)
        query = query.replace('  ', ' ')
        self.search_ledit.setText(query.strip())
        self.go_button.setAutoDefault(True)
        self.go_button.setDefault(True)

    def _on_search_click(self):
        query = unicode(self.search_ledit.text())
        QApplication.setOverrideCursor(Qt.WaitCursor)
        matches = self.db.search_getting_ids(query.strip(), None)
        QApplication.restoreOverrideCursor()
        #print('Matches:', matches)
        self._display_multiple_matches(matches)

    def _on_search_matches_select(self):
        self._on_search_matches_double_clicked(self.search_matches_table.currentIndex())

    def _on_search_matches_double_clicked(self, row):
        match_book = self.search_matches_table.books[row.row()]
        list_row = self.book_list_table.currentRow()
        book = self.book_list_table.books[list_row]
        for k in six.iterkeys(match_book):
            book[k] = match_book[k]
        if book['status'] in ['unmatched', 'multiple']: 
            book['status'] = 'matched'
        self.book_list_table.populate_table_row(list_row, book)
        self._update_book_counts()
        self._clear_match_list()

    def _display_multiple_matches(self, book_ids):
        match_books = {}
        for book_id in book_ids:
            match_book = { 'id': book_id }
            self._populate_calibre_info_for_book(match_book)
            match_books[book_id] = match_book
        # Sort by title and author
        skeys = sorted(list(match_books.keys(),
                            key=lambda ckey: '%s%s' % (match_books[ckey]['calibre_title'],
                                      match_books[ckey]['calibre_author_sort'])))
        sorted_books = [match_books[key] for key in skeys]
        self.search_matches_table.populate_table(sorted_books)
        if sorted_books:
            self.search_matches_table.selectRow(0)
        self._update_match_buttons()

    def _clear_match_list(self):
        self.search_matches_table.populate_table([])
        self._update_match_buttons()

    def _update_match_buttons(self):
        books = self.book_list_table.books
        have_books = len(self.search_matches_table.books) > 0
        is_row_selected = self.search_matches_table.currentRow() != -1
        self.select_book_button.setEnabled(have_books)
        self.select_book_action.setEnabled(is_row_selected and have_books)
        self.append_book_button.setEnabled(have_books)
        self.append_book_action.setEnabled(is_row_selected and have_books)

        self.prev_idx = self.next_idx = -1
        if len(books) > 0:
            sel_idx = self.book_list_table.currentRow()
            if sel_idx > 0:
                for i in reversed(range(0, sel_idx)):
                    status = books[i]['status']
                    if status == 'unmatched' or status == 'multiple':
                        self.prev_idx = i
                        break
            if sel_idx < len(books) - 1:
                for i in range(sel_idx + 1, len(books)):
                    status = books[i]['status']
                    if status == 'unmatched' or status == 'multiple':
                        self.next_idx = i
                        break

        self.previous_unmatched_button.setEnabled(self.prev_idx != -1)
        self.previous_unmatched_action.setEnabled(is_row_selected and self.prev_idx != -1)
        self.next_unmatched_button.setEnabled(self.next_idx != -1)
        self.next_unmatched_action.setEnabled(is_row_selected and self.next_idx != -1)

    def _select_previous_unmatched(self):
        self.book_list_table.selectRow(self.prev_idx)
        # Treat this the same as a double click on the book in the top list
        self._on_book_list_double_clicked(self.book_list_table.currentIndex())

    def _select_next_unmatched(self):
        self.book_list_table.selectRow(self.next_idx)
        # Treat this the same as a double click on the book in the top list
        self._on_book_list_double_clicked(self.book_list_table.currentIndex())
        
    def _update_book_counts(self):
        matches_cnt = 0
        total = len(self.book_list_table.books)
        for book in self.book_list_table.books:
            if book['status'] != 'unmatched':
                matches_cnt += 1
        if total == 0:
            self.list_gb.setTitle('List of books:')
        elif total == 1 and matches_cnt == 1:
            self.list_gb.setTitle('List of books: (1 match)')
        else:
            self.list_gb.setTitle('List of books: (%d of %d matches)'%(matches_cnt, total))


class PersistPage(WizardPage):

    ID = 3

    def init_controls(self):
        self.setTitle('Step 3: Save your imported list / configuration')
        l = QVBoxLayout(self)
        self.setLayout(l)

        rlgb = QGroupBox('Reading List plugin:', self)
        l.addWidget(rlgb)
        rlgbl = QGridLayout()
        rlgb.setLayout(rlgbl)
        rl_lbl = QLabel('If you have the <a href="http://www.mobileread.com/forums/showthread.php?t=134856">Reading list</a> plugin installed '
                        'then you can store the imported books into a new or existing list for that plugin. This will allow you to '
                        'view the list at a later time without having to import it again, or send the books on this list to '
                        'a device when it is connected.', self)
        rl_lbl.setWordWrap(True)
        self.rl_ignore_opt = QRadioButton('&Do not save list contents', self)
        self.rl_ignore_opt.setChecked(True)
        self.rl_create_opt = QRadioButton('Create a &new reading list:', self)
        self.rl_update_opt = QRadioButton('&Update an existing reading list:', self)
        self.rl_clear_chk = QCheckBox('C&lear reading list before adding', self)
        self.rl_create_ledit = QLineEdit('', self)
        self.rl_update_combo = QComboBox(self)
        self.rl_update_combo.setMinimumWidth(150)
        rlgbl.addWidget(rl_lbl, 0, 0, 1, 4)
        rlgbl.addWidget(self.rl_ignore_opt, 1, 0, 1, 2)
        rlgbl.addWidget(self.rl_create_opt, 2, 0, 1, 2)
        rlgbl.addWidget(self.rl_create_ledit, 2, 2, 1, 1)
        rlgbl.addWidget(self.rl_update_opt, 3, 0, 1, 2)
        rlgbl.addWidget(self.rl_update_combo, 3, 2, 1, 1)
        rlgbl.addWidget(self.rl_clear_chk, 4, 1, 1, 1)
        rlgbl.setColumnMinimumWidth(0, 16)
        rlgbl.setColumnStretch(3, 1)

        l.addSpacing(10)

        sgb = QGroupBox('Save import configuration:', self)
        l.addWidget(sgb)
        sgbl = QGridLayout()
        sgb.setLayout(sgbl)
        settings_lbl = QLabel('You can choose to store the current import settings, if you intend to import from this source again in future.', self)
        settings_lbl.setWordWrap(True)
        self.settings_dont_save_opt = QRadioButton('&Do not save the current import settings', self)
        self.settings_dont_save_opt.setChecked(True)
        self.settings_save_opt = QRadioButton('&Save these import settings as:', self)
        self.save_combo = QComboBox(self)
        self.save_combo.setMinimumWidth(150)
        sgbl.addWidget(settings_lbl, 0, 0, 1, 4)
        sgbl.addWidget(self.settings_dont_save_opt, 1, 0, 1, 1)
        sgbl.addWidget(self.settings_save_opt, 2, 0, 1, 1)
        sgbl.addWidget(self.save_combo, 2, 1, 1, 1)
        sgbl.setColumnStretch(3, 1)

        l.addStretch(1)


class LoadHashMapsWorker(QThread):
    '''
    Worker thread to populate our hash maps, done on a background thread
    to keep the initial dialog display responsive
    '''
    done  = pyqtSignal(object)

    def __init__(self, parent, db):
        QThread.__init__(self, parent)
        self.db = db
        self.canceled = False

    def run(self):
        try:
            builder = LibraryHashBuilder(self.db)
        except Exception as err:
            import traceback
            traceback.print_exc()
            msg = as_unicode(err)
            self.done.emit(msg)
        else:
            if not self.canceled:
                self.done.emit(builder.hash_maps)


class ImportListWizard(QWizard):

    def __init__(self, db, parent=None):
        QWizard.__init__(self, parent)
        self.setModal(True)
        self.setWindowTitle('Import Book List')
        self.setWindowIcon(get_icon('wizard.png'))
        self.setMinimumSize(600, 0)
        self.setOption(QWizard.NoDefaultButton)

        self.info = { 'books': [] }
        self.db = db

        self.worker = LoadHashMapsWorker(self, db)
        self.worker.done.connect(self._on_caches_loaded, type=Qt.QueuedConnection)
        self.worker.start()

        for attr, cls in [
                ('import_page',  ImportPage),
                ('resolve_page', ResolvePage),
                ('persist_page', PersistPage)
                ]:
            setattr(self, attr, cls(db, self))
            self.setPage(getattr(cls, 'ID'), getattr(self, attr))

        self.unique_pref_name = 'reading list plugin:import list wizard'
        geom = gprefs.get(self.unique_pref_name, None)
        if geom is None:
            self.resize(self.sizeHint())
        else:
            self.restoreGeometry(geom)
        self.info['settings'] = gprefs.get(self.unique_pref_name+':settings', {})
        self.finished.connect(self._on_dialog_closing)

    def _on_dialog_closing(self, result):
        # Hack - bug in QT with AeroStyle, dialog changes size (on Win 7 anyways)
        if self.wizardStyle() == QWizard.AeroStyle:
            new_width = self.width() + self.frameGeometry().width() - self.geometry().width()
            border_height = self.frameGeometry().height() - self.geometry().height()
            frame_height = self.style().pixelMetric(QStyle.PM_TitleBarHeight)
            new_height = self.height() - frame_height + border_height
            self.setFixedSize(new_width, new_height)
        geom = bytearray(self.saveGeometry())
        gprefs[self.unique_pref_name] = geom
        gprefs[self.unique_pref_name+':settings'] = self.info['settings']

    def _on_caches_loaded(self, hash_maps):
        if isinstance(hash_maps, six.string_types):
            error_dialog(self.gui, _('Data error'),
                    _('The hash map of books could not be built.'),
                    det_msg=hash_maps, show=True)
            return self.canceled()
        self.info['hash_maps'] = hash_maps



# Test Wizard {{{
# calibre-debug -e wizards.py
if __name__ == '__main__':
    from calibre.library import db
    app = QApplication([])
    w = ImportListWizard(db())
    w.exec_()
# }}}
