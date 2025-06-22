-- The 'Book status' screen:
--
-- I don't use star ratings or builtin status.  Remove those, add
-- current chapter, tags, and re-arrange.

local Blitbuffer = require("ffi/blitbuffer")
local BookList = require("ui/widget/booklist")
local Button = require("ui/widget/button")
local CenterContainer = require("ui/widget/container/centercontainer")
local Device = require("device")
local FileManagerBookInfo = require("apps/filemanager/filemanagerbookinfo")
local Font = require("ui/font")
local FocusManager = require("ui/widget/focusmanager")
local FrameContainer = require("ui/widget/container/framecontainer")
local Geom = require("ui/geometry")
local GestureRange = require("ui/gesturerange")
local HorizontalGroup = require("ui/widget/horizontalgroup")
local HorizontalSpan = require("ui/widget/horizontalspan")
local ImageWidget = require("ui/widget/imagewidget")
local InputDialog = require("ui/widget/inputdialog")
local InputText = require("ui/widget/inputtext")
local LeftContainer = require("ui/widget/container/leftcontainer")
local LineWidget = require("ui/widget/linewidget")
local ProgressWidget = require("ui/widget/progresswidget")
local RenderImage = require("ui/renderimage")
local Size = require("ui/size")
local TextBoxWidget = require("ui/widget/textboxwidget")
local TextWidget = require("ui/widget/textwidget")
local TitleBar = require("ui/widget/titlebar")
local ToggleSwitch = require("ui/widget/toggleswitch")
local UIManager = require("ui/uimanager")
local VerticalGroup = require("ui/widget/verticalgroup")
local VerticalSpan = require("ui/widget/verticalspan")
local datetime = require("datetime")
local util = require("util")
local _ = require("gettext")
local Screen = Device.screen
local T = require("ffi/util").template
local dump = require("dump")

local BookStatusWidget = require("ui/widget/bookstatuswidget")

function BookStatusWidget:genThumbnailGroup(img_height,img_width)
    local thumbnail = FileManagerBookInfo:getCoverImage(self.ui.document)
    if thumbnail then
        -- Much like BookInfoManager, honor AR here
        local cbb_w, cbb_h = thumbnail:getWidth(), thumbnail:getHeight()
        if cbb_w > img_width or cbb_h > img_height then
            local scale_factor = math.min(img_width / cbb_w, img_height / cbb_h)
            cbb_w = math.min(math.floor(cbb_w * scale_factor)+1, img_width)
            cbb_h = math.min(math.floor(cbb_h * scale_factor)+1, img_height)
            thumbnail = RenderImage:scaleBlitBuffer(thumbnail, cbb_w, cbb_h, true)
        end
        return ImageWidget:new{
            image = thumbnail,
            width = cbb_w,
            height = cbb_h,
        }
    end
end


