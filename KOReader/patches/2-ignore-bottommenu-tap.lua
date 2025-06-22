-- Show bottom menu while reader on swipe up, but not tap.  I kept
--getting it when I meant to page advance.

-- This one I copied from somewhere wholesale

local ReaderConfig = require("apps/reader/modules/readerconfig")

function ReaderConfig:onTapShowConfigMenu()
    if self.activation_menu ~= "swipe" then return end
end
