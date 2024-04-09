#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2020, Jim Miller'
__docformat__ = 'restructuredtext en'

import logging
logger = logging.getLogger(__name__)

from functools import partial
import string
import copy
import six
from six import text_type as unicode

from PyQt5.Qt import ( QProgressDialog, QTimer )

from calibre.gui2 import question_dialog

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction
from calibre.ptempfile import PersistentTemporaryFile, PersistentTemporaryDirectory, remove_dir
from calibre.ebooks.metadata import MetaInformation, authors_to_string

from calibre.gui2.dialogs.message_box import ViewLog
from calibre_plugins.splitmergenew.common_utils import get_icon
from calibre_plugins.splitmergenew.config import prefs
from calibre_plugins.splitmergenew.dialogs import (
    LoopProgressDialog
    )

load_translations()

class SplitMergeNewPlugin(InterfaceAction):

    name = 'SplitMergeNew'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (_('SplitMergeNew'),
                   None,
                   _('Split out (new) Chapters from FFF books and merge together into one book.'),
                   ())
    # None for keyboard shortcut doesn't allow shortcut.  () does, there just isn't one yet

    action_type = 'global'
    # make button menu drop down only
    #popup_type = QToolButton.InstantPopup

    # # disable when not in library. (main,carda,cardb)
    # def location_selected(self, loc):
    #     enabled = loc == 'library'
    #     self.qaction.setEnabled(enabled)
    #     self.menuless_qaction.setEnabled(enabled)

    def genesis(self):

        # This method is called once per plugin, do initial setup here

        base = self.interface_action_base_plugin
        self.version = base.name+" v%d.%d.%d"%base.version

        # Set the icon for this interface action
        # The get_icons function is a builtin function defined for all your
        # plugin code. It loads icons from the plugin zip file. It returns
        # QIcon objects, if you want the actual data, use the analogous
        # get_resources builtin function.

        # Note that if you are loading more than one icon, for performance, you
        # should pass a list of names to get_icons. In this case, get_icons
        # will return a dictionary mapping names to QIcons. Names that
        # are not found in the zip file will result in null QIcons.
        icon = get_icon('catalog.png')

        self.qaction.setText(_('SplitMergeNew'))
        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)

        # Call function when plugin triggered.
        self.qaction.triggered.connect(self.plugin_button)

    def get_epubmerge_plugin(self):
        if 'EpubMerge' in self.gui.iactions and self.gui.iactions['EpubMerge'].interface_action_base_plugin.version >= (1,3,1):
            return self.gui.iactions['EpubMerge']

    def get_epubsplit_plugin(self):
        if 'EpubSplit' in self.gui.iactions and self.gui.iactions['EpubSplit'].interface_action_base_plugin.version >= (1,3,1):
            return self.gui.iactions['EpubSplit']

    def plugin_button(self):
        if not self.gui.current_view().selectionModel().selectedRows() :
            self.gui.status_bar.show_message(_('No Selected Books for SplitMergeNew'),
                                             3000)
            return

        if not self.is_library_view():
            # device view, get from epubs on device.
            self.gui.status_bar.show_message(_('SplitMergeNew only works in libary'),
                                             3000)
            return

        if not self.get_epubmerge_plugin():
            self.gui.status_bar.show_message(_('No EpubMerge'), 3000)
            return

        if not self.get_epubsplit_plugin():
            self.gui.status_bar.show_message(_('No EpubSplit'), 3000)
            return

        em = self.get_epubmerge_plugin()
        es = self.get_epubsplit_plugin()

        book_list = [ em._convert_id_to_book(x, good=False) for x in self.gui.library_view.get_selected_ids() ]
        # book_ids = self.gui.library_view.get_selected_ids()
        # logger.debug(book_list)

        tdir = PersistentTemporaryDirectory(prefix='splitmergenew__')
        logger.debug("tdir:%s"%tdir)

        # logger.debug(book_list)
        logger.debug("before LoopProgressDialog!")
        LoopProgressDialog(self.gui,
                           book_list,
                           partial(self._do_splitnew_loop,
                                   tdir=tdir,
                                   db=self.gui.current_db),
                           partial(self._start_splitmerge,
                                   tdir=tdir,
                                   db=self.gui.current_db),
                           init_label=_("Collecting EPUBs..."),
                           win_title=_("Get EPUBs"),
                           status_prefix=_("EPUBs collected"))

    def _do_splitnew_loop(self, book, tdir=None, db=None):
        em = self.get_epubmerge_plugin()
        es = self.get_epubsplit_plugin()
        # modifies book.
        em._populate_book_from_calibre_id(book,db)

        # logger.debug("gonna split:")
        # logger.debug(book)

        tmp = PersistentTemporaryFile(prefix='splitmergenew-%s-'%book['calibre_id'],
                                      suffix='.epub',
                                      dir=tdir)

        epubO = es.get_splitepub(book['epub'])
        lines = epubO.get_split_lines()

        book['good']=False
        count = 0
        keep_lines=[]
        # showlist=['toc','guide','anchor','id','href']
        for line in lines:
            new_chap = '(new)' in "".join(line.get('toc',[]))
            if new_chap:
                book['good']=True
            if ( new_chap ): # or
                # 'cover' in line['id'] or
                # 'title_page' in line['id']):
                # or 'log_page' in line['id'])
                keep_lines.append(count)

                ## XXX Create and include a title page, or a
                ## title-author only epub or something?  Lengthy title
                ## page is a pain if doing TTS.

                ## Also grab the previous chapter if new.
                # if ( new_chap and
                #      count-1 not in keep_lines and
                #      'file' in lines[count-1]['id'] ):
                #     keep_lines.append(count-1)

                # print("\nLine Number: %d"%count)
                # for s in showlist:
                #     if s in line and line[s]:
                #         print("\t%s: %s"%(s,line[s]))
            count += 1
        epubO.write_split_epub(tmp,
                               keep_lines)
                               # ,
                               # authoropts=options.authoropts,
                               # titleopt=options.titleopt,
                               # descopt=options.descopt,
                               # tags=options.tagopts,
                               # languages=options.languageopts,
                               # coverjpgpath=options.coveropt)
        book['splittmp'] = tmp

        return book

    def _start_splitmerge(self,book_list, tdir=None, db=None):
        # logger.debug(book_list)

        em = self.get_epubmerge_plugin()
        es = self.get_epubsplit_plugin()

        good_list = [ b for b in book_list if b['good'] ]

        tmp = PersistentTemporaryFile(prefix='merge-',
                                      suffix='.epub',
                                      dir=tdir)
        if len(good_list) == 1:
            deftitle = "New "+good_list[0]['title']
            defauthors = good_list[0]['authors']
        else:
            deftitle = "New Chapters Anthology"
            defauthors = ["Various Authors"]

        mi = MetaInformation(deftitle,defauthors)
        tagslists = [ x['tags'] for x in good_list ]
        mi.tags = [item for sublist in tagslists for item in sublist]
        mi.comments = "<p>New Chapters from:</p>"
        mi.comments += '<br/>'.join( [ "%s by %s"%(x['title'],", ".join(x['authors'])) for x in good_list ] )


        mergetmps_list = []
        for book in good_list:
            tmptitle = PersistentTemporaryFile(prefix='splitmergenew-title-%s-'%book['calibre_id'],
                                               suffix='.epub',
                                               dir=tdir)
            title_author_epub(tmptitle,
                              book['title'],
                              ", ".join(book['authors']))
            mergetmps_list.append(tmptitle)
            mergetmps_list.append(book['splittmp'])

        em.do_merge(tmp,
                    mergetmps_list,# [b['splittmp'] for b in good_list],
                    authoropts=mi.authors,
                    titleopt=mi.title,
                    descopt=mi.comments,
                    tags=mi.tags,
                    keepmetadatafiles=False,
                    )

        book_id = db.create_book_entry(mi,
                                       add_duplicates=True)

        db.add_format_with_hooks(book_id,
                                 'EPUB',
                                 tmp, index_is_id=True)

        self.gui.library_view.model().books_added(1)
        self.gui.library_view.model().refresh_ids([book_id])
        # self.gui.iactions['Edit Metadata'].edit_metadata(False)
        self.gui.tags_view.recount()

        ## run word counts
        if 'Count Pages' in self.gui.iactions:
            cp_plugin = self.gui.iactions['Count Pages']
            cp_plugin.count_statistics([book_id],['WordCount'])

        ## run auto convert
        self.gui.iactions['Convert Books'].auto_convert_auto_add([book_id])

        ## add to FFF update lists
        self.gui.library_view.select_rows([book_id])
        if 'FanFicFare' in self.gui.iactions:
            fff_plugin = self.gui.iactions['FanFicFare']
            fff_plugin.update_lists(True)

        remove_dir(tdir)
        # logger.debug(good_list)

    def apply_settings(self):
        # No need to do anything with prefs here, but we could.
        prefs

    def is_library_view(self):
        # 0 = library, 1 = main, 2 = card_a, 3 = card_b
        return self.gui.stack.currentIndex() == 0

