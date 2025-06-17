local BD = require("ui/bidi")
local UIManager = require("ui/uimanager")

local Menu = require("ui/widget/menu")

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

-- local BookList = require("ui/widget/booklist")
-- 
-- -- overrides ui/widget/menu Menu:onSwipe
-- function BookList:onSwipe(arg, ges_ev)
--     local direction = BD.flipDirectionIfMirroredUILayout(ges_ev.direction)
--     if direction == "west" or direction == "north" then
--         self:onNextPage()
--     elseif direction == "east" or direction == "south" then
--         self:onPrevPage()
--     else -- diagonal swipe
--         -- trigger full refresh
--         UIManager:setDirty(nil, "full")
--     end
-- end
-- 
