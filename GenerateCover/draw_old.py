#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
from calibre import prints
from calibre.constants import DEBUG
from calibre.ebooks import normalize
from calibre.utils.config import tweaks
from calibre.utils.fonts.scanner import font_scanner
from calibre.utils.magick import Image
from calibre.utils.magick.draw import (TextLine, create_canvas, create_text_wand,
                                       _get_line, annotate_img, fit_image)

import calibre_plugins.generate_cover.config as cfg
from calibre_plugins.generate_cover.common_utils import swap_author_names

def get_image_size(image_path):
    logo = Image()
    logo.open(image_path)
    return logo.size

def get_font_or_default(font_name):
    default_font = tweaks.get('generate_cover_title_font',None)
    if default_font is None:
        default_font = P('fonts/liberation/LiberationSerif-Bold.ttf')
    font_path = default_font
    if font_name:
        found_font = font_scanner.legacy_fonts_for_family(font_name)
        if len(found_font) == 0:
            if DEBUG:
                prints('Could not find font: ', font_name)
        else:
            # Assume 'normal' always in dict, else use default
            # {'normal': (path_to_font, friendly name)}
            if 'normal' in found_font:
                font_path = found_font['normal'][0]
            else:
                # Couldn't find 'normal' so just use first value if it exists
                font_path = found_font[found_font.keys()[0]][0]
    if not font_path or not os.access(font_path, os.R_OK):
        font_path = default_font
    return font_path

def get_textline(text, font_info, margin):
    a_font = get_font_or_default(font_info['name'])
    a_size = font_info['size']
    t = TextLine(text, a_size, margin, a_font)
    t._align = font_info['align']
    return t

def create_colored_text_wand(line, fill_color, stroke_color):
    twand = create_text_wand(line.font_size, font_path=line.font_path)
    twand.fill_color = fill_color
    if stroke_color:
        twand.stroke_color = stroke_color
    return twand

def add_border(img, border_width, border_color, bgcolor):
    lwidth, lheight = img.size
    bg_canvas = create_canvas(lwidth, lheight, bgcolor)
    border_canvas = create_canvas(lwidth+border_width*2, lheight+border_width*2,
                                  border_color)
    border_canvas.compose(bg_canvas, border_width, border_width)
    border_canvas.compose(img, border_width, border_width)
    return border_canvas

def draw_sized_text(img, dw, line, top, left_margin, right_margin, auto_reduce_font):
    # Wrapper around the image magic to reduce the font size if needed
    total_margin = left_margin + right_margin
    if img.size[0] - total_margin <= 0:
        total_margin = 0
        left_margin = 0
        right_margin = 0
    if auto_reduce_font:
        line_width = img.size[0]-total_margin
        initial_font_size = dw.font_size
        text = line.text
        while True:
            m = img.font_metrics(dw, text)
            if m.text_width < line_width:
                break
            oversize_factor = m.text_width / line_width
            if oversize_factor > 10:
                dw.font_size -= 8
            elif oversize_factor > 5:
                dw.font_size -= 4
            elif oversize_factor > 3:
                dw.font_size -= 2
            else:
                dw.font_size -= 1
            if dw.font_size < 6:
                # Enough is enough, clearly cannot fit on one line!
                # Abort the font reduction process
                dw.font_size = initial_font_size
                line.text = '*** TEXT TOO LARGE TO AUTO-FIT ***'
                break
    return draw_text(img, dw, line.text, top, left_margin, right_margin, line._align)

def draw_text(img, dw, text, top, left_margin=10, right_margin=10, align='center'):
    # Replaces the version in calibre's draw.py as we need a right margin and ability to align
    img_width = img.size[0]
    tokens = text.split(' ')
    while tokens:
        line, tokens = _get_line(img, dw, tokens, img_width - left_margin - right_margin)
        if not line:
            # Could not fit the first token on the line
            line = tokens[:1]
            tokens = tokens[1:]
        bottom = draw_line(img, dw, ' '.join(line), top, left_margin, right_margin, align)
        top = bottom
    return top