function BookStatusWidget:genBookInfoGroup()
    local width = Screen:getWidth()
    local height = 174
    if Screen:getScreenMode() == "landscape" then
        height = Screen:scaleBySize(height)
    else
        height = Screen:scaleBySize(height * 1.5)
    end

    -- Get a chance to have title and authors rendered with alternate
    -- glyphs for the book language
    local props = self.ui.doc_props
    --[[
    print("dump(props)")
    print(dump(props))
        dump(props)
        {
            ["authors"] = "Cherico",
            ["keywords"] = "FanFiction\
        NSFW\
        Nick\
        Saved By The Bell\
        The Company Fucks Everyone\
        In-Progress\
        !000",
            ["display_title"] = "000 Saved by the Spell (109,932)",
            ["language"] = "en",
            ["title"] = "000 Saved by the Spell (109,932)",
            ["description"] = "<div class=\"bbWrapper\">Saved by the spell</div>",
        }
    ]]

    local lang = props.language
    -- title
    local vert_group = VerticalGroup:new{
        align = "center",
        VerticalSpan:new{ width = height * 0.1 },
    }
    local text_label = TextBoxWidget:new{
        text = "Title",
        lang = lang,
        width = width,
        face = self.small_font_face,
        fgcolor = Blitbuffer.colorFromString("#0066FF"),
        alignment = "center",
    }
    table.insert(vert_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_label:getSize().h },
            text_label
        }
    )
    local text_title =TextBoxWidget:new{
        text = props.display_title,
        lang = lang,
        width = width,
        face = self.large_font_face,
        alignment = "center",
    }
    table.insert(vert_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_title:getSize().h },
            text_title
        }
    )
    -- author
    local text_author = TextBoxWidget:new{
        text = (self.ui.doc_props.authors or "" ):gsub("\n", ", "),
        lang = lang,
        face = self.small_font_face,
        width = width,
        alignment = "center",
    }
    table.insert(vert_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_author:getSize().h },
            text_author,
        }
    )
    table.insert(vert_group,
        VerticalSpan:new{ width = height * 0.1 }
    )
    -- progress bar
    local read_percentage = self.ui:getCurrentPage() / self.total_pages
    local progress_bar = ProgressWidget:new{
        width = math.floor(width * 0.7),
        height = Screen:scaleBySize(10),
        percentage = read_percentage,
        ticks = nil,
        last = nil,
    }
    table.insert(vert_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = progress_bar:getSize().h },
            progress_bar
        }
    )
    -- complete text
    local text_complete = TextWidget:new{
        text = T(_("%1\xE2\x80\xAF% Completed"), string.format("%1.f", read_percentage * 100)),
        face = self.small_font_face,
    }
    table.insert(vert_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_complete:getSize().h },
            text_complete
        }
    )
    -- Current chapter

    table.insert(vert_group,
        VerticalSpan:new{ width = height * 0.1 }
    )
    local chapter_title = self.ui.toc:getTocTitleByPage(self.ui:getCurrentPage())

    text_label = TextBoxWidget:new{
        text = "Chapter",
        lang = lang,
        width = width,
        face = self.small_font_face,
        fgcolor = Blitbuffer.colorFromString("#0066FF"),
        alignment = "center",
    }
    table.insert(vert_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_label:getSize().h },
            text_label
        }
    )
    local text_chapter = TextBoxWidget:new{
        text = chapter_title,
        lang = lang,
        width = width,
        face = self.large_font_face,
        alignment = "center",
    }
    table.insert(vert_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_chapter:getSize().h },
            text_chapter
        }
    )

    return CenterContainer:new{
        dimen = Geom:new{ w = width, h = height },
        vert_group, -- book_info_group,
    }
end

function BookStatusWidget:getStatusContent(width)
    local title_bar = TitleBar:new{
        width = width,
        bottom_v_padding = 0,
        close_callback = not self.readonly and function() self:onClose() end,
        show_parent = self,
    }
    local content = VerticalGroup:new{
        align = "left",
        title_bar,
        self:genBookInfoGroup(),
        self:genHeader(_("Metadata")),
        self:genTagsGroup(width),
        self:genHeader(_("Statistics")),
        self:genStatisticsGroup(width),
    }
    return content
end

function BookStatusWidget:genTagsGroup(width)
    local screen_width = Screen:getWidth()
    local split_span_width = math.floor(screen_width * 0.05)
    local height
    if Screen:getScreenMode() == "landscape" then
        height = Screen:scaleBySize(150)
    else
        height = Screen:scaleBySize(300)
    end
    local split_span_width = math.floor(screen_width * 0.05)

    local img_width, img_height
    if Screen:getScreenMode() == "landscape" then
        img_width = Screen:scaleBySize(132)
        img_height = Screen:scaleBySize(184)
    else
        img_width = Screen:scaleBySize(132 * 1.5)
        img_height = Screen:scaleBySize(184 * 1.5)
    end

    local horz_group = HorizontalGroup:new{
        align = "top",
    }
    local thumbnail = self:genThumbnailGroup(img_height,img_width)
    if thumbnail then
        table.insert(horz_group,
            HorizontalSpan:new{ width =  split_span_width })
        table.insert(horz_group, thumbnail)
    end

    width = screen_width - split_span_width - img_width

    tags_text = TextBoxWidget:new{
        text = (self.ui.doc_props.keywords or "" ):gsub("\n", ", "),
        lang = lang,
        width = width,
        face = self.medium_font_face,
        alignment = "center",
    }
    if tags_text:getSize().h > height then
        tags_text:free()
        tags_text = TextBoxWidget:new{
            text = (self.ui.doc_props.keywords or ""):gsub("\n", ", "),
            lang = lang,
            width = width,
            face = self.small_font_face,
            alignment = "center",
        }
    end

    table.insert(horz_group, tags_text)

    return VerticalGroup:new{
        align = "center",
        VerticalSpan:new{ width = Size.span.vertical_large },
        CenterContainer:new{
            dimen = Geom:new{ w = screen_width, h = img_height },
            horz_group,
        }
    }
end