## XML isn't as forgiving as HTML, so rather than generate as strings,
## use DOM to generate the XML files.
from xml.dom.minidom import getDOMImplementation

from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED
from time import time

import string
from six import text_type as unicode
from six import ensure_binary
from io import BytesIO

def title_author_epub(zipio, title, author):
    ## Python 2.5 ZipFile is rather more primative than later
    ## versions.  It can operate on a file, or on a BytesIO, but
    ## not on an open stream.  OTOH, I suspect we would have had
    ## problems with closing and opening again to change the
    ## compression type anyway.

    ## mimetype must be first file and uncompressed.  Python 2.5
    ## ZipFile can't change compression type file-by-file, so we
    ## have to close and re-open
    outputepub = ZipFile(zipio, 'w', compression=ZIP_STORED)
    outputepub.debug=3
    outputepub.writestr('mimetype','application/epub+zip')
    outputepub.close()

    ## Re-open file for content.
    outputepub = ZipFile(zipio, 'a', compression=ZIP_DEFLATED)
    outputepub.debug=3

    ## Create META-INF/container.xml file.  The only thing it does is
    ## point to content.opf
    containerdom = getDOMImplementation().createDocument(None, "container", None)
    containertop = containerdom.documentElement
    containertop.setAttribute("version","1.0")
    containertop.setAttribute("xmlns","urn:oasis:names:tc:opendocument:xmlns:container")
    rootfiles = containerdom.createElement("rootfiles")
    containertop.appendChild(rootfiles)
    rootfiles.appendChild(newTag(containerdom,"rootfile",{"full-path":"content.opf",
                                                          "media-type":"application/oebps-package+xml"}))
    outputepub.writestr("META-INF/container.xml",containerdom.toxml(encoding='utf-8'))
    containerdom.unlink()
    del containerdom

    ## Epub has two metadata files with real data.  We're putting
    ## them in content.opf (pointed to by META-INF/container.xml)
    ## and toc.ncx (pointed to by content.opf)

    ## content.opf contains metadata, a 'manifest' list of all
    ## other included files, and another 'spine' list of the items in the
    ## file

    uniqueid="splitmergenew-uid-%d" % time() # real sophisticated uid scheme.

    contentdom = getDOMImplementation().createDocument(None, "package", None)
    package = contentdom.documentElement
    ## might want 3.1 or something in future.
    package.setAttribute("version","2.0")
    logger.info("Saving EPUB Version "+package.getAttribute("version"))
    package.setAttribute("xmlns","http://www.idpf.org/2007/opf")
    package.setAttribute("unique-identifier","splitmergenew-uid")
    metadata=newTag(contentdom,"metadata",
                    attrs={"xmlns:dc":"http://purl.org/dc/elements/1.1/",
                           "xmlns:opf":"http://www.idpf.org/2007/opf"})
    package.appendChild(metadata)

    metadata.appendChild(newTag(contentdom,"dc:identifier",
                                text=uniqueid,
                                attrs={"id":"splitmergenew-uid"}))

    metadata.appendChild(newTag(contentdom,"dc:title",text=title.lower(),
                                attrs={"id":"id"}))

    metadata.appendChild(newTag(contentdom,"dc:creator",
                                attrs={"opf:role":"aut"},
                                text=author.lower()))

    ## end of metadata, create manifest.
    items = [] # list of (id, href, type, title) tuples(all strings)
    itemrefs = [] # list of strings -- idrefs from .opfs' spines
    items.append(("ncx","toc.ncx","application/x-dtbncx+xml",None)) ## we'll generate the toc.ncx file,
                                                                    ## but it needs to be in the items manifest.

    items.append(("title_page","OEBPS/title_page.xhtml","application/xhtml+xml","%s by %s"%(title,author)))
    itemrefs.append("title_page")

    ## create toc.ncx file
    tocncxdom = getDOMImplementation().createDocument(None, "ncx", None)
    ncx = tocncxdom.documentElement
    ncx.setAttribute("version","2005-1")
    ncx.setAttribute("xmlns","http://www.daisy.org/z3986/2005/ncx/")
    head = tocncxdom.createElement("head")
    ncx.appendChild(head)
    head.appendChild(newTag(tocncxdom,"meta",
                            attrs={"name":"dtb:uid", "content":uniqueid}))
    head.appendChild(newTag(tocncxdom,"meta",
                            attrs={"name":"dtb:depth", "content":"1"}))
    head.appendChild(newTag(tocncxdom,"meta",
                            attrs={"name":"dtb:totalPageCount", "content":"0"}))
    head.appendChild(newTag(tocncxdom,"meta",
                            attrs={"name":"dtb:maxPageNumber", "content":"0"}))

    docTitle = tocncxdom.createElement("docTitle")
    docTitle.appendChild(newTag(tocncxdom,"text",text=title))
    ncx.appendChild(docTitle)

    tocnavMap = tocncxdom.createElement("navMap")
    ncx.appendChild(tocnavMap)

    # <navPoint id="<id>" playOrder="<risingnumberfrom0>">
    #   <navLabel>
    #     <text><chapter title></text>
    #   </navLabel>
    #   <content src="<chapterfile>"/>
    # </navPoint>
    index=0
    for item in items:
        (id,href,type,navtitle)=item
        # only items to be skipped, cover.xhtml, images, toc.ncx, stylesheet.css, should have no title.
        if navtitle :
            navPoint = newTag(tocncxdom,"navPoint",
                              attrs={'id':id,
                                     'playOrder':unicode(index)})
            tocnavMap.appendChild(navPoint)
            navLabel = newTag(tocncxdom,"navLabel")
            navPoint.appendChild(navLabel)
            ## the xml library will re-escape as needed.
            navLabel.appendChild(newTag(tocncxdom,"text",text=navtitle))
            navPoint.appendChild(newTag(tocncxdom,"content",attrs={"src":href}))
            index=index+1

    # write toc.ncx to zip file
    outputepub.writestr("toc.ncx",tocncxdom.toprettyxml(indent='   ',encoding='utf-8'))
    tocncxdom.unlink()
    del tocncxdom

    manifest = contentdom.createElement("manifest")
    package.appendChild(manifest)
    for item in items:
        (id,href,type,itemtitle)=item
        manifest.appendChild(newTag(contentdom,"item",
                                    attrs={'id':id,
                                           'href':href,
                                           'media-type':type}))

    spine = newTag(contentdom,"spine",attrs={"toc":"ncx"})
    package.appendChild(spine)
    for itemref in itemrefs:
        spine.appendChild(newTag(contentdom,"itemref",
                                 attrs={"idref":itemref,
                                        "linear":"yes"}))
    # write content.opf to zip.
    contentxml = contentdom.toprettyxml(indent='   ',encoding='utf-8')
    outputepub.writestr("content.opf",contentxml)

    contentdom.unlink()
    del contentdom

    PAGE = string.Template('''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>${title} by ${author}</title>
</head>
<body>
<h3>${title} by ${author}</h3>
</body>
</html>
''')
    titlepageIO = BytesIO()
    titlepageIO.write(ensure_binary(PAGE.substitute({'title':title,
                                                     'author':author})))
    outputepub.writestr("OEBPS/title_page.xhtml",titlepageIO.getvalue())
    titlepageIO.close()

    # declares all the files created by Windows.  otherwise, when
    # it runs in appengine, windows unzips the files as 000 perms.
    for zf in outputepub.filelist:
        zf.create_system = 0
    outputepub.close()

## Utility method for creating new tags.
def newTag(dom,name,attrs=None,text=None):
    tag = dom.createElement(name)
    if( attrs is not None ):
        for attr in attrs.keys():
            tag.setAttribute(attr,attrs[attr])
    if( text is not None ):
        tag.appendChild(dom.createTextNode(text))
    return tag

# title_author_epub("TitleAuthor.epub", "Minimal Title","Minimal Author")
