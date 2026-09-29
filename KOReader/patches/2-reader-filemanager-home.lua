-- Default 'FileManager' action from reader is to open in same dir as
-- the book, with the book highlighted.

-- Doing that takes uncomfortably long for me, but openning instead in
-- the empty 'Home' directory I defined is basically instant.

local ReaderMenu = require("apps/reader/modules/readermenu")

local orig_getDefaultMenuButtons = ReaderMenu.getDefaultMenuButtons

function ReaderMenu:getDefaultMenuButtons()
    retval = orig_getDefaultMenuButtons(self)
    retval.filemanager.callback = function()
                 self:onTapCloseMenu()
                 local file = G_reader_settings:readSetting("home_dir") or ""
                 self.ui:onClose()
                 self.ui:showFileManager(file .. "/")
             end
    return retval
end
