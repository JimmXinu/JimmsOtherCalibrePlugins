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

local BookStatusWidget = require("ui/widget/bookstatuswidget")

function BookStatusWidget:genBookInfoGroup()
    local screen_width = Screen:getWidth()
    local split_span_width = math.floor(screen_width * 0.05)

    local img_width, img_height
    if Screen:getScreenMode() == "landscape" then
        img_width = Screen:scaleBySize(132)
        img_height = Screen:scaleBySize(184)
    else
        img_width = Screen:scaleBySize(132 * 1.5)
        img_height = Screen:scaleBySize(184 * 1.5)
    end

    local height = img_height
    local width = screen_width - split_span_width - img_width

    -- Get a chance to have title and authors rendered with alternate
    -- glyphs for the book language
    local props = self.ui.doc_props
    local lang = props.language
    -- title
    local book_meta_info_group = VerticalGroup:new{
        align = "center",
        VerticalSpan:new{ width = height * 0.1 },
        TextBoxWidget:new{
            text = props.display_title,
            lang = lang,
            width = width,
            face = self.medium_font_face,
            alignment = "center",
        },

    }
    -- author
    local text_author = TextBoxWidget:new{
        text = props.authors,
        lang = lang,
        face = self.small_font_face,
        width = width,
        alignment = "center",
    }
    table.insert(book_meta_info_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_author:getSize().h },
            text_author
        }
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
    table.insert(book_meta_info_group,
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
    table.insert(book_meta_info_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_complete:getSize().h },
            text_complete
        }
    )
    -- Current chapter

    table.insert(book_meta_info_group,    
        VerticalSpan:new{ width = height * 0.1 }
    )
    local chapter_title = self.ui.toc:getTocTitleByPage(self.ui:getCurrentPage())

    local text_label = TextBoxWidget:new{
        text = "Chapter",
        lang = lang,
        width = width,
        face = self.small_font_face,
        alignment = "center",
    }
    table.insert(book_meta_info_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_label:getSize().h },
            text_label
        }
    )
    local text_chapter = TextBoxWidget:new{
        text = chapter_title,
        lang = lang,
        width = width,
        face = self.medium_font_face,
        alignment = "center",
    }
    table.insert(book_meta_info_group,
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = text_chapter:getSize().h },
            text_chapter
        }
    )
    --[[ rating
    table.insert(book_meta_info_group,
                 VerticalSpan:new{ width = Screen:scaleBySize(30) })
    local rateHeight = Screen:scaleBySize(60)
    table.insert(book_meta_info_group,
                 self:generateRateGroup(screen_width, rateHeight, self.summary.rating))
--]]
    -- build the final group
    local book_info_group = HorizontalGroup:new{
        align = "top",
        HorizontalSpan:new{ width =  split_span_width }
    }
    -- thumbnail
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
        table.insert(book_info_group, ImageWidget:new{
            image = thumbnail,
            width = cbb_w,
            height = cbb_h,
        })
    end

    table.insert(book_info_group, CenterContainer:new{
        dimen = Geom:new{ w = width, h = height },
        book_meta_info_group,
    })

    return CenterContainer:new{
        dimen = Geom:new{ w = screen_width, h = img_height },
        book_info_group,
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
        self:genHeader(_("Tags")),
        self:genTagsGroup(width),
        self:genHeader(_("Statistics")),
        self:genStatisticsGroup(width),
    }
    return content
end

function BookStatusWidget:genTagsGroup(width)
    local height
    if Screen:getScreenMode() == "landscape" then
        height = Screen:scaleBySize(120)
    else
        height = Screen:scaleBySize(240)
    end

    tags_text = TextBoxWidget:new{
        text = self.ui.doc_props.keywords:gsub("\n", ", "),
        lang = lang,
        width = width,
        face = self.medium_font_face,
        alignment = "center",
    }
    if tags_text:getSize().h > height then
        tags_text:free()
        tags_text = TextBoxWidget:new{
            text = self.ui.doc_props.keywords:gsub("\n", ", "),
            lang = lang,
            width = width,
            face = self.small_font_face,
            alignment = "center",
        }
    end

    return VerticalGroup:new{
        align = "center",
        VerticalSpan:new{ width = Size.span.vertical_large },
        CenterContainer:new{
            dimen = Geom:new{ w = width, h = height },
            tags_text
        }
    }
end
