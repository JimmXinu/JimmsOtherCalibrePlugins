-- This one I copied from somewhere wholesale

local ReaderConfig = require("apps/reader/modules/readerconfig")

function ReaderConfig:onTapShowConfigMenu()
    if self.activation_menu ~= "swipe" then return end
end
