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
       - Optionally only bump book in History list if they have the 'bump' tag.
    """

    name = "KOReader Device Interface"
    gui_name = "KOReader eReader"
    author = "Jim Miller"
    description = _(
        "Communicate with KOReader running (on Kobo?) to make it behave how I want."
    )
    supported_platforms = ['windows', 'osx', 'linux']

    minimum_calibre_version = (8,4,0)
    version = (0,3,0)

    ## also delete .sdr 'sidecar' dirs on file delete.
    DELETE_EXTS  = ['.sdr']

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
            "KOReader's cache sqlite3 file relative to Calibre's 'main' dir.") + '</p>',
        _('KOReader History File') + ':::<p>' + _(
            "KOReader's history.lua file relative to Calibre's 'main' dir.") + '</p>',
        _('KOReader Onboard Path') + ':::<p>' + _(
            "KOReader's relative path ON DEVICE.  Needs to match keys in cache and history.") + '</p>',
        _('Bump Up History Tag') + ':::<p>' + _(
            "If set, ONLY books with this tag will be bumped up the History list.  Otherwise, all sent books will be.") + '</p>',
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
                '/mnt/onboard',
                '',
    ]

    OPT_KOREADER_CACHE        = 12
    OPT_KOREADER_HISTORY      = 13
    OPT_KOREADER_ONBOARD      = 14
    OPT_KOREADER_BUMP_TAG     = 15

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        # logger.debug(f'uploading {len(files)} books')
        # logger.debug(f'uploading {files} books')
        # logger.debug(f'uploading {names}')
        # logger.debug(f'uploading {metadata}')
        retlist = super(KOREADER, self).upload_books(files, names, on_card, end_session, metadata)

        e = self.settings().extra_customization
        # logger.debug("KOReader:upload_books: cache:%s"%e[self.OPT_KOREADER_CACHE])
        # logger.debug("KOReader:upload_books: history:%s"%e[self.OPT_KOREADER_HISTORY])

        cache_sql_path = e[self.OPT_KOREADER_CACHE]
        if cache_sql_path:
            cache_sql_path = os.path.join(self._main_prefix,cache_sql_path)

        history_lua_path = e[self.OPT_KOREADER_HISTORY]
        if history_lua_path:
            history_lua_path = os.path.join(self._main_prefix, history_lua_path)

        onboard_path = e[self.OPT_KOREADER_ONBOARD]
        bump_tag = e[self.OPT_KOREADER_BUMP_TAG]

        # logger.debug("KOReader:upload_books: cache_sql_path:%s"%cache_sql_path)
        # logger.debug("KOReader:upload_books: cache_sql_path isfile:%s"%os.path.isfile(cache_sql_path))
        # logger.debug("KOReader:upload_books: history_lua_path:%s"%history_lua_path)
        # logger.debug("KOReader:upload_books: history_lua_path isfile:%s"%os.path.isfile(history_lua_path))

        db = None
        if cache_sql_path:
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
                logger.debug("Remove '%s','%s' from cache db"%(path,filename))

                # for row in db.execute('select directory, filename, title from bookinfo where directory=? and filename=?',
                #                       (path, filename)):
                #     logger.debug(row)
                db.execute('delete from bookinfo where directory=? and filename=?',
                           (path, filename))
                updated_filepaths.append(path+filename)
            db.close()

        if history_lua_path:
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

            bump_list = []
            if bump_tag:
                bump_list = [ bump_tag in m.tags for m in reversed(metadata) ]
            # logger.debug(bump_list)
            ## history only cares about order, so I don't bother updating
            ## the time, although it would be easy.
            # logger.debug(updated_filepaths)
            changed = False
            for i, b in enumerate(reversed(updated_filepaths)):
                # always if no bump_tag set.
                if not bump_tag or bump_list[i]:
                    if b not in odata:
                        odata[b] = {'file':b,'time':int(datetime.now().timestamp()) }
                    logger.debug('history bump:%s'%b)
                    odata.move_to_end(b,last=False) # and the last shall be first...
                    changed = True
            if changed:
                luadata.write(history_lua_path, list(odata.values()), encoding="utf-8",
                              indent="\t", prefix="return ")
        return retlist

    ## Also remove from cache on delete?  Deleting in KOReader
    ## doesn't bother, and there is a prune function in koreader.
    ## So, no.