def draw_line(img, dw, line, top, left_margin, right_margin, align):
    # Replaces the version in calibre's draw.py as we need a right margin and ability to align
    m = img.font_metrics(dw, line)
    width, height = m.text_width, m.text_height
    img_width = img.size[0] - left_margin - right_margin
    if align == 'center':
        left = left_margin + max(int((img_width - width)/2.), 0)
    elif align == 'left':
        left = left_margin
    else:
        left = max(int(img_width - right_margin - width), 0)
    annotate_img(img, dw, left, top, 0, line)
    return top + height

def scaleup_image(width, height, pwidth, pheight):
    '''
    Fit image in box of width pwidth and height pheight.
    @param width: Width of image
    @param height: Height of image
    @param pwidth: Width of box
    @param pheight: Height of box
    @return: scaled, new_width, new_height. scaled is True iff new_width and/or new_height is different from width or height.
    '''
    image_ratio = width/float(height)
    box_ratio = pwidth/float(pheight)
    if image_ratio > box_ratio:
        width, height = pwidth, pwidth / image_ratio
    else:
        width, height = pheight * image_ratio, pheight

    return True, int(width), int(height)

def create_cover_page(top_lines, bottom_lines, display_image, options, image_path, output_format='jpg'):
    (width, height) = options.get(cfg.KEY_SIZE,(590, 750))
    margins = options.get(cfg.KEY_MARGINS)
    (top_mgn, bottom_mgn, left_mgn, right_mgn, image_mgn) = \
        (margins['top'], margins['bottom'], margins['left'], margins['right'], margins['image'])
    left_mgn = min([left_mgn, (width / 2) - 10])
    left_text_margin = left_mgn if left_mgn > 0 else 10
    right_mgn = min([right_mgn, (width / 2) - 10])
    right_text_margin = right_mgn if right_mgn > 0 else 10

    colors = options[cfg.KEY_COLORS]
    bgcolor, border_color, fill_color, stroke_color = (colors['background'], colors['border'],
                                                       colors['fill'], colors['stroke'])
    if not options.get(cfg.KEY_COLOR_APPLY_STROKE, False):
        stroke_color = None
    auto_reduce_font = options.get(cfg.KEY_FONTS_AUTOREDUCED, False)
    borders = options[cfg.KEY_BORDERS]
    (cover_border_width, image_border_width) = (borders['coverBorder'], borders['imageBorder'])
    is_background_image = options.get(cfg.KEY_BACKGROUND_IMAGE, False)
    if image_path:
        if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
            display_image = is_background_image = False

    canvas = create_canvas(width - cover_border_width*2, height - cover_border_width*2, bgcolor)
    if cover_border_width > 0:
        canvas = add_border(canvas, cover_border_width, border_color, bgcolor)

    if is_background_image:
        logo = Image()
        logo.open(image_path)
        outer_margin = 0 if cover_border_width == 0 else cover_border_width
        logo.size = (width - outer_margin * 2, height - outer_margin * 2)
        left = top = outer_margin
        canvas.compose(logo, left, top)

    top = top_mgn
    if len(top_lines) > 0:
        for line in top_lines:
            twand = create_colored_text_wand(line, fill_color, stroke_color)
            top = draw_sized_text(canvas, twand, line, top,
                                  left_text_margin, right_text_margin, auto_reduce_font)
            top += line.bottom_margin
        top -= top_lines[-1].bottom_margin

    if len(bottom_lines) > 0:
        # Draw this on a fake canvas so can determine the space required
        fake_canvas = create_canvas(width, height, bgcolor)
        footer_height = 0
        for line in bottom_lines:
            line.twand = create_colored_text_wand(line, fill_color, stroke_color)
            footer_height = draw_sized_text(fake_canvas, line.twand, line, footer_height,
                                            left_text_margin, right_text_margin, auto_reduce_font)
            footer_height += line.bottom_margin
        footer_height -= bottom_lines[-1].bottom_margin

        footer_top = height - footer_height - bottom_mgn
        bottom = footer_top
        # Re-use the text wand from previously which we will have adjusted the font size on
        for line in bottom_lines:
            bottom = draw_sized_text(canvas, line.twand, line, bottom,
                                     left_text_margin, right_text_margin, auto_reduce_font=False)
            bottom += line.bottom_margin
        available = (width - (left_mgn + right_mgn), int(footer_top - top) - (image_mgn * 2))
    else:
        available = (width - (left_mgn + right_mgn), int(height - top) - bottom_mgn - (image_mgn * 2))

    if not is_background_image and display_image and available[1] > 40:
        logo = Image()
        logo.open(image_path)
        lwidth, lheight = logo.size
        available = (available[0] - image_border_width*2, available[1] - image_border_width*2)
        scaled, lwidth, lheight = fit_image(lwidth, lheight, *available)
        if not scaled and options.get(cfg.KEY_RESIZE_IMAGE_TO_FIT, False):
            scaled, lwidth, lheight = scaleup_image(lwidth, lheight, *available)
        if scaled:
            logo.size = (lwidth, lheight)
        if image_border_width > 0:
            logo = add_border(logo, image_border_width, border_color, bgcolor)

        left = int(max(0, (width - lwidth)/2.))
        top  = top + image_mgn + ((available[1] - lheight)/2.)
        canvas.compose(logo, left, top)

    return canvas.export(output_format)

