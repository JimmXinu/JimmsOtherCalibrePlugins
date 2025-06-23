local DataStorage = require("datastorage")
local SQ3 = require("lua-ljsqlite3/init")

local dump = require("dump")

local userpatch = require("userpatch")

-- This patch makes the statistics plugin work better with my personal
-- paradigm.
--
-- 1.  My books change.  A lot.  Depending on the book, sometimes
-- multiple times a day.
--
-- 2.  My book titles change.  Even more than the content because I
-- use a calibre plugboard to prepend an indicator ("000") to the
-- title to indicate new content I want read.  Yes, there exist other
-- mechanisms I could use instead, but this is the one I'm using right
-- now.  Oh, and I prepend series into title, too.  Which can also
-- change.
--
-- 3.  My book titles change evern more--because I also append the
-- book word count in parans to the title.  Yes, I favor word count
-- over ambiguous page counts; I'm weird that way.
--
-- Those two oddities mean ReaderStatistics' normal way of indexing
-- (Title, Authors, PartialMD5 of file) don't work for me
--
-- But! I pretty much always manage my books from Calibre, which
-- assigns a uuid to each one.  I can use that to index instead.
--
-- As of now, this patch expects the usser(me) to create the uuid
-- table in statistics.sqlite3 manually--and that it exists before
-- this patch is used. 
--
-- After that, if the book has one, the "calibre:<uuid>" (example:
-- "calibre:dcf61b0b-c049-4f23-ac2f-663eed3eb9d6") will be searched
-- for in the uuid table before the user/authors/md5 search.
--
-- If "calibre:<uuid>" not found, fall back to user/authors/md5
-- search, BUT only after normalizing to remove the leading '000' and
-- trailing page counts.  If it weren't for the included md5 key, I
-- probably would have stopped there.
--
-- After user/authors/md5 fine (or insert), also insert uuid, if the
-- book has one.

-- ----------------
--
-- Consolidating data from old duplicate data, both title and md5 changing
-- -- done in python off device.


--[=[
-- Assumed manually created right now.
local STATISTICS_DB_UUID_SCHEMA = [[
    CREATE TABLE IF NOT EXISTS uuid
        (
            uuid        TEXT PRIMARY KEY,
            id_book     INTEGER,
            UNIQUE (id_book),
            FOREIGN KEY(id_book) REFERENCES book(id)
        );
]]

]=]


-- plugins aren't referenced the same way
-- Basically runs the function given with 'plugin' as named.
userpatch.registerPatchPluginFunc("statistics", function(ReaderStatistics)

    local db_location = DataStorage:getSettingsDir() .. "/statistics.sqlite3"


    local orig_onBookMetadataChanged = ReaderStatistics.onBookMetadataChanged
    ReaderStatistics.onBookMetadataChanged = function(self, prop_updated)
        print("stats patch onBookMetadataChanged: "..dump(prop_update))
        return orig_onBookMetadataChanged(self, prop_updated)
    end
    
--    local orig_getIdBookDB = ReaderStatistics.getIdBookDB
    ReaderStatistics.getIdBookDB = function(self)
        -- print("stats patch self.ui.doc_settings.data.doc_props.identifiers")
        -- print(dump(self.ui.doc_settings.data.doc_props.identifiers))

        -- self.ui.doc_settings.data.doc_props.identifiers
        -- "fanficfare-uid:archiveofourown.org-uRHJunior-s14436069\
        -- calibre:db2e5387-0ba6-49b8-8af7-8818a4922b56\
        -- URL:https://archiveofourown.org/works/14436069"
        local uuid
        for j in (self.ui.doc_settings.data.doc_props.identifiers or ""):gmatch("calibre:[%w-]+") do uuid = j end
        if uuid then
            print("stats patch uuid:"..uuid)
        end

        local title, authors = self.data.title, self.data.authors
        --------
        -------- Fix titles for my use pattern
        --------
        print("stats patch orig title: "..title)
        -- titles in my library can be:
        -- "The book title"
        -- "(000) The book title"
        -- "(000) The book title (123,123)"
        -- "The book title (123,123)"
        title = title:gsub("^000 ", "")
        title = title:gsub(" %([%d,]+%)$", "")
        print("stats patch fixed title: "..title)
        
        local conn = SQ3.open(db_location)
        local id_book
        
        ----------- Search for id_book by uuid
        ----------- Used over title/authors/md5 search because my books change. 
        local sql_stmt = [[
            SELECT id_book
            FROM   uuid
            WHERE  uuid = ?;
        ]]
        local stmt = conn:prepare(sql_stmt)
        local result = stmt:reset():bind(uuid):step()
        if result then
            -- update basic book info in case it changed
            sql_stmt = [[
                UPDATE book
                SET    title = ?,
                       authors = ?,
                       md5 = ?
                WHERE  id = ?;
            ]]
            stmt = conn:prepare(sql_stmt)
            stmt:reset():bind(title, authors, self.doc_md5, result[1]):step()
            print("stats patch uuid retval:"..tonumber(result[1]))
            return tonumber(result[1])
        end

        -- --------- Search for *existence* by book record by title/authors/md5
        local sql_stmt = [[
            SELECT count(id)
            FROM   book
            WHERE  title = ?
              AND  authors = ?
              AND  md5 = ?;
        ]]
        local stmt = conn:prepare(sql_stmt)
        local result = stmt:reset():bind(title, authors, self.doc_md5):step()
        local nr_id = tonumber(result[1])
        if nr_id == 0 and self.ui.paging then
            -- In the past, title and/or authors strings, got from MuPDF, may have been or not null terminated.
            -- We need to check with all combinations if a book with these null terminated exists, and use it.
            title = title .. "\0"
            result = stmt:reset():bind(title, authors, self.doc_md5):step()
            nr_id = tonumber(result[1])
            if nr_id == 0 then
                authors = authors .. "\0"
                result = stmt:reset():bind(title, authors, self.doc_md5):step()
                nr_id = tonumber(result[1])
                if nr_id == 0 then
                    title = self.data.title
                    result = stmt:reset():bind(title, authors, self.doc_md5):step()
                    nr_id = tonumber(result[1])
                end
            end
        end
        if nr_id == 0 then
            if not self.is_doc_not_frozen then return end
            -- Not in the DB yet, initialize it
            stmt = conn:prepare("INSERT INTO book VALUES(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);")
            stmt:reset():bind(title, authors, self.data.notes,
                os.time(), self.data.highlights, self.data.pages,
                self.data.series, self.data.language, self.doc_md5, 0, 0):step()
            sql_stmt = [[
                SELECT last_insert_rowid() AS num;
            ]]
            id_book = conn:rowexec(sql_stmt)
        else
            sql_stmt = [[
                SELECT id
                FROM   book
                WHERE  title = ?
                  AND  authors = ?
                  AND  md5 = ?;
            ]]
            stmt = conn:prepare(sql_stmt)
            result = stmt:reset():bind(title, authors, self.doc_md5):step()
            id_book = result[1]
        end

        ------- insert into uuid table too if have a value.  'upsert'
        ------- because uuid can change once in a while, such as
        ------- rebuilding an anthology in a new book.
        if uuid then
            stmt = conn:prepare("INSERT INTO uuid VALUES(?, ?) ON CONFLICT (id_book) do update set uuid=excluded.uuid;")
            stmt:reset():bind(uuid,id_book):step()
            print("stats patch Added uuid record")
        end
        
        stmt:close()
        conn:close()

        print("stats patch title/authors/md5 retval:"..tonumber(id_book))
        return tonumber(id_book)
        
    end

end)

