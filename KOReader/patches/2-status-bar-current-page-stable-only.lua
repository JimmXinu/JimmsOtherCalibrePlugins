-- Status Bar - Current page entry now shows both stable pages and
-- rendered pages as "{2 / 3} 4 / 6" -- I only want stable.
-- Keeping "{}" as stable indicator.

local ReaderFooter = require("apps/reader/modules/readerfooter")

local footerTextGeneratorMap = ReaderFooter.textGeneratorMap

footerTextGeneratorMap.page_progress = function(footer)
    local page_label = footer.ui.pagemap and footer.ui.pagemap:wantsPageLabels()
        and footer.ui.pagemap:getCurrentPageLabel(true)
    if footer.ui.document:hasHiddenFlows() then
        local flow = footer.ui.document:getPageFlow(footer.pageno)
        local page = footer.ui.document:getPageNumberInFlow(footer.pageno)
        local pages = footer.ui.document:getTotalPagesInFlow(flow)
        if flow == 0 then
            if page_label then
                local last_page = footer.ui.document:getLastLinearPage()
                local last_page_label = footer.ui.pagemap:getPageLastLabel(last_page)
                return ("{%s / %s} %d // %d"):format(page_label, last_page_label, page, pages)
            end
            return ("%d // %d"):format(page, pages)
        else
            if page_label then
                local first_page = footer.ui.document:getFirstPageInFlow(flow)
                local last_page_label = footer.ui.pagemap:getPageLastLabel(first_page + pages - 1)
                return ("{%s / %s} [%d / %d]%d"):format(page_label, last_page_label, page, pages, flow)
            end
            return ("[%d / %d]%d"):format(page, pages, flow)
        end
    else
        if page_label then
            return ("{%s / %s}"):format(page_label, footer.ui.pagemap:getLastPageLabel(true))
        end
        return ("%d / %d"):format(footer.pageno, footer.pages)
    end
end
