# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=indent:ai

"""The main driver for the KOReader driver. Everything starts here."""

__license__ = "GPL v3"
__copyright__ = "2025, Jim Miller"
__docformat__ = "markdown en"

import os
import apsw
from collections import OrderedDict
from datetime import datetime

import logging
logger = logging.getLogger(__name__)

from calibre.devices.user_defined.driver import USER_DEFINED

from calibre_plugins.koreader import luadata

class KOREADER(USER_DEFINED):
    """
    Cheese update a couple places in KOReader to:
    - Force koreader meta cache to reload updated books.
    - Make History act more like 'most recent' list, including new/updated.
    """

    name = "KOReader Device Interface"
    gui_name = "KOReader eReader"
    author = "Jim Miller"
    description = _( 
        "Communicate with KOReader running (on Kobo?) to make it behave how I want."
    )
    supported_platforms = ['windows', 'osx', 'linux']

    minimum_calibre_version = (8,4,0)
    version = (0,1,0)

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('USB Vendor ID (in hex)') + ':::<p>' + _(
            'Get this ID using Preferences -> Misc -> Get information to '
            'set up the user-defined device') + '</p>',
        _('USB Product ID (in hex)')+ ':::<p>' + _(
            'Get this ID using Preferences -> Misc -> Get information to '
            'set up the user-defined device') + '</p>',
        _('USB Revision ID (in hex)')+ ':::<p>' + _(
            'Get this ID using Preferences -> Misc -> Get information to '
            'set up the user-defined device') + '</p>',
        '',
        _('Unused (leave blank)') + ':::<p>' + _(
            'This field is no longer used, leave it blank.') + '</p>',
        _('Unused (leave blank)') + ':::<p>' + _(
            'This field is no longer used, leave it blank.') + '</p>',
        _('Unused (leave blank)') + ':::<p>' + _(
            'This field is no longer used, leave it blank.') + '</p>',
        _('Unused (leave blank)') + ':::<p>' + _(
            'This field is no longer used, leave it blank.') + '</p>',
        _('Main memory folder') + ':::<p>' + _(
            'Enter the folder where the books are to be stored. This folder '
            'is prepended to any send_to_device template') + '</p>',
        _('Card A folder') + ':::<p>' + _(
            'Enter the folder where the books are to be stored. This folder '
            'is prepended to any send_to_device template') + '</p>',
        _('Swap main and card A') + ':::<p>' + _(
            "Check this box if the device's main memory is being seen as "
            'card a and the card is being seen as main memory') + '</p>',
        '',
        _('KOReader Cache File') + ':::<p>' + _(
            '.adds/koreader/settings/bookinfo_cache.sqlite3') + '</p>',
        _('KOReader History File') + ':::<p>' + _(
            '.adds/koreader/history.lua') + '</p>',
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                '0xffff',
                '0xffff',
                '0xffff',
                None,
                '',
                '',
                '',
                '',
                '',
                '',
                False,
                None,
                '.adds/koreader/settings/bookinfo_cache.sqlite3',
                '.adds/koreader/history.lua',
    ]

    OPT_KOREADER_CACHE        = 12
    OPT_KOREADER_HISTORY      = 13

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        logger.debug(f'uploading {len(files)} books')
        logger.debug(f'uploading {names}')
        retlist = super(KOREADER, self).upload_books(files, names, on_card, end_session, metadata)

        e = self.settings().extra_customization
        logger.debug("KOReader:upload_books: cache:%s"%e[self.OPT_KOREADER_CACHE])
        logger.debug("KOReader:upload_books: history:%s"%e[self.OPT_KOREADER_HISTORY])

        cache_sql_path = os.path.join(self._main_prefix, e[self.OPT_KOREADER_CACHE])
        history_lua_path = os.path.join(self._main_prefix, e[self.OPT_KOREADER_HISTORY])
        onboard_path = '/mnt/onboard'

        logger.debug("KOReader:upload_books: cache_sql_path:%s"%cache_sql_path)
        logger.debug("KOReader:upload_books: cache_sql_path isfile:%s"%os.path.isfile(cache_sql_path))
        logger.debug("KOReader:upload_books: history_lua_path:%s"%history_lua_path)
        logger.debug("KOReader:upload_books: history_lua_path isfile:%s"%os.path.isfile(history_lua_path))

        db = apsw.Connection(cache_sql_path)

        ## matching
        ## 'D:\\calibre\\11956.epub'
        ## to
        ## '/mnt/onboard/calibre/', '7158.epub'
        ##
        updated_filepaths = []
        for book in retlist:
            path, filename = os.path.split(os.path.splitdrive(book[0])[1])
            path = onboard_path + path.replace('\\','/')
            if not path.endswith('/'):
                path = path + '/'
            logger.debug("'%s','%s'"%(path,filename))

            # for row in db.execute('select directory, filename, title from bookinfo where directory=? and filename=?',
            #                       (path, filename)):
            #     logger.debug(row)
            db.execute('delete from bookinfo where directory=? and filename=?',
                       (path, filename))
            updated_filepaths.append(path+filename)
        db.close()

        data = luadata.read(history_lua_path, encoding="utf-8")
        ## [
        ##   {'file': '/mnt/onboard/.adds/koreader/help/quickstart-en-v2025.04.html',
        ##    'time': 1750010070
        ##   },
        ##   {'file': ## '/mnt/onboard/calibre/8876.epub',
        ##    'time': 1749698045
        ##   },
        ##   {'file': '/mnt/onboard/calibre/12805.epub', 
        ##    'time': 1750009108
        ##   }, ... ]

        # convert to an orderedict to key by file and preserve... order
        odata = OrderedDict([ (x['file'], x) for x in data ])
        # logger.debug(odata)

        logger.debug(updated_filepaths)
        for b in reversed(updated_filepaths):
            if b not in odata:
                odata[b] = {'file':b,'time':int(datetime.now().timestamp()) }
            odata.move_to_end(b,last=False) # and the last shall be first...        

        luadata.write(history_lua_path, list(odata.values()), encoding="utf-8",
                      indent="\t", prefix="return ")
        return retlist

    # XXX Also remove from cache on delete?  Deleting in KOReader doesn't bother...
    # XXX .sdr dir? Keeping it keeps settings, etc in case it comes back?
    #     koreader *does* delete .sdr dir...
    #     I don't *think* the calibre KoboTouch driver does.
    
