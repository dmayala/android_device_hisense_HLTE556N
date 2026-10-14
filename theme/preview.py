#!/usr/bin/env python3
"""Offline preview of the generated TWRP theme (recovery/root/twres).

A small interpreter for the subset of TWRP's GUI XML the theme uses: templates,
styles, %variables%, conditions, background/fill/image/text/button/slider/
progressbar/console/lists/checkbox/input/keyboard/slidervalue. Geometry follows
bootable/recovery/gui (button.cpp, text.cpp, scrolllist.cpp, slider.cpp,
keyboard.cpp) and the TrueType box of minuitwrp/truetype.cpp. Runtime values
(battery, paths, list contents, console lines) are mock data, so this checks
layout and look, not behaviour.

  nix-shell -p python3Packages.pillow --run \
    'python3 theme/preview.py OUTDIR [page ...]'
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TW = os.path.join(os.path.dirname(HERE), "recovery", "root", "twres")

MOCK = {
    "tw_version": "3.7.1_12-0", "tw_cpu_temp": "37", "tw_battery": "96% ", "tw_time": "11:39",
    "tw_no_cpu_temp": "0", "tw_no_battery_percent": "0", "tw_simulate_actions": "0", "tw_busy": "0",
    "tw_is_decrypted": "1", "tw_is_encrypted": "0", "tw_has_boot_slots": "1", "tw_active_slot": "A",
    "tw_storage_display_name": "Internal Storage", "tw_storage_free_size": "221184",
    "tw_has_data_media": "1", "tw_selectimage": "0", "tw_zip_location": "/sdcard/Download",
    "tw_reboot_system": "1", "tw_reboot_poweroff": "1", "tw_reboot_recovery": "1",
    "tw_reboot_bootloader": "1", "tw_fastboot_mode": "1", "tw_edl_mode": "1", "tw_download_mode": "0",
    "tw_operation": "Backing Up", "tw_partition": "Data", "tw_size_progress": "4600MB of 7400MB, 62%",
    "tw_file_progress": "18233 of 29410 files, 62%", "ui_progress": "62", "tw_samsung_navbar": "0",
    "tw_gui_sort_order": "1", "tw_has_brightnesss_file": "1", "tw_brightness_pct": "78",
    "tw_screen_timeout_secs": "0", "tw_no_screen_timeout": "1", "tw_action_text1": "Factory Reset...",
    "tw_action_text2": "", "tw_text1": "Make slot B the active slot?", "tw_text2": "Slot A stays as it is.",
    "tw_text3": "", "tw_text4": "", "tw_slider_text": "Swipe to switch to slot B", "tw_operation_status": "0",
    "tw_complete_text1": "Backup Complete", "tw_has_cancel": "0", "tw_hide_kb": "0", "tw_military_time": "1",
    "tw_crypto_display": "", "tw_crypto_pwtype": "1", "tw_backup_name": "(Auto Generate)",
    "tw_has_adopted_storage": "0", "tw_include_encrypted_backup": "1", "tw_has_usb_storage": "0",
    "tw_allow_partition_sdcard": "1", "tw_show_reboot": "1", "tw_has_injecttwrp": "0",
    "tw_terminal_state": "0", "tw_sideload": "0", "tw_ink_hide_log": "0", "tw_eink_page_refresh": "1",
    "tw_multiuser_warning_destination": "", "tw_fileexists": "0", "fileexists": "0",
    "tw_crypto_user_id": "0", "tw_ab_device": "1", "tw_has_repack_tools": "1", "tw_has_fastboot": "1",
    "tw_language_display": "English", "tw_is_fbe": "1", "tw_all_users_decrypted": "1",
}
LIST_MOCK = {
    "fileselector": [("folder", "Magisk"), ("folder", "modules"), ("file", "Magisk-v30.7.apk"),
                     ("file", "MindTheGapps-16.0.0-arm64.zip"), ("file", "twrp-HLTE556N.img"),
                     ("file", "Sorayomi-0.6.3.apk")],
    "partitionlist": [("checkbox_true", "Boot (64MB)"), ("checkbox_false", "System (3500MB)"),
                      ("checkbox_true", "Data (excl. storage) (7400MB)"), ("checkbox_false", "Persist (32MB)"),
                      ("checkbox_false", "EFS (16MB)")],
    "listbox": [("radio_true", "English"), ("radio_false", "Deutsch"), ("radio_false", "Español")],
}
CONSOLE = ["Backing up Boot...", "Backup completed in 2 seconds", "Backing up Persist...",
           "Backup completed in 1 second", "Backing up Data (excl. storage)...",
           "Generating digest...", "Writing data.f2fs.win003"]


class Theme:
    def __init__(self):
        self.ui = ET.parse(os.path.join(TW, "ui.xml")).getroot()
        self.po = ET.parse(os.path.join(TW, "portrait.xml")).getroot()
        self.vars = {}
        for v in self.ui.iter("variable"):
            self.vars[v.get("name")] = v.get("value")
        self.vars.update(MOCK)
        self.fonts, self.images = {}, {}
        for f in self.ui.find("resources").iter("font"):
            em = int(f.get("size")) * 300.0 / 288.0
            pil = ImageFont.truetype(os.path.join(TW, "fonts", f.get("filename")), em)
            ymax = ymin = 0
            for ch in range(33, 127):
                x0, y0, x1, y1 = pil.getbbox(chr(ch), anchor="ls")
                ymax, ymin = max(ymax, -y0), min(ymin, -y1)
            size = int(f.get("size"))
            self.fonts[f.get("name")] = (pil, ymax - ymin + size // 4, ymax + size // 4)
        for i in self.ui.find("resources").iter("image"):
            p = os.path.join(TW, "images", i.get("filename") + ".png")
            if os.path.exists(p):
                self.images[i.get("name")] = Image.open(p).convert("RGBA")
        self.templates = {t.get("name"): t for t in self.ui.find("templates")}
        self.styles = {s.get("name"): s for s in self.po.find("styles")}
        self.pages = {p.get("name"): p for p in self.po.find("pages")}

    def val(self, s):
        if s is None:
            return None
        for _ in range(5):
            s2 = re.sub(r"%([A-Za-z0-9_]+)%", lambda m: self.vars.get(m.group(1), ""), s)
            if s2 == s:
                break
            s = s2
        s = re.sub(r"\{@[^=}]+=([^}]*)\}", lambda m: m.group(1), s)
        s = re.sub(r"\{@([^}]+)\}", lambda m: m.group(1), s)
        return s

    def num(self, s, default=0):
        if s is None:
            return default
        s = self.val(s)
        if re.fullmatch(r"-?\d+", s.strip()):
            return int(s)
        if s in self.vars:
            return self.num(self.vars[s])
        return default

    def cond_true(self, node):
        conds = list(node.findall("condition"))
        for cs in node.findall("conditions"):
            conds += cs.findall("condition")
        for c in conds:
            v1 = c.get("var1")
            a = self.vars.get(v1, v1)
            b = self.val(c.get("var2", ""))
            op = c.get("op", "=")
            if op == "modified":
                return False
            try:
                fa, fb = float(re.match(r"-?\d+", a).group()), float(re.match(r"-?\d+", b).group())
            except Exception:
                fa = fb = None
            ok = {"=": a == b, "!=": a != b,
                  ">": fa is not None and fa > fb, "<": fa is not None and fa < fb,
                  ">=": fa is not None and fa >= fb, "<=": fa is not None and fa <= fb}.get(op, a == b)
            if not ok:
                return False
        return True


def child(node, style_nodes, tag):
    n = node.find(tag)
    if n is not None:
        return n
    for s in style_nodes:
        n = s.find(tag)
        if n is not None:
            return n
    return None


def rgba(s):
    s = s.lstrip("#")
    if len(s) == 6:
        s += "FF"
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))


class Renderer:
    def __init__(self, th):
        self.th = th
        self.im = Image.new("RGBA", (824, 1648), "white")
        self.d = ImageDraw.Draw(self.im)

    def color(self, s, default="#111111"):
        return rgba(self.th.val(s) if s else default)

    def text_at(self, s, font, x, y, color, placement=0, maxw=None):
        pil, mh, base = self.th.fonts[font]
        w = pil.getlength(s)
        if placement in (1, 3):
            x -= w
        if placement in (4, 5):
            x -= w / 2
        if placement in (2, 3):
            y -= mh
        if placement == 4:
            y -= mh / 2
        self.d.text((x, y + base), s, font=pil, fill=color, anchor="ls")
        return w, mh

    def paste(self, name, x, y, clipw=None):
        img = self.th.images.get(name)
        if img is None:
            return
        if clipw is not None:
            img = img.crop((0, 0, max(0, min(clipw, img.width)), img.height))
        self.im.alpha_composite(img, (int(x), int(y)))

    def place(self, node, styles):
        p = child(node, styles, "placement")
        if p is None:
            return 0, 0, 0, 0, 0
        th = self.th
        return (th.num(p.get("x")), th.num(p.get("y")), th.num(p.get("w")), th.num(p.get("h")),
                th.num(p.get("placement"), 0))

    def styles_of(self, node):
        st = []
        if node.get("style") and node.get("style") in self.th.styles:
            st.append(self.th.styles[node.get("style")])
        elif node.tag in self.th.styles:
            st.append(self.th.styles[node.tag])
        return st

    def render(self, node):
        for el in node:
            t = el.tag
            if t == "template":
                self.render(self.th.templates[el.get("name")])
                continue
            if t in ("action", "condition", "conditions", "details", "include"):
                continue
            if not self.th.cond_true(el):
                continue
            fn = getattr(self, "r_" + t, None)
            if fn:
                fn(el, self.styles_of(el))

    # -- elements --------------------------------------------------------
    def r_background(self, el, st):
        self.d.rectangle((0, 0, 824, 1648), fill=self.color(el.get("color")))

    def r_fill(self, el, st):
        x, y, w, h, _ = self.place(el, st)
        col = self.color(el.get("color"))
        if col[3] and w and h:
            self.d.rectangle((x, y, x + w - 1, y + h - 1), fill=col)

    def r_image(self, el, st):
        x, y, _, _, pl = self.place(el, st)
        res = el.find("image").get("resource")
        img = self.th.images.get(res)
        if img is None:
            return
        if pl in (1, 3):
            x -= img.width
        if pl in (4, 5):
            x -= img.width // 2
        if pl in (2, 3):
            y -= img.height
        if pl == 4:
            y -= img.height // 2
        self.paste(res, x, y)

    def font_of(self, el, st):
        f = child(el, st, "font")
        return (f.get("resource") if f is not None else "font_m",
                self.color(el.get("color") or (f.get("color") if f is not None else None)))

    def r_text(self, el, st):
        x, y, _, _, pl = self.place(el, st)
        font, col = self.font_of(el, st)
        s = self.th.val(el.find("text").text or "")
        self.text_at(s, font, x, y, col, pl)

    def r_button(self, el, st):
        x, y, w, h, pl = self.place(el, st)
        imgn = child(el, st, "image")
        if imgn is not None and imgn.get("resource") in self.th.images:
            img = self.th.images[imgn.get("resource")]
            w, h = img.width, img.height
            if pl in (4, 5):
                x -= w // 2
            if pl == 4:
                y -= h // 2
            if pl in (1, 3):
                x -= w
            self.paste(imgn.get("resource"), x, y)
        else:
            fill = child(el, st, "fill")
            if fill is not None:
                col = self.color(fill.get("color"))
                if col[3]:
                    self.d.rectangle((x, y, x + w - 1, y + h - 1), fill=col)
        tn = el.find("text")
        if tn is not None and tn.text:
            font, col = self.font_of(el, st)
            s = self.th.val(tn.text)
            p = child(el, st, "placement")
            if p is not None and p.get("textplacement") == "6":
                mh = self.th.fonts[font][1]
                self.text_at(s, font, x + w + 5, y + h / 2 - mh / 2, col)
            else:
                self.text_at(s, font, x + w / 2, y + h / 2, col, 4)

    def r_checkbox(self, el, st):
        x, y, _, _, _ = self.place(el, st)
        im = child(el, st, "image")
        res = im.get("checked") if self.th.vars.get(el.find("data").get("variable"), "0") == "1" else im.get("unchecked")
        img = self.th.images[res]
        self.paste(res, x, y)
        font, col = self.font_of(el, st)
        mh = self.th.fonts[font][1]
        self.text_at(self.th.val(el.find("text").text or ""), font, x + img.width + 5, y + img.height / 2 - mh / 2, col)

    def r_slider(self, el, st):
        x, y, _, _, pl = self.place(el, st)
        res = child(el, st, "resource")
        base = self.th.images[res.get("base")]
        x -= base.width // 2
        y -= base.height // 2
        self.paste(res.get("base"), x, y)
        touch = self.th.images[res.get("touch")]
        self.paste(res.get("touch"), x, y + (base.height - touch.height) // 2)
        font, col = self.font_of(el, st)
        self.text_at(self.th.val(el.find("text").text or ""), font, x + base.width / 2,
                     y + base.height / 2, col, 4)

    def r_progressbar(self, el, st):
        x, y, _, _, _ = self.place(el, st)
        res = el.find("resource")
        e = self.th.images[res.get("empty")]
        self.paste(res.get("empty"), x, y)
        self.paste(res.get("full"), x, y, clipw=int(e.width * 0.62))

    def r_console(self, el, st):
        x, y, w, h, _ = self.place(el, st)
        pil, mh, base = self.th.fonts["fixed"]
        for i, ln in enumerate(CONSOLE):
            if (i + 1) * mh > h:
                break
            self.d.text((x, y + i * mh + base), ln, font=pil, fill=rgba("#111111"), anchor="ls")

    r_terminal = r_console

    def r_input(self, el, st):
        x, y, w, h, _ = self.place(el, st)
        font, col = self.font_of(el, st)
        self.d.rectangle((x, y + 8, x + 3, y + h - 8), fill=rgba("#111111"))

    def list_common(self, el, st, rows, kind):
        x, y, w, h, _ = self.place(el, st)
        font = child(el, st, "font")
        fname = font.get("resource")
        pil, mh, base = self.th.fonts[fname]
        sep = child(el, st, "separator")
        sep_h = self.th.num(sep.get("height")) if sep is not None else 0
        sep_c = self.color(sep.get("color")) if sep is not None else None
        icons = [self.th.images[r] for r, _ in rows if r in self.th.images]
        icon_node = child(el, st, "icon")
        if kind == "advanced" and icon_node is not None:
            icons = [self.th.images[icon_node.get("selected")]]
        max_iw = max([i.width for i in icons] or [0])
        max_ih = max([i.height for i in icons] or [0])
        item_h = max(mh, max_ih) + sep_h
        yy = y
        hdr = el.find("text")
        if hdr is not None and hdr.text:
            hdrn = child(el, st, "header")
            self.text_at(self.th.val(hdr.text), fname, x + 5, yy + item_h / 2 - mh / 2, rgba("#111111"))
            hs = self.th.num(hdrn.get("separatorheight")) if hdrn is not None else 0
            self.d.rectangle((x, yy + item_h - hs, x + w - 1, yy + item_h - 1), fill=rgba("#111111"))
            yy += item_h
        for res, label in rows:
            if yy + item_h > y + h:
                break
            if kind == "advanced":
                res = icon_node.get("selected")
            img = self.th.images.get(res)
            if img is not None:
                self.paste(res, x + (max_iw - img.width) // 2, yy + (item_h - img.height) // 2)
            self.text_at(label, fname, x + max_iw + 5, yy + item_h / 2 - mh / 2, rgba("#111111"))
            if sep_h:
                self.d.rectangle((x, yy + item_h - sep_h, x + w - 1, yy + item_h - 1), fill=sep_c)
            yy += item_h

    def r_fileselector(self, el, st):
        self.list_common(el, st, LIST_MOCK["fileselector"], "file")

    def r_partitionlist(self, el, st):
        lt = el.find("listtype").get("name") if el.find("listtype") is not None else ""
        rows = LIST_MOCK["partitionlist"]
        if lt == "storage":
            rows = [("radio_true", "Internal Storage (221184 MB)"), ("radio_false", "Micro SDcard (59640 MB)"),
                    ("radio_false", "USB OTG (0 MB)")]
        self.list_common(el, st, rows, "part")

    def r_listbox(self, el, st):
        items = [(None, self.th.val(li.get("name"))) for li in el.findall("listitem") if self.th.cond_true(li)]
        if not items:
            items = LIST_MOCK["listbox"]
        kind = "advanced" if el.get("style") == "advanced_listbox" else "list"
        if kind == "list" and items and items[0][0] is None:
            items = [("radio_true" if i == 0 else "radio_false", t) for i, (_, t) in enumerate(items)]
        self.list_common(el, st, items, kind)

    def r_slidervalue(self, el, st):
        x, y, w, _, _ = self.place(el, st)
        font, col = self.font_of(el, st)
        pil, mh, base = self.th.fonts[font]
        self.text_at(self.th.val(el.find("text").text or ""), font, x, y, col)
        ly = y + mh + 44
        self.d.rectangle((x, ly - 2, x + w, ly + 1), fill=rgba("#111111"))
        self.paste("handle", x + int(w * 0.6) - 28, ly - 44)

    def r_keyboard(self, el, st):
        x, y, w, h, _ = self.place(el, st)
        bg = self.color(el.find("background").get("color"))
        self.d.rectangle((x, y, x + w - 1, y + h - 1), fill=bg)
        km = el.find("keymargin")
        mx, my = int(km.get("x")), int(km.get("y"))
        alnum = el.find("key-alphanumeric")
        other = el.find("key-other")
        labels = {k.get("key"): (k.get("text"), k.get("resource")) for k in el.findall("keylabel")}
        lay = el.find("layout1")
        for k in lay.findall("keylabel"):
            labels[k.get("key")] = (k.get("text"), k.get("resource"))
        ks = lay.find("keysize")
        kw, kh = int(ks.get("width")), int(ks.get("height"))
        ry = y
        for r in sorted([c for c in lay if c.tag.startswith("row")], key=lambda c: int(c.tag[3:])):
            kx = x
            for i in range(1, 20):
                key = r.get("key%02d" % i)
                if key is None:
                    continue
                width = kw
                m = re.match(r"^(\d+):(.*)$", key)
                if m:
                    width, key = int(m.group(1)), m.group(2)
                if key == "":  # blank keys are drawn too (keyboard.cpp DrawKey)
                    self.d.rectangle((kx + mx, ry + my, kx + width - mx - 1, ry + kh - my - 1),
                                     fill=rgba(other.get("color")))
                    kx += width
                    continue
                is_char = len(key) == 1
                node = alnum if is_char else other
                self.d.rectangle((kx + mx, ry + my, kx + width - mx - 1, ry + kh - my - 1),
                                 fill=rgba(node.get("color")))
                lab = labels.get("0:" + key) or labels.get(key)
                if lab and lab[1] and lab[1] in self.th.images:
                    img = self.th.images[lab[1]]
                    self.paste(lab[1], kx + (width - img.width) // 2, ry + (kh - img.height) // 2)
                else:
                    t = lab[0] if lab else key
                    self.text_at(t, node.get("font"), kx + width / 2, ry + kh / 2, rgba(node.get("textcolor")), 4)
                lp = r.get("long%02d" % i)
                if lp:
                    lpn = el.find("longpress")
                    self.text_at(lp, lpn.get("font"), kx + width - mx - 22, ry + my + 2, rgba(lpn.get("textcolor")))
                kx += width
            ry += kh


def render_page(th, name, base_page=None):
    r = Renderer(th)
    if base_page:
        r.render(th.pages[base_page])
    r.render(th.pages[name])
    return r.im.convert("RGB")


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    th = Theme()
    pages = sys.argv[2:] or ["main2", "wipe", "install", "reboot", "backup_run"]
    for p in pages:
        overlay, sets = None, {}
        if "," in p:  # page,var=value,... overrides mock values
            p, *kv = p.split(",")
            sets = dict(x.split("=", 1) for x in kv)
        if ":" in p:
            overlay, p = p.split(":", 1)[1], p.split(":", 1)[0]
        for k, v in list(MOCK.items()):
            th.vars[k] = v
        th.vars.update(sets)
        im = render_page(th, p)
        if overlay:
            r = Renderer(th)
            r.im = im.convert("RGBA")
            r.d = ImageDraw.Draw(r.im)
            r.render(th.pages[overlay])
            im = r.im.convert("RGB")
            p = p + "+" + overlay
        im.save(os.path.join(out, p + ".png"))
        print("wrote", p)


if __name__ == "__main__":
    main()
