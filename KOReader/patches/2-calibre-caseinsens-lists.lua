local userpatch = require("userpatch")

userpatch.registerPatchPluginFunc("calibre", function(Calibre)

    -- 'sub' module CalibreSearch gotten from the reference frame of
    -- one of the functions on main plugin object, but it has to be
    -- one that's been called.  Only getSearchMenuTable works.
    local CalibreSearch, up_idx = userpatch.getUpValue(Calibre.getSearchMenuTable, "CalibreSearch")

    -- print("\ncalibre patch CalibreSearch:")
    -- print(CalibreSearch)

    CalibreSearch.switchResults = function(self,t, title, is_child, page)
        if not title then
            title = _("Search results")
        end
        print("\nCalibreSearch.switchResults HERE\n")
        local natsort = my_natsort_cmp(self.natsort_cache)
        table.sort(t, function(a, b) return natsort(a.text, b.text) end)
    
        if is_child then
            local path_entry = {}
            path_entry.page = (self.search_menu.perpage or 1) * (self.search_menu.page or 1)
            table.insert(self.search_menu.paths, path_entry)
        end
        self.search_menu:switchItemTable(title, t, page or 1)
    end   
    
end)

-- function getUpValue(func_obj, up_value_name)
--     local upvalue
--     local up_value_idx = 1
--     while true do
--         local name, value = debug.getupvalue(func_obj, up_value_idx)
--         print("upvalue:")
--         print(name)
--         if not name then break end
--         if name == up_value_name then
--             upvalue = value
--             break
--         end
--         up_value_idx = up_value_idx + 1
--     end
--     return upvalue, up_value_idx
-- end


-- plugins aren't referenced the same way
-- Basically runs the function given with 'plugin' as named.

--[[
Natural sorting functions, for use with table.sort
<http://notebook.kulchenko.com/algorithms/alphanumeric-natural-sorting-for-humans-in-lua>
--]]
-- Original implementation by Paul Kulchenko
--[[--
Generates a natural sorting comparison function for table.sort.

@param cache Optional, hashmap used to cache the processed strings to speed up sorting
@return The cmp function to feed to `table.sort`
@return The cache used (same object as the passed one, if any; will be created if not)

@usage

-- t is an array of strings, we don't want to keep the cache around
table.sort(t, sort.natsort_cmp())

-- t is an array of arrays, we want to sort the strings in the "text" field of the inner arrays, and we want to keep the cache around.
local cmp, cache
cmp, cache = sort.natsort_cmp(cache)
table.sort(t, function(a, b) return cmp(a.text, b.text) end)
]]
function my_natsort_cmp(cache)
    if not cache then
        cache = {}
    end

    local function natsort_conv(s)
        local res, dot = "", ""
        for n, m, c in tostring(s):gmatch("(0*(%d*))(.?)") do
            if n == "" then
                dot, c = "", dot..c
            else
                res = res..(dot == "" and ("%03d%s"):format(#m, m)
                                       or "."..n)
                dot, c = c:match("(%.?)(.*)")
            end
            res = res..c:gsub("[%z\1-\127\192-\255]", "\0%0")
        end
        res = res:lower()
        cache[s] = res
        return res
    end

    local function natsort(a, b)
        local ca, cb = cache[a] or natsort_conv(a), cache[b] or natsort_conv(b)
        return ca < cb or ca == cb and a < b
    end
    return natsort, cache
end
