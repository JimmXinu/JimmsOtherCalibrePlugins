-- Default 'FileManager' action from reader is to open in same dir as
-- the book, with the book highlighted.

-- Doing that takes uncomfortably long for me, but openning instead in
-- the empty 'Home' directory I defined is basically instant.

local ReaderMenu = require("apps/reader/modules/readermenu")

-- Couldn't set directly in data, defined, but not instantiated at this point.
--  ReaderMenu.menu_items.filemanager.callback = function()
--                  self:onTapCloseMenu()
--                  local file = G_reader_settings:readSetting("home_dir") or ""
--                  self.ui:onClose()
--                  self.ui:showFileManager(file .. "/")
--              end

-- So as to not copy the whole function
local orig_init = ReaderMenu.init

function ReaderMenu:init()
    orig_init(self)
    self.menu_items.filemanager.callback = function()
                 self:onTapCloseMenu()
                 local file = G_reader_settings:readSetting("home_dir") or ""
                 self.ui:onClose()
                 self.ui:showFileManager(file .. "/")
             end
end
