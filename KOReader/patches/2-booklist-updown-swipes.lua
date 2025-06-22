local BD = require("ui/bidi")
local UIManager = require("ui/uimanager")

local Menu = require("ui/widget/menu")

-- I want to be able to swipe lists up and down, default is only
-- right-left for some reason.  Covers ToC, History, and several other
-- lists, but not all.

-- for ToC, History, etc.
function Menu:onSwipe(arg, ges_ev)
    local direction = BD.flipDirectionIfMirroredUILayout(ges_ev.direction)
    if direction == "west" or direction == "north" then
        self:onNextPage()
    elseif direction == "east" or direction == "south" then
        self:onPrevPage()
    else -- diagonal swipe
        -- trigger full refresh
        UIManager:setDirty(nil, "full")
    end
end
