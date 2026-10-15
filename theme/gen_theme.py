#!/usr/bin/env python3
"""Generate the "Ink" TWRP theme for the Hisense A9 (HLTE556N, E Ink, 824x1648).

The approved design is in ../design/*.dc.html (artboards at half scale, 412x824
CSS px; every size here is the mockup value x 2). This script writes a complete
TWRP theme into ../recovery/root/twres/, which the build copies over the stock
portrait_hdpi theme when it assembles the recovery ramdisk (build/make
core/Makefile: `cp -rf <device>/recovery/root $(TARGET_RECOVERY_OUT)/` runs
after Soong has filled twres/). See the device tree README, "Theme".

Inputs:
  --stock   bootable/recovery/gui/theme/common/portrait.xml of the TWRP tree the
            image is built from (android-12.1). Every page that the design does
            not cover is taken from it and only restyled through variables,
            styles and images; the five designed pages are replaced.
Outputs (all regenerated, do not edit by hand):
  recovery/root/twres/ui.xml, portrait.xml, splash.xml, images/*.png, fonts/*

Requires: python3 with Pillow and cairosvg
  nix-shell -p python3Packages.pillow python3Packages.cairosvg \
    --run 'python3 theme/gen_theme.py --stock <recovery>/gui/theme/common/portrait.xml'
"""
import argparse
import os
import re
import shutil
import sys

import cairosvg
from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
OUT = os.path.join(TREE, "recovery", "root", "twres")
FONTDIR = os.path.join(HERE, "fonts")

W, H = 824, 1648
INK = "#111111"
MUTED = "#5C5C5C"
WHITE = "#FFFFFF"
SW = 4                    # outline stroke: 2 CSS px in the mockup
THEME_VERSION = 6         # TW_THEME_VERSION in bootable/recovery/variables.h

# --------------------------------------------------------------------------
# Fonts. TWRP: FT_Set_Char_Size(size*16 [26.6 pt], 300 dpi) -> em = size*300/288
# px, so size = em_px * 0.96. Line box: max_height = (yMax - yMin over '!'..'~')
# + size/4, base = yMax + size/4 (minuitwrp/truetype.cpp).
# --------------------------------------------------------------------------
FONTS = {
    # name: (file, em px on the panel)
    "font_l": ("Figtree-Bold.ttf", 44),           # page titles (22 CSS / 700)
    "font_m": ("Figtree-SemiBold.ttf", 30),       # rows, buttons, lists (15 / 600)
    "font_m_bold": ("Figtree-Bold.ttf", 30),      # errors (no red on E Ink)
    "font_s": ("Figtree-Regular.ttf", 28),        # descriptions (14 / 400)
    "font_xs": ("Figtree-Regular.ttf", 26),       # secondary text (13 / 400)
    "font_status": ("Figtree-SemiBold.ttf", 26),  # status bar, card values (13 / 600)
    "font_label": ("Figtree-SemiBold.ttf", 28),   # tile labels (14 / 600)
    "font_home": ("Figtree-Bold.ttf", 40),        # "Recovery" (20 / 700)
    "font_chip": ("Figtree-SemiBold.ttf", 28),    # chips (14 / 600)
    "fixed": ("JetBrainsMono-Regular.ttf", 24),   # console, terminal (12 mono)
    "keylabel": ("Figtree-SemiBold.ttf", 44),
    "keylabel-small": ("Figtree-SemiBold.ttf", 30),
    "keylabel-longpress": ("Figtree-Regular.ttf", 22),
}


def tw_size(px):
    return int(round(px * 288.0 / 300.0))


class Metrics:
    """TWRP's text box for one font resource, computed the way truetype.cpp does."""

    def __init__(self, name):
        f, px = FONTS[name]
        self.size = tw_size(px)
        self.em = self.size * 300.0 / 288.0
        self.pil = ImageFont.truetype(os.path.join(FONTDIR, f), self.em)
        y_max, y_min = 0, 0
        for c in range(ord("!"), ord("~") + 1):
            x0, y0, x1, y1 = self.pil.getbbox(chr(c), anchor="ls")
            y_max = max(y_max, -y0)
            y_min = min(y_min, -y1)
        self.max_height = (y_max - y_min) + self.size // 4
        self.base = y_max + self.size // 4
        self.cap = -self.pil.getbbox("H", anchor="ls")[1]

    def top_for_center(self, cy):
        """Text top (TWRP placement y) that puts the cap-height centre at cy."""
        return int(round(cy - self.base + self.cap / 2.0))

    def width(self, s):
        return int(round(self.pil.getlength(s)))


M = {}


def met(name):
    if name not in M:
        M[name] = Metrics(name)
    return M[name]


def ty(font, cy):
    return met(font).top_for_center(cy)