def get_title_author_series(mi, options=None):
    if not options:
        options = cfg.plugin_prefs[cfg.STORE_CURRENT]
    title = normalize(mi.title)
    authors = mi.authors
    if options.get(cfg.KEY_SWAP_AUTHOR, False):
        swapped_authors = []
        for author in authors:
            swapped_authors.append(swap_author_names(author))
        authors = swapped_authors
    author_string = normalize(' & '.join(authors))

    series = None
    if mi.series:
        series_text = options.get(cfg.KEY_SERIES_TEXT, '')
        if not series_text:
            series_text = cfg.DEFAULT_SERIES_TEXT
        from calibre.ebooks.metadata.book.formatter import SafeFormat
        series = SafeFormat().safe_format(series_text, mi, 'GC template error', mi)
    series_string = normalize(series)
    return (title, author_string, series_string)

def split_and_replace_newlines(text):
    text = text.replace('\\n','<br/>').replace('<br>','<br/>')
    return text.split('<br/>')

def generate_cover_for_book(mi, options=None):
    if not options:
        options = cfg.plugin_prefs[cfg.STORE_CURRENT]
    (title, author_string, series_string) = get_title_author_series(mi, options)
    custom_text = options.get(cfg.KEY_CUSTOM_TEXT, None)
    if custom_text:
        from calibre.ebooks.metadata.book.formatter import SafeFormat
        custom_text = SafeFormat().safe_format(custom_text.replace('\n', '<br/>'),
                                                      mi, 'GC template error', mi)

    fonts = options[cfg.KEY_FONTS]
    margin = options[cfg.KEY_MARGINS]['text']
    content_lines = {}
    content_lines['Title'] = [get_textline(title_line.strip(), fonts['title'], margin) for title_line in split_and_replace_newlines(title)]
    content_lines['Author'] = [get_textline(author_line.strip(), fonts['author'], margin) for author_line in split_and_replace_newlines(author_string)]
    if series_string:
        content_lines['Series'] = [get_textline(series_line.strip(), fonts['series'], margin) for series_line in split_and_replace_newlines(series_string)]
    if custom_text:
        content_lines['Custom Text'] = [get_textline(ct.strip(), fonts['custom'], margin)
                                        for ct in split_and_replace_newlines(custom_text)]
    top_lines = []
    bottom_lines = []
    field_order = options[cfg.KEY_FIELD_ORDER]
    above_image = True
    display_image = False
    for field in field_order:
        field_name = field['name']
        if field_name == 'Image':
            display_image = field['display']
            above_image = False
            continue
        if field_name not in content_lines:
            continue
        if field['display']:
            lines = content_lines[field_name]
            for line in lines:
                if above_image:
                    top_lines.append(line)
                else:
                    bottom_lines.append(line)

    image_name = options[cfg.KEY_IMAGE_FILE]
    image_path = None
    if image_name == cfg.TOKEN_CURRENT_COVER and hasattr(mi, '_path_to_cover'):
        image_path = mi._path_to_cover
    elif image_name == cfg.TOKEN_DEFAULT_COVER:
        image_path = I('library.png')
    else:
        image_path = os.path.join(cfg.get_images_dir(), image_name)
    if image_path is None or not os.path.exists(image_path):
        image_path = I('library.png')
    return create_cover_page(top_lines, bottom_lines, display_image, options, image_path)