def wrap(text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if met(font).width(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------
# Images: SVG rasterised at panel size. Outlines 4 px (2 CSS px), icon strokes
# as in the mockup x2. Only #111111 and transparency; antialiased edges only.
# --------------------------------------------------------------------------
IMAGES = {}


def svg(name, w, h, body):
    IMAGES[name] = (w, h, body)


def rrect(x, y, w, h, r, fill=False, stroke=SW):
    if fill:
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{INK}"/>'
    s = stroke / 2.0
    return (f'<rect x="{x + s}" y="{y + s}" width="{w - stroke}" height="{h - stroke}" '
            f'rx="{max(r - s, 0)}" fill="none" stroke="{INK}" stroke-width="{stroke}"/>')


def icon(d, x, y, scale, sw, color=INK, fill="none", cap="round"):
    return (f'<g transform="translate({x},{y}) scale({scale})"><path d="{d}" fill="{fill}" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="{cap}" '
            f'stroke-linejoin="round"/></g>')


# Icon paths from the approved mockups (viewBox 32 unless noted).
TILE_ICONS = {
    "install": "M16 5v15M9.5 13.5L16 20l6.5-6.5M7 25h18",
    "wipe": "M7 10h18M12 10V7h8v3M9.5 10l1.3 15h10.4l1.3-15M14 14v7M18 14v7",
    "backup": ("M6 9.5c0-2 4.5-3.5 10-3.5s10 1.5 10 3.5-4.5 3.5-10 3.5S6 11.5 6 9.5zM6 9.5v13c0 2 "
               "4.5 3.5 10 3.5s10-1.5 10-3.5v-13M6 16c0 2 4.5 3.5 10 3.5S26 18 26 16"),
    "restore": "M8 16a8 8 0 1 0 2.4-5.7M8 6.5v4.8h4.8M16 11.5V16l3 2",
    "mount": "M5 12h22v12H5zM9 8h14M12 18h8",
    "settings": ("M16 11.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zM16 4.5v3M16 24.5v3M4.5 16h3M24.5 16h3"
                 "M7.9 7.9l2.1 2.1M22 22l2.1 2.1M7.9 24.1L10 22M22 10l2.1-2.1"),
    "advanced": "M6 10h12M22 10h4M6 22h4M14 22h12M18 7v6M10 19v6",
    "reboot": "M16 5v9M10.5 8.2a9 9 0 1 0 11 0",
}
REBOOT_ICONS = {
    "system": "M16 6v9M10.5 9.2a9 9 0 1 0 11 0",
    "poweroff": "M8 7h16v18H8zM12 25v3M20 25v3M12 13h8",
    "recovery": "M16 5a11 11 0 1 0 0 22 11 11 0 0 0 0-22zM12 13l4-4 4 4M16 9v14",
    "bootloader": "M7 8h18v16H7zM11 13l4 3-4 3M17 19h4",
    "fastbootd": "M7 8h18v16H7zM11 19h10M11 14h6",
    "edl": "M9 6h14v20H9zM13 11h6M13 16h6M13 21h3",
}
TAB_ICONS = {
    "tab_general": TILE_ICONS["settings"],
    "tab_timezone": "M16 5a11 11 0 1 0 0 22 11 11 0 0 0 0-22zM16 10v6l4 2.5",
    "tab_display": ("M16 10.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM16 3.5v3M16 25.5v3M3.5 16h3"
                    "M25.5 16h3M7.2 7.2l2.1 2.1M22.7 22.7l2.1 2.1M7.2 24.8l2.1-2.1M22.7 9.3l2.1-2.1"),
    "tab_vibration": "M11.5 6h9v20h-9zM6.5 11v10M25.5 11v10M3 13.5v5M29 13.5v5",
    "tab_language": ("M16 5a11 11 0 1 0 0 22 11 11 0 0 0 0-22zM5 16h22M16 5c3 3 4.5 7 4.5 11"
                     "s-1.5 8-4.5 11c-3-3-4.5-7-4.5-11S13 8 16 5z"),
}
LOGO = ('<circle cx="17" cy="17" r="14.5" fill="none" stroke="{c}" stroke-width="{sw}"/>'
        '<path d="M11 13.5l6-5 6 5M17 8.5v17M11 20.5l6 5 6-5" fill="none" stroke="{c}" '
        'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')

# --------------------------------------------------------------------------
# Layout (panel px). Stock portrait_hdpi is 1080x1920 with 64 px rows; this
# theme is native 824x1648 (no runtime scaling), 54 px rows.
# --------------------------------------------------------------------------
STATUS_H = 60
HEADER_H = 240            # status 60 + header row 88 at y 88 + subtitle
ROW0, ROW = 240, 54
NAV_H = 112
NAV_Y = H - NAV_H         # 1536
NAV_BTN_Y = NAV_Y + NAV_H // 2
NAV_X = (199, 412, 625)   # space-around of 3 x 88 in 824 - 2*92 (mockup padding 46)
INDENT = 44               # mockup margin 22
CONTENT_W = W - 2 * INDENT
TITLE_CY = 132            # header row centre (88 + 44)
SUB_CY = 202
SLIDER_CY = 1436          # 128-high pill, bottom margin 36 above the nav bar
KB_KEY_H = 124
KB_Y = NAV_Y - 4 * KB_KEY_H
KB_TERM_H = 88
KB_TERM_Y = KB_Y - KB_TERM_H


def row(n):
    return ROW0 + (n - 1) * ROW


def build_images():
    # nav bar glyphs (22-unit viewBox, stroke 1.8 CSS) in 88x88 touch targets
    def nav(name, body):
        svg(name, 88, 88, f'<g transform="translate(22,22) scale(2)">{body}</g>')

    nav("back", f'<path d="M16 3.5L5 11l11 7.5z" fill="none" stroke="{INK}" stroke-width="1.8" stroke-linejoin="round"/>')
    nav("home", f'<circle cx="11" cy="11" r="8.5" fill="none" stroke="{INK}" stroke-width="1.8"/>')
    nav("console", f'<rect x="3.5" y="3.5" width="15" height="15" rx="2.5" fill="none" stroke="{INK}" stroke-width="1.8"/>')
    kb = (f'<path d="M2.5 3.5h17v10h-17zM6 7h.01M9.3 7h.01M12.7 7h.01M16 7h.01M7 10.5h8" fill="none" '
          f'stroke="{INK}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    nav("kb_hide", kb + f'<path d="M8 16.5l3 2.5 3-2.5" fill="none" stroke="{INK}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    nav("kb_show", kb + f'<path d="M8 19l3-2.5 3 2.5" fill="none" stroke="{INK}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    # header back chevron (Wipe/Install/Reboot mockups), 88x88
    svg("hdr_back", 88, 88, icon("M14 4l-7 7 7 7", 22, 22, 2, 2.2))
    # TWRP logo outline, 68x68 (34 CSS)
    svg("logo", 68, 68, f'<g transform="scale(2)">{LOGO.format(c=INK, sw=2.2)}</g>')
    svg("splashlogo", 272, 272, f'<g transform="scale(8)">{LOGO.format(c=INK, sw=1.4)}</g>')

    # home tiles: 132x132 outline r34 at the top of a 172x184 touch area
    for k, d in TILE_ICONS.items():
        svg("tile_" + k, 172, 184, rrect(20, 0, 132, 132, 34) + icon(d, 54, 34, 2, 2.2))
    # reboot tiles: 148x148 outline r38 in a 234x206 touch area
    for k, d in REBOOT_ICONS.items():
        svg("rtile_" + k, 234, 206, rrect(43, 0, 148, 148, 38) + icon(d, 85, 42, 2, 2.2))

    # stock button resources, redrawn as outlines (canvas = touch area)
    svg("main_button", 368, 243, rrect(8, 24, 352, 195, 32))
    svg("main_button_half_height", 368, 162, rrect(8, 29, 352, 104, 28))
    svg("main_button_half_height_full_width", 736, 162, rrect(8, 29, 720, 104, 28))
    svg("tab_3", 234, 108, rrect(4, 10, 226, 88, 24))
    svg("tab_4", 172, 108, rrect(4, 10, 164, 88, 24))
    svg("btn_half", 358, 96, rrect(0, 0, 358, 96, 28))
    svg("btn_half_filled", 358, 96, rrect(0, 0, 358, 96, 28, fill=True))
    # sort arrows sit on the right of a tab_3 sized button
    svg("sort_asc", 234, 108, icon("M5 13l6-6 6 6", 182, 32, 2, 2.2))
    svg("sort_desc", 234, 108, icon("M5 9l6 6 6-6", 182, 32, 2, 2.2))
    svg("sort_empty", 234, 108, "")

    # check boxes and radios: 40 px glyph in a 64x88 cell (88 px list rows)
    svg("checkbox_false", 64, 88, rrect(12, 24, 40, 40, 10))
    svg("checkbox_true", 64, 88, rrect(12, 24, 40, 40, 10, fill=True) +
        icon("M5 11.5l4 4 8-8.5", 21, 33, 1, 3.4, color=WHITE))
    svg("radio_false", 64, 88, f'<circle cx="32" cy="44" r="18" fill="none" stroke="{INK}" stroke-width="{SW}"/>')
    svg("radio_true", 64, 88, f'<circle cx="32" cy="44" r="18" fill="none" stroke="{INK}" stroke-width="{SW}"/>'
        f'<circle cx="32" cy="44" r="10" fill="{INK}"/>')
    # file list icons (24-unit viewBox, stroke 1.9) in 104x112 cells (112 px rows)
    svg("folder", 104, 112, icon("M3 6.5h6l2 2h10v10H3z", 32, 32, 2, 1.9))
    svg("file", 104, 112, icon("M6 3h8l4 4v14H6zM14 3v4h4", 32, 32, 2, 1.9))
    svg("list_spacer", 24, 88, "")
    # slidervalue thumb
    svg("handle", 56, 88, f'<circle cx="28" cy="44" r="20" fill="{INK}"/>')
    svg("fab_selectfolder", 160, 160, f'<circle cx="80" cy="80" r="64" fill="{INK}"/>' +
        icon("M5 11.5l4 4 8-8.5", 58, 58, 2, 2.4, color=WHITE))
    svg("unlock_icon", 262, 380, icon("M9 14V10a7 7 0 0 1 14 0v4M6 14h20v14H6zM16 19v4",
                                      51, 60, 5, 1.6))
    svg("cursor", 36, 36, f'<path d="M2 2l28 12-12 4-4 12z" fill="{INK}"/>')

    # progress bar: outlined pill, black fill (Backup mockup: 14 CSS high)
    svg("progress_empty", CONTENT_W, 28, rrect(0, 0, CONTENT_W, 28, 14))
    svg("progress_fill", CONTENT_W, 28, rrect(0, 0, CONTENT_W, 28, 14, fill=True))

    # swipe slider: outlined pill 736x128, solid round knob 100 with a chevron
    knob = (f'<circle cx="62" cy="50" r="50" fill="{INK}"/>' +
            icon("M8 4l7 7-7 7", 40, 28, 2, 2.4, color=WHITE))
    svg("slider", CONTENT_W, 128, rrect(0, 0, CONTENT_W, 128, 64))
    svg("slider_used", CONTENT_W, 128, rrect(0, 0, CONTENT_W, 128, 64))
    svg("slider_touch", 124, 100, knob)
    svg("slider_hint", CONTENT_W, 128, rrect(0, 0, CONTENT_W, 128, 64) +
        f'<g transform="translate(0,14)">{knob}</g>')

    # settings tabs: 48 px icons in 165x88 cells
    for k, d in TAB_ICONS.items():
        svg(k, 165, 88, icon(d, 58.5, 20, 1.5, 2.2))

    # keyboard key glyphs
    def keyglyph(name, w, h, d, sz=48, fill="none"):
        sc = sz / 22.0
        svg(name, w, h, icon(d, (w - sz) / 2, (h - sz) / 2, sc, 1.8, fill=fill))

    keyglyph("backspace", 124, 124, "M8 5h11v12H8l-5-6zM11 8.5l5 5M16 8.5l-5 5")
    keyglyph("enter", 124, 124, "M18 5v6H5M8.5 7.5L5 11l3.5 3.5")
    keyglyph("shift", 124, 124, "M11 4l7 7h-4v6H8v-6H4z")
    keyglyph("shift_fill", 124, 124, "M11 4l7 7h-4v6H8v-6H4z", fill=INK)
    svg("space", 410, 124, icon("M0 0v8h120V0", 145, 54, 1, 4))
    keyglyph("kb_arrow_left", 117, 88, "M13.5 5l-6 6 6 6", 40)
    keyglyph("kb_arrow_right", 117, 88, "M8.5 5l6 6-6 6", 40)
    keyglyph("kb_arrow_up", 117, 88, "M5 13.5l6-6 6 6", 40)
    keyglyph("kb_arrow_down", 117, 88, "M5 8.5l6 6 6-6", 40)

    # info icon (Reboot mockup), 44x44
    svg("info", 44, 44, f'<g transform="scale(2)"><circle cx="11" cy="11" r="8.5" fill="none" stroke="{INK}" '
        f'stroke-width="1.8"/><path d="M11 6.5v5.5M11 15v0.5" stroke="{INK}" stroke-width="2" '
        'stroke-linecap="round"/></g>')
    # slot chips (40x32 CSS)
    svg("chip_slot_on", 80, 64, rrect(0, 0, 80, 64, 32, fill=True))
    svg("chip_slot_off", 80, 64, rrect(0, 0, 80, 64, 32))
    frame("frame_console", CONTENT_W, 15 * ROW)


def frame(name, w, h, r=32):
    svg(name, w, h, rrect(0, 0, w, h, r))


def chip(label):
    w = max(120, met("font_chip").width(label) + 64)
    on, off = f"chip_on_{w}", f"chip_off_{w}"
    svg(on, w, 80, rrect(0, 0, w, 80, 40, fill=True))
    svg(off, w, 80, rrect(0, 0, w, 80, 40))
    return w, on, off


def write_images():
    d = os.path.join(OUT, "images")
    os.makedirs(d, exist_ok=True)
    for name, (w, h, body) in sorted(IMAGES.items()):
        doc = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
               f'viewBox="0 0 {w} {h}">{body}</svg>')
        cairosvg.svg2png(bytestring=doc.encode(), write_to=os.path.join(d, name + ".png"),
                         output_width=w, output_height=h)


# --------------------------------------------------------------------------
# XML helpers
# --------------------------------------------------------------------------
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def text(t, font, x, cy, color="%text_color%", placement=None, cond=""):
    pl = f' placement="{placement}"' if placement is not None else ""
    return (f'\t\t\t<text color="{color}">\n{cond}\t\t\t\t<font resource="{font}"/>\n'
            f'\t\t\t\t<placement x="{x}" y="{ty(font, cy)}"{pl}/>\n'
            f'\t\t\t\t<text>{t}</text>\n\t\t\t</text>\n\n')


def image(res, x, y, cond="", placement=None):
    pl = f' placement="{placement}"' if placement is not None else ""
    return (f'\t\t\t<image>\n{cond}\t\t\t\t<image resource="{res}"/>\n'
            f'\t\t\t\t<placement x="{x}" y="{y}"{pl}/>\n\t\t\t</image>\n\n')


def c(var, val, op=None):
    o = f' op="{op}"' if op else ""
    return f'\t\t\t\t<condition var1="{var}"{o} var2="{val}"/>\n'


def acts(*a):
    body = "".join(f'\t\t\t\t\t<action function="{f}">{v}</action>\n' if v is not None
                   else f'\t\t\t\t\t<action function="{f}"/>\n' for f, v in a)
    return f"\t\t\t\t<actions>\n{body}\t\t\t\t</actions>\n"


def button(res, x, y, actions, cond="", label=None, font="font_m", color="%text_color%"):
    t = ""
    if label is not None:
        t = f'\t\t\t\t<font resource="{font}" color="{color}"/>\n\t\t\t\t<text>{label}</text>\n'
    return (f'\t\t\t<button>\n{cond}\t\t\t\t<placement x="{x}" y="{y}"/>\n'
            f'\t\t\t\t<image resource="{res}"/>\n{t}{actions}\t\t\t</button>\n\n')


def keys(back, home):
    return (f'\t\t\t<action>\n\t\t\t\t<touch key="back"/>\n{back}\t\t\t</action>\n\n'
            f'\t\t\t<action>\n\t\t\t\t<touch key="home"/>\n{home}\t\t\t</action>\n')


def one(f, v):
    return f'\t\t\t\t<action function="{f}">{v}</action>\n'


# --------------------------------------------------------------------------
# ui.xml
# --------------------------------------------------------------------------
def variables():
    v = []

    def add(n, val, extra=""):
        v.append(f'\t\t<variable name="{n}" value="{val}"{extra}/>')

    add("tw_samsung_navbar", 0, ' persist="1"')
    # E Ink: one full (GC16) refresh after each page change; Settings > Screen
    add("tw_eink_page_refresh", 1, ' persist="1"')
    add("tw_ink_hide_log", 0)
    add("tw_hide_kb", 0)
    add("screen_width", W)
    add("screen_height", H)
    add("status_height", STATUS_H)
    add("header_height", HEADER_H)
    add("navbar_height", NAV_H)
    add("content_width", CONTENT_W)
    add("content_overlay_width", W - 4 * INDENT)
    add("dialog_height", 11 * ROW)
    add("dialog_list_y", row(5) + 24)        # below the frame stroke, inside its corner radius
    add("back_button_x", NAV_X[0])
    add("console_button_x", NAV_X[2])
    add("indent", INDENT)
    add("col1_x_left", 2 * INDENT)
    add("col1_x_header", 128)
    # subtitles under a page title start at the page margin, as in the design
    # (mockup 26 px x 2), not under the title after the back chevron
    add("col1_x_sub", 52)
    add("center_x", W // 2)
    add("col1_x_right", W // 2 + INDENT)
    add("indent_right", W - INDENT)
    add("tab_height", 88)
    add("tab_indicator_height", 4)
    add("tab_y", ROW0 + 44)
    add("tab3_width", 275)
    add("tab4_width", 206)
    add("tab5_width", 165)
    add("tab3_col2_x", 275)
    add("tab3_col3_x", 549)
    add("tab4_col2_x", 206)
    add("tab4_col4_x", 618)
    add("tab5_col2_x", 165)
    add("tab5_col3_x", 330)
    add("tab5_col4_x", 494)
    add("tab5_col5_x", 659)
    add("tab5_centered_col1_x", 82)
    add("tab5_centered_col2_x", 247)
    add("tab5_centered_col4_x", 577)
    add("tab5_centered_col5_x", 742)
    add("btn3_col2_x", 295)
    add("btn3_col3_x", 546)
    add("btn4_col2_x", 232)
    add("btn4_col3_x", 420)
    add("btn4_col4_x", 608)
    status_top = ty("font_status", STATUS_H // 2)
    add("status_topalign_header_y", status_top)
    add("status_centeralign_header_y", status_top)
    add("status_bottomalign_header_y", status_top)
    add("row1_header_y", status_top)
    add("row2_header_y", STATUS_H)
    add("row3_header_y", ty("font_l", TITLE_CY))
    add("row4_header_y", ty("font_m", SUB_CY))
    add("hdr_back_x", 28)
    add("hdr_back_y", TITLE_CY - 44)
    add("row1_y", row(1))
    add("row1a_y", row(1) + ROW // 2)
    add("row2_y", row(2))
    add("row2a_y", row(2) + ROW // 2)
    add("row_tab_y", ROW0 + 88 - 4)
    add("row2_input_y", row(2) + 51)
    add("row3_y", row(3))
    add("row3_input_y", row(3) + 24)
    add("row3a_y", row(3) + ROW // 2)
    add("row4_y", row(4))
    add("row4_input_y", row(4) + 24)
    add("row4a_y", row(4) + ROW // 2)
    for n in range(5, 25):
        add(f"row{n}_y", row(n))
        add(f"row{n}a_y", row(n) + ROW // 2)
    add("row25_y", NAV_Y)
    add("navbar_y", NAV_Y)
    add("navbar_btn_y", NAV_BTN_Y)
    add("slider_y", SLIDER_CY)
    add("keyboard_y", KB_Y)
    add("keyboard_terminal_y", KB_TERM_Y)
    # palette: white ground, ink, one secondary grey for secondary TEXT only
    add("background_color", WHITE)
    add("accent_color", INK)
    add("accent_color_semitransparent", INK)
    add("text_color", INK)
    add("text_muted_color", MUTED)
    add("text_button_color", INK)
    add("text_success_color", INK)
    add("text_fail_color", INK)
    add("button_text_color", INK)
    add("highlight_color", INK)
    add("caps_highlight_color", INK)
    add("transparent", "#00000000")
    add("semi_transparent", WHITE)    # overlays hide the page instead of dimming it
    add("warning", INK)
    add("error", INK)
    add("highlight", INK)
    add("fileselector_linecolor", INK)
    add("fileselector_highlight_color", INK)
    add("fileselector_highlight_font_color", WHITE)
    add("fileselector_separatorheight", 3)
    add("fileselector_spacing", 0)
    add("fileselector_install_height", 18 * ROW)
    add("fileselector_filemanager_height", 1161)
    add("partitionlist_spacing", 0)
    add("partitionlist_storage_height", 459)
    add("partitionlist_flashimage_height", 459)
    add("partitionlist_wipe_height", 918)
    add("partitionlist_mount_height", 702)
    add("partitionlist_backup_height", 648)
    add("listbox_timezone_height", 638)
    add("listbox_settings_height", 810)
    add("listbox_advanced_height", 591)
    add("listbox_options_height", 324)
    add("fastscroll_w", 32)
    add("fastscroll_linew", 3)
    add("fastscroll_rectw", 24)
    add("fastscroll_recth", 92)
    add("slidervalue_lineh", 4)
    add("slidervalue_padding", 0)
    add("slidervalue_sliderw", 56)
    add("slidervalue_sliderh", 88)
    add("slideout_height", NAV_Y - ty("font_l", TITLE_CY) - 16)
    add("slideout_bg_height", NAV_Y - STATUS_H)
    add("input_height", ROW)
    add("input_line_width", SW)
    add("console_height", 15 * ROW)
    add("console_terminal_height", KB_TERM_Y - ty("font_l", TITLE_CY) - 8)
    add("terminal_x", INDENT)                 # clear of the glass's rounded edge
    add("terminal_y", ty("font_l", TITLE_CY))
    add("terminal_w", CONTENT_W)
    add("dialog_button_x", W - INDENT - 24 - 234)
    add("pattern_x", 96)
    add("pattern_dot_dia", 26)
    add("pattern_line_w", 9)
    add("pattern_size", 632)
    add("tw_clock_12_pos_x", 0)
    add("tw_clock_24_pos_x", 0)
    add("tw_cpu_pos_x", 0)
    add("tw_battery_pos_x", 0)
    return "\n".join(v)


def status_bar():
    y = "%row1_header_y%"
    s = ""
    s += (f'\t\t\t<text color="%text_color%">\n{c("tw_no_cpu_temp", 1)}\t\t\t\t<font resource="font_status"/>\n'
          f'\t\t\t\t<placement x="36" y="{y}"/>\n\t\t\t\t<text>TWRP %tw_version%</text>\n\t\t\t</text>\n\n')
    s += (f'\t\t\t<text color="%text_color%">\n{c("tw_no_cpu_temp", 0)}\t\t\t\t<font resource="font_status"/>\n'
          f'\t\t\t\t<placement x="36" y="{y}"/>\n\t\t\t\t<text>CPU %tw_cpu_temp% °C</text>\n\t\t\t</text>\n\n')
    bat = ('\t\t\t\t<conditions>\n\t\t\t\t\t<condition var1="tw_no_battery_percent" var2="0"/>\n'
           '\t\t\t\t\t<condition var1="tw_battery" op="&gt;" var2="0"/>\n'
           '\t\t\t\t\t<condition var1="tw_battery" op="&lt;" var2="101"/>\n\t\t\t\t</conditions>\n')
    nobat = ('\t\t\t\t<conditions>\n\t\t\t\t\t<condition var1="tw_no_battery_percent" var2="1"/>\n'
             '\t\t\t\t</conditions>\n')
    s += (f'\t\t\t<text color="%text_color%">\n{bat}\t\t\t\t<font resource="font_status"/>\n'
          f'\t\t\t\t<placement x="{W - 36}" y="{y}" placement="1"/>\n'
          f'\t\t\t\t<text>%tw_time% · %tw_battery%</text>\n\t\t\t</text>\n\n')
    s += (f'\t\t\t<text color="%text_color%">\n{nobat}\t\t\t\t<font resource="font_status"/>\n'
          f'\t\t\t\t<placement x="{W - 36}" y="{y}" placement="1"/>\n'
          f'\t\t\t\t<text>%tw_time%</text>\n\t\t\t</text>\n\n')
    # tw_simulate_actions: stock paints the status bar red; here a 4 px ink rule
    s += (f'\t\t\t<fill color="%text_color%">\n{c("tw_simulate_actions", 1)}'
          f'\t\t\t\t<placement x="0" y="{STATUS_H - 4}" w="%screen_width%" h="4"/>\n\t\t\t</fill>\n\n')
    return s


def navbar():
    def b(xvar, res, act, extra=""):
        return (f'\t\t\t<button>\n{extra}\t\t\t\t<placement x="%{xvar}%" y="%navbar_btn_y%" placement="4"/>\n'
                f'\t\t\t\t<image resource="{res}"/>\n{c("tw_busy", 0)}{act}\t\t\t</button>\n\n')
    key = lambda k: f'\t\t\t\t<action function="key">{k}</action>\n'
    ovl = '\t\t\t\t<action function="overlay">slideout</action>\n'
    s = b("back_button_x", "back", key("back"), c("tw_samsung_navbar", 1, "!="))
    s += b("back_button_x", "console", ovl, c("tw_samsung_navbar", 1, "="))
    s += b("center_x", "home", key("home"))
    s += b("console_button_x", "console", ovl, c("tw_samsung_navbar", 1, "!="))
    s += b("console_button_x", "back", key("back"), c("tw_samsung_navbar", 1, "="))
    s += ('\t\t\t<action>\n\t\t\t\t<touch key="power"/>\n\t\t\t\t<action function="togglebacklight"/>\n'
          '\t\t\t</action>\n\n\t\t\t<action>\n\t\t\t\t<touch key="power+voldown"/>\n'
          '\t\t\t\t<action function="screenshot"/>\n\t\t\t</action>\n')
    return s


def keyboard_templates():
    k = []
    common = ('\t\t\t\t<keymargin x="2" y="2"/>\n'
              f'\t\t\t\t<background color="{INK}"/>\n'
              f'\t\t\t\t<key-alphanumeric color="{WHITE}" font="keylabel" textcolor="{INK}"/>\n'
              f'\t\t\t\t<key-other color="{WHITE}" font="keylabel-small" textcolor="{INK}"/>\n'
              f'\t\t\t\t<longpress font="keylabel-longpress" textcolor="{MUTED}" x="10" y="2"/>\n')
    k.append(f'''		<template name="keyboardterminaltemplate">
			<keyboard>
				<condition var1="tw_hide_kb" var2="0"/>
				<placement x="2" y="%keyboard_terminal_y%" w="820" h="{KB_TERM_H}"/>
{common}				<keylabel key="0:k:29" text="Ctrl"/>
				<keylabel key="0:c:27" text="Esc"/>
				<keylabel key="0:c:9" text="Tab"/>
				<keylabel key="0:k:105" text="&lt;" resource="kb_arrow_left"/>
				<keylabel key="0:k:108" text="v" resource="kb_arrow_down"/>
				<keylabel key="0:k:103" text="^" resource="kb_arrow_up"/>
				<keylabel key="0:k:106" text="&gt;" resource="kb_arrow_right"/>
				<highlight color="%highlight_color%"/>
				<ctrlhighlight color="%highlight_color%"/>
				<layout1>
					<keysize height="{KB_TERM_H}" width="117"/>
					<row1 key01="118:k:29" key02="118:c:27" long02=":c:3" key03="117:c:9" key04="117:k:105" key05="117:k:108" key06="117:k:103" key07="116:k:106"/>
				</layout1>
			</keyboard>
		</template>
''')
    rows = '''				<layout1>
					<keysize height="{h}" width="82"/>
					<row1 key01="q" long01="1" key02="w" long02="2" key03="e" long03="3" key04="r" long04="4" key05="t" long05="5" key06="y" long06="6" key07="u" long07="7" key08="i" long08="8" key09="o" long09="9" key10="p" long10="0"/>
					<row2 key01="41:" key02="a" long02="@" key03="s" long03="#" key04="d" long04="$" key05="f" long05="%" key06="g" long06="&amp;" key07="h" long07="*" key08="j" long08="-" key09="k" long09="+" key10="l" long10="_" key11="41:"/>
					<row3 key01="123:layout2" key02="z" long02="!" key03="x" long03="&quot;" key04="c" long04="'" key05="v" long05=":" key06="b" long06=";" key07="n" long07="/" key08="m" long08="?" key09="123:c:8"/>
					<row4 key01="123:layout3" key02="/" key03="410: " key04="." key05="123:action"/>
					<keylabel key="0:layout2" text="Shift" resource="shift"/>
					<keylabel key="0:layout3" text="?123"/>
				</layout1>
				<layout2>
					<keysize height="{h}" width="82" capslock="0" revert_layout="1"/>
					<row1 key01="Q" long01="1" key02="W" long02="2" key03="E" long03="3" key04="R" long04="4" key05="T" long05="5" key06="Y" long06="6" key07="U" long07="7" key08="I" long08="8" key09="O" long09="9" key10="P" long10="0"/>
					<row2 key01="41:" key02="A" long02="@" key03="S" long03="#" key04="D" long04="$" key05="F" long05="%" key06="G" long06="&amp;" key07="H" long07="*" key08="J" long08="-" key09="K" long09="+" key10="L" long10="_" key11="41:"/>
					<row3 key01="123:layout1" key02="Z" long02="!" key03="X" long03="&quot;" key04="C" long04="'" key05="V" long05=":" key06="B" long06=";" key07="N" long07="/" key08="M" long08="?" key09="123:c:8"/>
					<row4 key01="123:layout3" key02="/" key03="410: " key04="." key05="123:action"/>
					<keylabel key="0:layout1" text="Shift" resource="shift_fill"/>
					<keylabel key="0:layout3" text="?123"/>
				</layout2>
				<layout3>
					<keysize height="{h}" width="82"/>
					<row1 key01="1" key02="2" key03="3" key04="4" key05="5" key06="6" key07="7" key08="8" key09="9" key10="0"/>
					<row2 key01="@" key02="#" key03="$" key04="%" key05="&amp;" key06="*" key07="-" key08="+" key09="(" key10=")"/>
					<row3 key01="123:layout4" key02="!" key03="82:c:34" key04="'" key05=":" key06=";" key07="/" key08="?" key09="123:c:8"/>
					<row4 key01="123:layout1" key02="," key03="410: " key04="." key05="123:action"/>
					<keylabel key="0:layout1" text="ABC"/>
					<keylabel key="0:layout4" text="~\\{{"/>
				</layout3>
				<layout4>
					<keysize height="{h}" width="82"/>
					<row1 key01="~" key02="`" key03="|" key04="82:" key05="82:" key06="82:" key07="%" key08="82:" key09="{{" key10="}}"/>
					<row2 key01="82:" key02="82:" key03="82:" key04="82:" key05="82:" key06="^" key07="_" key08="=" key09="[" key10="]"/>
					<row3 key01="123:layout3" key02="82:" key03="82:" key04="82:" key05="82:" key06="\\" key07="&lt;" key08="&gt;" key09="123:c:8"/>
					<row4 key01="123:layout1" key02="82:c:34" key03="410: " key04="." key05="123:action"/>
					<keylabel key="0:layout1" text="ABC"/>
					<keylabel key="0:layout3" text="?123"/>
				</layout4>
'''.format(h=KB_KEY_H)
    labels = ('\t\t\t\t<keylabel key="0:c:8" text="Bksp" resource="backspace"/>\n'
              '\t\t\t\t<keylabel key="0:action" text="Enter" resource="enter"/>\n'
              '\t\t\t\t<keylabel key=" " text="Space" resource="space"/>\n'
              '\t\t\t\t<highlight color="%highlight_color%"/>\n'
              '\t\t\t\t<capshighlight color="%caps_highlight_color%"/>\n')
    k.append(f'''		<template name="keyboardtemplate">
			<keyboard>
				<condition var1="tw_hide_kb" var2="0"/>
				<placement x="2" y="%keyboard_y%" w="820" h="{4 * KB_KEY_H}"/>
{common}{labels}{rows}			</keyboard>
		</template>
''')
    k.append(f'''		<template name="keyboardnum">
			<keyboard>
				<condition var1="tw_hide_kb" var2="0"/>
				<placement x="2" y="%keyboard_y%" w="820" h="{4 * KB_KEY_H}"/>
{common}{labels}				<layout1>
					<keysize height="{KB_KEY_H}" width="158"/>
					<row1 key01="173:" key02="1" key03="2" key04="3" key05="173:"/>
					<row2 key01="173:" key02="4" key03="5" key04="6" key05="173:"/>
					<row3 key01="173:" key02="7" key03="8" key04="9" key05="173:"/>
					<row4 key01="173:" key02="158:c:8" key03="0" key04="158:action" key05="173:"/>
				</layout1>
			</keyboard>
		</template>
''')
    return "".join(k)


def sort_options():
    # row1_y, not row1a_y: the 108 px tab image placed at row1a_y (267) reached
    # 375 and the file list starting at row3_y (348) painted over its bottom
    # (cut-off sort buttons on Restore, seen on the phone 2026-10-14)
    y = "%row1_y%"
    out = ""
    for x in ("%indent%", "%btn3_col2_x%", "%btn3_col3_x%"):
        out += f'\t\t\t<image>\n\t\t\t\t<placement x="{x}" y="{y}"/>\n\t\t\t\t<image resource="tab_3"/>\n\t\t\t</image>\n\n'
    for n, x, label in ((1, "%indent%", "{@sort_by_name_only=Name}"),
                        (2, "%btn3_col2_x%", "{@sort_by_date_only=Date}"),
                        (3, "%btn3_col3_x%", "{@sort_by_size_only=Size}")):
        for cond, img, nxt in ((c("tw_gui_sort_order", n, "="), "sort_asc", -n),
                               (c("tw_gui_sort_order", -n, "="), "sort_desc", n),
                               (f'\t\t\t\t<conditions>\n\t{c("tw_gui_sort_order", n, "!=")}\t{c("tw_gui_sort_order", -n, "!=")}\t\t\t\t</conditions>\n', "sort_empty", n)):
            out += (f'\t\t\t<button>\n{cond}\t\t\t\t<placement x="{x}" y="{y}"/>\n'
                    f'\t\t\t\t<font resource="font_s" color="%text_button_color%"/>\n'
                    f'\t\t\t\t<text>{label}</text>\n\t\t\t\t<image resource="{img}"/>\n'
                    f'\t\t\t\t<action function="set">tw_gui_sort_order={nxt}</action>\n\t\t\t</button>\n\n')
    return out


def tabs(name, items):
    out = f'\t\t<template name="{name}">\n'
    # a hairline under the tab row; the page draws the 4 px indicator itself
    out += ('\t\t\t<fill color="%text_color%">\n\t\t\t\t<placement x="0" y="%row_tab_y%" '
            'w="%screen_width%" h="1"/>\n\t\t\t</fill>\n\n')
    out += items
    out += "\t\t</template>\n\n"
    return out


def ui_xml():
    fonts = "\n".join(f'\t\t<font name="{n}" filename="{f}" size="{tw_size(px)}"/>'
                      for n, (f, px) in FONTS.items())
    imgs = sorted(IMAGES)
    retain = {"logo", "fab_selectfolder", "file", "folder", "unlock_icon", "home", "back", "console",
              "kb_hide", "kb_show", "checkbox_false", "checkbox_true", "radio_false", "radio_true",
              "cursor", "backspace", "enter", "shift", "shift_fill", "space", "kb_arrow_left",
              "kb_arrow_right", "kb_arrow_up", "kb_arrow_down"}
    res = []
    for n in imgs:
        if n in ("splashlogo",):
            continue
        r = ' retainaspect="1"' if n in retain else ""
        res.append(f'\t\t<image name="{n}" filename="{n}"{r}/>')
    res.append('\t\t<image name="progress_full" filename="progress_fill"/>')
    images = "\n".join(res)

    header_back = (f'\t\t\t<button>\n{c("tw_busy", 0)}\t\t\t\t<placement x="%hdr_back_x%" y="%hdr_back_y%"/>\n'
                   '\t\t\t\t<image resource="hdr_back"/>\n\t\t\t\t<action function="key">back</action>\n'
                   '\t\t\t</button>\n\n')
    base_top = '\t\t\t<background color="%background_color%"/>\n\n' + status_bar()

    tabs_backup = tabs("tabs_backup", (
        '\t\t\t<button style="tab">\n\t\t\t\t<placement x="0" y="%row1_y%" w="%tab3_width%" h="%tab_height%"/>\n'
        '\t\t\t\t<text>{@tab_backup=BACKUP}</text>\n\t\t\t\t<action function="page">backup</action>\n\t\t\t</button>\n\n'
        '\t\t\t<button style="tab">\n\t\t\t\t<placement x="%tab3_col2_x%" y="%row1_y%" w="%tab3_width%" h="%tab_height%"/>\n'
        '\t\t\t\t<text>{@tab_options=OPTIONS}</text>\n\t\t\t\t<action function="page">backup_options</action>\n\t\t\t</button>\n\n'),
        )
    tab_items = ""
    for x, img, page in (("%tab5_centered_col1_x%", "tab_general", "settings"),
                         ("%tab5_centered_col2_x%", "tab_timezone", "settings_timezone"),
                         ("%center_x%", "tab_display", "settings_screen"),
                         ("%tab5_centered_col4_x%", "tab_vibration", "settings_vibration"),
                         ("%tab5_centered_col5_x%", "tab_language", "settings_language")):
        tab_items += (f'\t\t\t<button style="tab">\n\t\t\t\t<placement x="{x}" y="%tab_y%" placement="4"/>\n'
                      f'\t\t\t\t<image resource="{img}"/>\n\t\t\t\t<action function="page">{page}</action>\n\t\t\t</button>\n\n')
    tabs_settings = tabs("tabs_settings", tab_items)

    console_frame = image("frame_console", "%indent%", "%row2_y%")
    cons_x, cons_y = INDENT + 20, row(2) + 16

    return f'''<?xml version="1.0"?>
<!-- Generated by device/hisense/HLTE556N/theme/gen_theme.py. Do not edit. -->
<recovery>
	<details>
		<resolution width="{W}" height="{H}"/>
		<author>Hisense A9 (HLTE556N) device tree</author>
		<title>Ink</title>
		<description>Monochrome outline theme for the 824x1648 E Ink panel</description>
		<preview>preview.png</preview>
		<themeversion>{THEME_VERSION}</themeversion>
	</details>

	<include>
		<xmlfile name="portrait.xml"/>
	</include>

	<resources>
{fonts}

{images}
	</resources>

	<variables>
{variables()}
	</variables>

	<mousecursor>
		<placement w="36" h="36"/>
		<background color="{INK}" resource="cursor"/>
		<speed multiplier="2.5"/>
	</mousecursor>

	<templates>
		<template name="page">
{base_top}{header_back}{navbar()}		</template>

		<template name="page_home">
{base_top}{navbar()}		</template>

		<template name="progress_bar">
			<progressbar>
				<placement x="%indent%" y="%row17a_y%"/>
				<resource empty="progress_empty" full="progress_full"/>
				<data name="ui_progress"/>
			</progressbar>
		</template>

		<template name="sort_options">
{sort_options()}		</template>

{tabs_backup}{tabs_settings}		<template name="console">
{console_frame}			<console>
				<placement x="{cons_x}" y="{cons_y}" w="{CONTENT_W - 40}" h="{15 * ROW - 32}"/>
			</console>
		</template>

		<template name="console_terminal">
{console_frame}			<console>
				<placement x="{cons_x}" y="{cons_y}" w="{CONTENT_W - 40}" h="{15 * ROW - 32}"/>
			</console>
		</template>

{keyboard_templates()}	</templates>
</recovery>
'''


# --------------------------------------------------------------------------
# portrait.xml: styles + the five designed pages; everything else from stock
# --------------------------------------------------------------------------
def styles():
    fs = ('<fastscroll linecolor="%fileselector_linecolor%" rectcolor="%accent_color%" w="%fastscroll_w%" '
          'linew="%fastscroll_linew%" rectw="%fastscroll_rectw%" recth="%fastscroll_recth%"/>')
    hdr = ('<header background="%background_color%" textcolor="%accent_color%" separatorcolor="%accent_color%" '
           'separatorheight="%fileselector_separatorheight%"/>')
    sep = '<separator color="%fileselector_linecolor%" height="%fileselector_separatorheight%"/>'
    dims = ('<dimensions lineh="%slidervalue_lineh%" linepadding="%slidervalue_padding%" '
            'sliderw="%slidervalue_sliderw%" sliderh="%slidervalue_sliderh%"/>')
    bg = '<background color="%background_color%"/>'
    hl = '<highlight color="%fileselector_highlight_color%"/>'
    lf = ('<font resource="font_m" spacing="%fileselector_spacing%" color="%text_color%" '
          'highlightcolor="%fileselector_highlight_font_color%"/>')
    pf = ('<font resource="font_m" spacing="%partitionlist_spacing%" color="%text_color%" '
          'highlightcolor="%fileselector_highlight_font_color%"/>')

    def st(name, *lines):
        body = "".join(f"\t\t\t{l}\n" for l in lines)
        return f'\t\t<style name="{name}">\n{body}\t\t</style>\n\n'

    # No <highlight> on buttons: on E Ink a press flash is an extra panel update
    # right before the page change that the press causes anyway.
    return ("\t<styles>\n" +
            st("text_l", '<font resource="font_l" color="%text_color%"/>') +
            st("text_m", '<font resource="font_m" color="%text_color%"/>') +
            st("text_m_accent", '<font resource="font_m" color="%accent_color%"/>') +
            st("text_m_fail", '<font resource="font_m_bold" color="%text_fail_color%"/>') +
            st("text_s", '<font resource="font_s" color="%text_color%"/>') +
            st("text_muted", '<font resource="font_s" color="%text_muted_color%"/>') +
            st("input", bg, '<cursor color="%accent_color%" hasfocus="1" width="%input_line_width%"/>',
               '<font resource="font_m" color="%text_color%"/>') +
            st("checkbox", '<font resource="font_m" color="%text_color%"/>',
               '<image checked="checkbox_true" unchecked="checkbox_false"/>') +
            st("main_button", '<font resource="font_m" color="%text_button_color%"/>', '<image resource="main_button"/>') +
            st("main_button_half_height", '<font resource="font_m" color="%text_button_color%"/>',
               '<image resource="main_button_half_height"/>') +
            st("main_button_half_height_full_width", '<font resource="font_m" color="%text_button_color%"/>',
               '<image resource="main_button_half_height_full_width"/>') +
            st("button_third_width", '<font resource="font_m" color="%text_button_color%"/>', '<image resource="tab_3"/>') +
            st("button_quarter_width", '<font resource="font_m" color="%text_button_color%"/>', '<image resource="tab_4"/>') +
            st("fab", '<placement x="%indent_right%" y="%row21a_y%" placement="1"/>',
               '<font resource="font_m" color="%button_text_color%"/>') +
            st("tab", '<fill color="%transparent%"/>', '<font resource="font_s" color="%text_button_color%"/>') +
            st("console", '<fastscroll rectcolor="%accent_color%" w="%fastscroll_w%" rectw="%fastscroll_rectw%" recth="%fastscroll_recth%"/>',
               '<color foreground="%text_color%" background="%background_color%" scroll="%background_color%"/>',
               '<font resource="fixed"/>') +
            st("terminal", '<fastscroll linecolor="%transparent%" rectcolor="%accent_color%" w="%fastscroll_w%" rectw="%fastscroll_rectw%" recth="%fastscroll_recth%"/>',
               bg, '<font resource="fixed" spacing="3" color="%text_color%"/>') +
            st("fileselector", hl, hdr, fs, sep, '<sort name="tw_gui_sort_order"/>',
               '<icon folder="folder" file="file"/>', bg, lf) +
            # Install's list has no title: a <header> always takes a row (scrolllist.cpp),
            # so it gets a style without one instead of an empty band
            st("fileselector_nohdr", hl, fs, sep, '<sort name="tw_gui_sort_order"/>',
               '<icon folder="folder" file="file"/>', bg, lf) +
            st("listbox", hl, hdr, fs, sep, '<icon selected="radio_true" unselected="radio_false"/>', bg, lf) +
            st("scrolllist", bg, '<font resource="font_m" spacing="%fileselector_spacing%" color="%text_color%"/>', fs) +
            st("partitionlist", hl, hdr, fs, dims, '<icon selected="checkbox_true" unselected="checkbox_false"/>', sep, bg, pf) +
            st("partitionlist_storage", hl,
               '<placement x="%col1_x_left%" y="%row5_y%" w="%content_overlay_width%" h="%partitionlist_storage_height%"/>',
               hdr, fs, dims, '<icon selected="radio_true" unselected="radio_false"/>', sep, bg, pf) +
            st("advanced_listbox", hl, fs, sep, dims, '<icon selected="list_spacer" unselected="list_spacer"/>', bg, lf) +
            st("options_listbox", hl, fs, '<separator color="%background_color%" height="%fileselector_separatorheight%"/>',
               dims, bg, lf) +
            st("slider", '<placement x="%center_x%" y="%slider_y%"/>', '<font resource="font_m" color="%text_color%"/>',
               '<resource base="slider" used="slider_used" touch="slider_touch"/>') +
            st("slidervalue", '<resource handle="handle"/>', '<font resource="font_m" color="%text_color%"/>',
               '<colors line="%fileselector_linecolor%"/>', dims) +
            st("patternpassword", '<size name="tw_gui_pattern_grid_size" default="3"/>') +
            "\t</styles>\n")


def nav_keys_main():
    return keys(one("page", "main"), one("page", "main"))


def page_main2():
    p = '\t\t<page name="main2">\n\t\t\t<template name="page_home"/>\n\n'
    p += image("logo", 52, 104)
    p += text("{@rb_recovery_btn=Recovery}", "font_home", 148, 124)
    p += text("TWRP %tw_version% · Hisense A9", "font_xs", 148, 160, color="%text_muted_color%")
    tiles = [
        ("install", "{@install_btn=Install}", acts(("queueclear", None), ("set", "tw_selectimage=0"), ("page", "install"))),
        ("wipe", "{@wipe_btn=Wipe}", acts(("page", "wipe"))),
        ("backup", "{@backup_btn=Backup}", acts(("page", "backup"))),
        ("restore", "{@restore_btn=Restore}", acts(("page", "restore"))),
        ("mount", "{@mount_btn=Mount}", acts(("page", "mount"))),
        ("settings", "{@settings_btn=Settings}", acts(("page", "settings"))),
        ("advanced", "{@advanced_btn=Advanced}", acts(("page", "advanced"))),
        ("reboot", "{@reboot_btn=Reboot}", acts(("page", "reboot"))),
    ]
    cols = (130, 318, 506, 694)
    for i, (k, label, a) in enumerate(tiles):
        cx, y = cols[i % 4], (220, 456)[i // 4]
        p += button("tile_" + k, cx - 86, y, a)
        p += text(label, "font_label", cx, y + 164, placement=5)

    # status card: fields only where TWRP has a variable (no "System": TWRP
    # keeps no variable for the installed ROM)
    card_y, card_h = 708, 212
    frame("card_home", CONTENT_W, card_h)
    p += image("card_home", INDENT, card_y)
    l1, l2 = 76, 424
    r1l, r1v, r2l, r2v = card_y + 44, card_y + 80, card_y + 132, card_y + 168
    mute = "%text_muted_color%"
    p += text("Data", "font_xs", l1, r1l, color=mute)
    p += text("Decrypted", "font_status", l1, r1v, cond=c("tw_is_decrypted", 1))
    p += text("Encrypted", "font_status", l1, r1v,
              cond=c("tw_is_decrypted", 0) + c("tw_is_encrypted", 1))
    p += text("Not encrypted", "font_status", l1, r1v,
              cond=c("tw_is_decrypted", 0) + c("tw_is_encrypted", 0))
    p += text("Active slot", "font_xs", l2, r1l, color=mute, cond=c("tw_has_boot_slots", 1))
    p += text("%tw_active_slot%", "font_status", l2, r1v, cond=c("tw_has_boot_slots", 1))
    p += text("Storage", "font_xs", l1, r2l, color=mute)
    p += text("%tw_storage_display_name%", "font_status", l1, r2v)
    p += text("Free", "font_xs", l2, r2l, color=mute)
    p += text("%tw_storage_free_size% MB", "font_status", l2, r2v)
    p += "\t\t</page>\n"
    return p


def page_wipe():
    p = '\t\t<page name="wipe">\n\t\t\t<template name="page"/>\n\n'
    p += text("{@wipe_hdr=Wipe}", "font_l", "%col1_x_header%", TITLE_CY)
    mute = "%text_muted_color%"
    # TWRP's factory reset (wipe data): /data except the media folder, plus cache
    # and dalvik where present. This device has no /cache partition.
    p += text("Factory reset wipes Data and the Dalvik cache.", "font_s", 52, 216, color=mute)
    p += text("Internal storage and the microSD card are kept.", "font_s", 52, 257, color=mute)
    frame("row_wipe", CONTENT_W, 104, 28)
    rows_ = [("{@data=Data}", True, "", "Wiped"),
             ("Internal storage", False, c("tw_has_data_media", 1), "Kept"),
             ("MicroSD", False, "", "Kept")]
    y = 321
    for label, on, cond, state in rows_:
        p += image("row_wipe", INDENT, y, cond)
        p += image("checkbox_true" if on else "checkbox_false", 64, y + 8, cond)
        p += text(label, "font_m", 148, y + 52, cond=cond)
        p += text(state, "font_s", W - INDENT - 32, y + 52, color=mute, placement=1, cond=cond)
        y += 124
    by = y - 20 + 44
    p += button("btn_half", INDENT, by, acts(("set", "partitionlisterror=0"), ("page", "advancedwipe")),
                label="{@advanced_btn=Advanced}")
    p += button("btn_half", INDENT + 378, by, one("page", "formatdata"), cond=c("tw_has_data_media", 1),
                label="{@format_data_btn=Format Data}")
    p += button("btn_half", INDENT + 378, by, acts(
        ("set", "tw_back=wipe"), ("set", "tw_action=wipe"), ("set", "tw_action_param=DATAMEDIA"),
        ("set", "tw_has_action2=0"), ("set", "tw_text1={@wipe_enc_confirm=Wipe Encryption from Data?}"),
        ("set", "tw_text2="), ("set", "tw_action_text1={@formatting_data=Formatting Data...}"),
        ("set", "tw_complete_text1={@format_data_complete=Data Format Complete}"),
        ("set", "tw_slider_text={@swipe_format_data=Swipe to Format Data}"), ("page", "confirm_action")),
        cond=c("tw_is_encrypted", 1) + c("tw_has_data_media", 0), label="{@wipe_enc_btn=Wipe Encryption}")
    p += ('\t\t\t<slider>\n\t\t\t\t<text>{@swipe_factory_reset=Swipe to Factory Reset}</text>\n' +
          acts(("set", "tw_back=wipe"), ("set", "tw_action=wipe"), ("set", "tw_action_param=data"),
               ("set", "tw_action_text1={@factory_resetting=Factory Reset...}"),
               ("set", "tw_complete_text1={@factory_reset_complete=Factory Reset Complete}"),
               ("page", "action_page")) + "\t\t\t</slider>\n\n")
    p += nav_keys_main() + "\t\t</page>\n"
    return p


def page_install():
    p = '\t\t<page name="install">\n\t\t\t<template name="page"/>\n\n'
    p += text("{@install_btn=Install}", "font_l", "%col1_x_header%", TITLE_CY)
    # chips: the selected mode is solid black; Storage opens TWRP's storage list
    wz, zon, zoff = chip("ZIP")
    wi, ion, ioff = chip("Image")
    ws, son, soff = chip("Storage")
    cy = 188
    sel0, sel1 = c("tw_selectimage", 0), c("tw_selectimage", 1)
    p += button(zon, INDENT, cy, one("set", "tw_selectimage=0"), cond=sel0, label="ZIP", font="font_chip", color=WHITE)
    p += button(zoff, INDENT, cy, acts(("set", "tw_selectimage=0"), ("page", "install")), cond=sel1,
                label="ZIP", font="font_chip")
    xi = INDENT + wz + 16
    p += button(ion, xi, cy, one("set", "tw_selectimage=1"), cond=sel1, label="{@image=Image}", font="font_chip", color=WHITE)
    p += button(ioff, xi, cy, acts(("set", "tw_selectimage=1"), ("page", "install")), cond=sel0,
                label="{@image=Image}", font="font_chip")
    p += button(soff, W - INDENT - ws, cy, acts(("set", "tw_back=install"), ("overlay", "select_storage")),
                label="Storage", font="font_chip")
    p += text("%tw_zip_location%", "font_xs", 52, 316, color="%text_muted_color%")
    ly, lh = 348, 1000
    frame("frame_list", CONTENT_W, lh)
    p += image("frame_list", INDENT, ly)
    fsel = '''			<fileselector style="fileselector_nohdr">
{cond}				<placement x="{x}" y="{y}" w="{w}" h="{h}"/>
				<filter extn="{extn}" folders="1" files="1"/>
{prfx}				<path name="tw_zip_location" default="/sdcard"/>
				<data name="tw_filename"/>
				<selection name="tw_file"/>
			</fileselector>

'''
    for sel, extn, prfx in ((sel0, ".zip;.ozip;.ZIP;.OZIP",
                             '\t\t\t\t<prfxfilter prfx="Magisk-;Magisk.apk;app-release.apk;app-debug.apk" folders="1" files="1"/>\n'),
                            (sel1, ".img", "")):
        # inset by the frame's corner radius top and bottom: the list paints a square
        # background that would otherwise cut the rounded corners (phone, 2026-10-15)
        p += fsel.format(cond=sel, x=INDENT + SW, y=ly + 32, w=CONTENT_W - 2 * SW, h=lh - 64,
                         extn=extn, prfx=prfx)
    # static hint in the slider's place (the swipe happens on the next page)
    p += image("slider_hint", INDENT, SLIDER_CY - 64)
    p += text("Select a ZIP to install", "font_m", W // 2 + 50, SLIDER_CY, placement=5, cond=sel0)
    p += text("Select an image to flash", "font_m", W // 2 + 50, SLIDER_CY, placement=5, cond=sel1)
    p += '''			<action>
				<conditions>
					<condition var1="tw_selectimage" var2="0"/>
					<condition var1="tw_filename" op="modified"/>
				</conditions>
				<actions>
					<action function="queuezip"/>
					<action function="page">flash_confirm</action>
				</actions>
			</action>

			<action>
				<conditions>
					<condition var1="tw_selectimage" var2="1"/>
					<condition var1="tw_filename" op="modified"/>
				</conditions>
				<actions>
					<action function="set">tw_is_slot_part=0</action>
					<action function="page">flashimage_confirm</action>
				</actions>
			</action>

'''
    p += nav_keys_main() + "\t\t</page>\n"
    return p


def reboot_actions(param, text1, text2, slider):
    return acts(("set", "tw_back=reboot"), ("set", "tw_action=reboot"), ("set", f"tw_action_param={param}"),
                ("set", f"tw_reboot_param={param}"), ("set", "tw_has_action2=0"),
                ("set", "tw_text1={@no_os1=No OS Installed! Are you}"), ("set", f"tw_text2={text2}"),
                ("set", f"tw_action_text1={text1}"), ("set", f"tw_complete_text1={text1}"),
                ("set", f"tw_slider_text={slider}"), ("page", "rebootcheck"))


def page_reboot():
    p = '\t\t<page name="reboot">\n\t\t\t<template name="page"/>\n\n'
    p += text("{@reboot_hdr=Reboot}", "font_l", "%col1_x_header%", TITLE_CY)
    slots = c("tw_has_boot_slots", 1)
    mute = "%text_muted_color%"
    p += text("Current slot", "font_s", 52, 244, color=mute, cond=slots)
    for s, x in (("A", W - INDENT - 80 - 12 - 80), ("B", W - INDENT - 80)):
        other = "B" if s == "A" else "A"
        on = slots + c("tw_active_slot", s)
        off = slots + c("tw_active_slot", s, "!=")
        p += image("chip_slot_on", x, 212, on)
        p += text(s, "font_chip", x + 40, 244, color=WHITE, placement=5, cond=on)
        # switching slots asks for a swipe first (stock switches on the tap)
        p += button("chip_slot_off", x, 212, acts(
            ("set", "tw_back=reboot"), ("set", "tw_action=setbootslot"), ("set", f"tw_action_param={s}"),
            ("set", "tw_has_action2=0"), ("set", f"tw_text1=Make slot {s} the active slot?"),
            ("set", f"tw_text2=Slot {other} stays as it is."),
            ("set", "tw_action_text1={@changing_boot_slot=Changing Boot Slot}"), ("set", "tw_action_text2="),
            ("set", "tw_complete_text1={@changing_boot_slot_complete=Change Boot Slot Complete}"),
            ("set", f"tw_slider_text=Swipe to switch to slot {s}"), ("page", "confirm_action")),
            cond=off, label=s, font="font_chip")
    rb = "{@rebooting=Rebooting...}"
    srb = "{@swipe_reboot=Swipe to Reboot}"
    nosrb = "{@no_osrb=sure you wish to reboot?}"
    tiles = [
        ("system", "{@rb_system_btn=System}", c("tw_reboot_system", 1),
         acts(("set", "tw_back=reboot"), ("page", "reboot_system_routine"))),
        ("poweroff", "{@rb_poweroff_btn=Power Off}", c("tw_reboot_poweroff", 1),
         reboot_actions("poweroff", "{@turning_off=Turning Off...}", "{@no_ospo=sure you wish to power off?}",
                        "{@swipe_power_off=Swipe to Power Off}")),
        ("recovery", "{@rb_recovery_btn=Recovery}", c("tw_reboot_recovery", 1),
         reboot_actions("recovery", rb, nosrb, srb)),
        ("bootloader", "{@rb_bootloader_btn=Bootloader}", c("tw_reboot_bootloader", 1),
         reboot_actions("bootloader", rb, nosrb, srb)),
        ("fastbootd", "Fastbootd", c("tw_fastboot_mode", 1),
         reboot_actions("fastboot", rb, nosrb, srb)),
        # EDL always asks first: the phone then waits for a host tool and only
        # a long Power press gets it out again
        ("edl", "{@rb_edl_btn=EDL}", c("tw_edl_mode", 1),
         acts(("set", "tw_back=reboot"), ("set", "tw_action=reboot"), ("set", "tw_action_param=edl"),
              ("set", "tw_reboot_param=edl"), ("set", "tw_has_action2=0"),
              ("set", "tw_text1=Reboot to EDL (Qualcomm 9008)?"),
              ("set", "tw_text2=Needs a PC with an EDL tool."),
              ("set", "tw_text3=To leave EDL, hold Power for 10-15 s."), ("set", "tw_text4="),
              ("set", f"tw_action_text1={rb}"), ("set", f"tw_complete_text1={rb}"),
              ("set", "tw_slider_text=Swipe to reboot to EDL"), ("page", "confirm_action"))),
    ]
    xs = (INDENT, INDENT + 251, INDENT + 502)
    for i, (k, label, cond, a) in enumerate(tiles):
        x, y = xs[i % 3], (324, 578)[i // 3]
        p += button("rtile_" + k, x, y, a, cond=cond)
        p += text(label, "font_label", x + 117, y + 180, placement=5, cond=cond)

    # no power-off info card: the user asked for it to go (2026-10-15); the feature stays
    p += nav_keys_main() + "\t\t</page>\n"
    return p


def page_backup_run():
    p = '\t\t<page name="backup_run">\n\t\t\t<template name="page"/>\n\n'
    mute = "%text_muted_color%"
    p += text("%tw_operation%", "font_l", 52, TITLE_CY)
    p += text("{@storage=Storage}: %tw_storage_display_name%", "font_s", 52, 188, color=mute)
    p += text("%tw_partition%", "font_m", 52, 282)
    p += ('\t\t\t<progressbar>\n\t\t\t\t<placement x="%indent%" y="310"/>\n'
          '\t\t\t\t<resource empty="progress_empty" full="progress_full"/>\n'
          '\t\t\t\t<data name="ui_progress"/>\n\t\t\t</progressbar>\n\n')
    p += text("%tw_size_progress%", "font_xs", 52, 372, color=mute)
    p += text("%tw_file_progress%", "font_xs", W - 52, 372, color=mute, placement=1)
    fy, fh = 416, 952
    frame("frame_backup_console", CONTENT_W, fh)
    show = c("tw_ink_hide_log", 0)
    p += image("frame_backup_console", INDENT, fy, show)
    p += (f'\t\t\t<console>\n{show}\t\t\t\t<placement x="{INDENT + 20}" y="{fy + 16}" '
          f'w="{CONTENT_W - 40}" h="{fh - 32}"/>\n\t\t\t</console>\n\n')
    by = 1404
    p += button("btn_half", INDENT, by, '\t\t\t\t<action function="cancelbackup"/>\n', label="{@cancel_btn=Cancel}")
    p += button("btn_half_filled", INDENT + 378, by, one("set", "tw_ink_hide_log=1"), cond=show,
                label="Hide log", color=WHITE)
    p += button("btn_half_filled", INDENT + 378, by, one("set", "tw_ink_hide_log=0"),
                cond=c("tw_ink_hide_log", 1), label="Show log", color=WHITE)
    p += '''			<action>
				<action function="nandroid">backup</action>
			</action>

			<action>
				<condition var1="tw_operation_state" var2="1"/>
				<condition var1="tw_cancel_backup" var2="0"/>
				<actions>
					<action function="set">tw_back=backup</action>
					<action function="set">tw_complete_text1={@backup_complete=Backup Complete}</action>
					<action function="set">tw_show_reboot=1</action>
					<action function="page">action_complete</action>
				</actions>
			</action>

			<action>
				<condition var1="tw_operation_state" var2="1"/>
				<condition var1="tw_cancel_backup" var2="1"/>
				<actions>
					<action function="set">tw_back=backup</action>
					<action function="set">tw_complete_text1={@backup_cancel=Backup Cancelled}</action>
					<action function="set">tw_show_reboot=1</action>
					<action function="page">action_complete</action>
				</actions>
			</action>
		</page>
'''
    return p


EINK_SETTING = '''			<button>
				<placement x="%indent%" y="%row12a_y%" textplacement="6"/>
				<font resource="font_m" color="%text_color%"/>
				<condition var1="tw_eink_page_refresh" op="!=" var2="0"/>
				<text>Full E Ink refresh on page change</text>
				<image resource="checkbox_true"/>
				<action function="set">tw_eink_page_refresh=0</action>
			</button>

			<button>
				<placement x="%indent%" y="%row12a_y%" textplacement="6"/>
				<font resource="font_m" color="%text_color%"/>
				<condition var1="tw_eink_page_refresh" var2="0"/>
				<text>Full E Ink refresh on page change</text>
				<image resource="checkbox_false"/>
				<action function="set">tw_eink_page_refresh=1</action>
			</button>

'''


def portrait_xml(stock):
    s = stock
    s = re.sub(r"\t<styles>.*?\t</styles>\n", lambda m: styles(), s, count=1, flags=re.S)

    def replace_page(name, new):
        nonlocal s
        pat = re.compile(r'\t\t<page name="%s">.*?\n\t\t</page>\n' % re.escape(name), re.S)
        s, n = pat.subn(lambda m: new, s, count=1)
        if n != 1:
            sys.exit(f"page {name} not found in stock portrait.xml")

    replace_page("main2", page_main2())
    replace_page("wipe", page_wipe())
    replace_page("install", page_install())
    replace_page("reboot", page_reboot())
    replace_page("backup_run", page_backup_run())

    # black nav-bar fills on overlay/terminal pages -> white ground
    s = s.replace('<fill color="#000000">', '<fill color="%background_color%">')
    # stock subtitles (storage line etc.) to the page margin
    s = s.replace('x="%col1_x_header%" y="%row4_header_y%"', 'x="%col1_x_sub%" y="%row4_header_y%"')
    # dialogs: outline the white dialog box (the page behind is hidden, not dimmed)
    frame("frame_dialog", CONTENT_W, 11 * ROW)
    dlg = ('\t\t\t<fill color="%background_color%">\n'
           '\t\t\t\t<placement x="%indent%" y="row5_y" w="%content_width%" h="%dialog_height%"/>\n'
           '\t\t\t</fill>\n')
    n = s.count(dlg)
    s = s.replace(dlg, dlg + '\n' + image("frame_dialog", "%indent%", "%row5_y%").rstrip("\n") + "\n")
    if n < 2:
        sys.exit("dialog fills not found")
    # The dialog lists (storage, language) paint their own white background over their whole
    # placement (scrolllist.cpp), which started on the frame's top stroke at row5_y and erased
    # it between the corner arcs. Start them below the stroke and inside the corner radius.
    lst = 'y="%row5_y%" w="%content_overlay_width%" h="%partitionlist_storage_height%"'
    if s.count(lst) != 2:
        sys.exit("dialog list placements not found")
    s = s.replace(lst, lst.replace("%row5_y%", "%dialog_list_y%"))
    # Terminal: full-width at x 0 put the first column under the glass's rounded edge
    term = 'x="0" y="%row3_header_y%" w="%screen_width%"'
    if s.count(term) != 2:
        sys.exit("terminal placements not found")
    s = s.replace(term, 'x="%terminal_x%" y="%terminal_y%" w="%terminal_w%"')
    # Settings > Time Zone: save right away. TWRP writes .twrps only on a GUI reboot (tw_reboot), so a
    # zone set and then left with adb reboot or a long Power press was lost (measured 2026-10-15:
    # the user's Pacific choice came back as the default CST6CDT).
    tz = '<action function="setguitimezone"/>'
    if s.count(tz) != 1:
        sys.exit("settings_timezone button not found")
    s = s.replace(tz, '<actions>\n\t\t\t\t\t<action function="setguitimezone"/>\n'
                      '\t\t\t\t\t<action function="savesettings"/>\n\t\t\t\t</actions>')
    # Settings > Screen: the E Ink page-refresh switch, below the brightness slider
    anchor = '\t\t\t<slidervalue>\n\t\t\t\t<condition var1="tw_has_brightnesss_file" var2="1"/>'
    if anchor not in s:
        sys.exit("settings_screen anchor not found")
    s = s.replace(anchor, EINK_SETTING + anchor, 1)
    return ('<?xml version="1.0"?>\n<!-- Generated by device/hisense/HLTE556N/theme/gen_theme.py from TWRP\'s\n'
            '     gui/theme/common/portrait.xml (android-12.1). Do not edit. -->\n' +
            s.split("\n", 1)[1])


def splash_xml():
    return f'''<?xml version="1.0"?>
<!-- Generated by device/hisense/HLTE556N/theme/gen_theme.py. Do not edit. -->
<recovery>
	<details>
		<resolution width="{W}" height="{H}"/>
		<author>Hisense A9 (HLTE556N) device tree</author>
		<title>TWRP</title>
		<description>splash screen</description>
		<themeversion>{THEME_VERSION}</themeversion>
	</details>

	<resources>
		<font name="font_l" filename="Figtree-Bold.ttf" size="{tw_size(44)}"/>
		<font name="font_s" filename="Figtree-Regular.ttf" size="{tw_size(28)}"/>
		<image name="splashlogo" filename="splashlogo" retainaspect="1"/>
	</resources>

	<variables>
		<variable name="screen_width" value="{W}"/>
		<variable name="screen_height" value="{H}"/>
		<variable name="background_color" value="{WHITE}"/>
	</variables>

	<pages>
		<page name="splash">
			<background color="%background_color%"/>

			<image>
				<image resource="splashlogo"/>
				<placement x="{W // 2}" y="640" placement="4"/>
			</image>

			<text color="{INK}">
				<font resource="font_l"/>
				<placement x="{W // 2}" y="{ty("font_l", 860)}" placement="5"/>
				<text>Recovery</text>
			</text>

			<text color="{MUTED}">
				<font resource="font_s"/>
				<placement x="{W // 2}" y="{ty("font_s", 912)}" placement="5"/>
				<text>TWRP %tw_version% · Hisense A9</text>
			</text>
		</page>
	</pages>
</recovery>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", required=True, help="TWRP gui/theme/common/portrait.xml (android-12.1)")
    args = ap.parse_args()
    stock = open(args.stock, encoding="utf-8").read()

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "fonts"))
    build_images()
    portrait = portrait_xml(stock)   # registers page-specific images
    ui = ui_xml()                    # after all images are known
    write_images()
    with open(os.path.join(OUT, "ui.xml"), "w", encoding="utf-8") as f:
        f.write(ui)
    with open(os.path.join(OUT, "portrait.xml"), "w", encoding="utf-8") as f:
        f.write(portrait)
    with open(os.path.join(OUT, "splash.xml"), "w", encoding="utf-8") as f:
        f.write(splash_xml())
    for fn in os.listdir(FONTDIR):
        shutil.copy(os.path.join(FONTDIR, fn), os.path.join(OUT, "fonts", fn))
    print(f"wrote {OUT}: {len(IMAGES)} images")


if __name__ == "__main__":
    main()
