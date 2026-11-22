#!/usr/bin/env python3
"""THE WORLD IN ONE DAY - a broadsheet front page for Sunday 22 November 2026.
Pure Python standard library. Draws one 1024x1024 PNG deterministically.
Everything is drawn by this program: a stroke-built vector typeface rendered
as filled polygons, layered polygon illustration scenes, a world map, and
all page furniture. Supersampled x2, then box-downscaled for clean edges.
"""
import math
import os
import struct
import zlib

SS = 2
W = 1024
H = 1024

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w * SS
        self.h = h * SS
        self.px = bytearray(self.w * self.h * 3)
        self.fill_all(bg)

    def fill_all(self, c):
        row = bytes(c) * self.w
        for y in range(self.h):
            s = y * self.w * 3
            self.px[s:s + self.w * 3] = row

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]; self.px[i + 1] = c[1]; self.px[i + 2] = c[2]

    def blend(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            ia = 1.0 - a
            self.px[i] = int(self.px[i] * ia + c[0] * a)
            self.px[i + 1] = int(self.px[i + 1] * ia + c[1] * a)
            self.px[i + 2] = int(self.px[i + 2] * ia + c[2] * a)

    def rect(self, x, y, w, h, c, a=1.0):
        x0 = int(round(x * SS)); y0 = int(round(y * SS))
        x1 = int(round((x + w) * SS)); y1 = int(round((y + h) * SS))
        x0 = max(0, x0); y0 = max(0, y0); x1 = min(self.w, x1); y1 = min(self.h, y1)
        if x1 <= x0 or y1 <= y0:
            return
        if a >= 1.0:
            row = bytes(c) * (x1 - x0)
            for yy in range(y0, y1):
                s = (yy * self.w + x0) * 3
                self.px[s:s + (x1 - x0) * 3] = row
        else:
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    self.blend(xx, yy, c, a)

    def poly(self, pts, c, a=1.0):
        """Filled polygon, scanline, coordinates in output pixels."""
        if len(pts) < 3:
            return
        P = [(p[0] * SS, p[1] * SS) for p in pts]
        ys = [p[1] for p in P]
        y0 = max(0, int(math.floor(min(ys)))); y1 = min(self.h - 1, int(math.ceil(max(ys))))
        n = len(P)
        for yy in range(y0, y1 + 1):
            yc = yy + 0.5
            xs = []
            for i in range(n):
                xa, ya = P[i]; xb, yb = P[(i + 1) % n]
                if (ya <= yc < yb) or (yb <= yc < ya):
                    xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = int(math.ceil(xs[k] - 0.5)); xb = int(math.floor(xs[k + 1] - 0.5))
                for xx in range(max(0, xa), min(self.w - 1, xb) + 1):
                    if a >= 1.0:
                        self.set(xx, yy, c)
                    else:
                        self.blend(xx, yy, c, a)

    def circle(self, cx, cy, r, c, a=1.0):
        cx *= SS; cy *= SS; r *= SS
        x0 = max(0, int(cx - r - 1)); x1 = min(self.w - 1, int(cx + r + 1))
        y0 = max(0, int(cy - r - 1)); y1 = min(self.h - 1, int(cy + r + 1))
        r2 = r * r
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                d2 = (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2
                if d2 <= r2:
                    if a >= 1.0:
                        self.set(xx, yy, c)
                    else:
                        self.blend(xx, yy, c, a)

    def ellipse(self, cx, cy, rx, ry, c, a=1.0):
        cx *= SS; cy *= SS; rx *= SS; ry *= SS
        x0 = max(0, int(cx - rx - 1)); x1 = min(self.w - 1, int(cx + rx + 1))
        y0 = max(0, int(cy - ry - 1)); y1 = min(self.h - 1, int(cy + ry + 1))
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                v = ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2
                if v <= 1.0:
                    if a >= 1.0:
                        self.set(xx, yy, c)
                    else:
                        self.blend(xx, yy, c, a)

    def seg(self, x1, y1, x2, y2, wdt, c, a=1.0):
        """Thick line segment drawn as a filled polygon plus round caps."""
        dx = x2 - x1; dy = y2 - y1
        ln = math.hypot(dx, dy)
        if ln < 1e-9:
            self.circle(x1, y1, wdt / 2.0, c, a); return
        nx = -dy / ln * wdt / 2.0; ny = dx / ln * wdt / 2.0
        self.poly([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
                   (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)], c, a)
        self.circle(x1, y1, wdt / 2.0, c, a)
        self.circle(x2, y2, wdt / 2.0, c, a)

    def path(self, pts, wdt, c, a=1.0):
        for i in range(len(pts) - 1):
            self.seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], wdt, c, a)

    def bezier(self, p0, p1, p2, p3, wdt, c, a=1.0, steps=28):
        pts = []
        for i in range(steps + 1):
            t = i / steps; u = 1 - t
            x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
            y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
            pts.append((x, y))
        self.path(pts, wdt, c, a)

    def ring(self, cx, cy, r, wdt, c, a=1.0, steps=48):
        pts = [(cx + r * math.cos(2 * math.pi * i / steps),
                cy + r * math.sin(2 * math.pi * i / steps)) for i in range(steps + 1)]
        self.path(pts, wdt, c, a)

    def downscale_png_rows(self):
        """Box-downscale by SS and return raw RGB rows for PNG encoding."""
        out = bytearray(W * H * 3)
        sw = self.w
        for y in range(H):
            for x in range(W):
                r = g = b = 0
                for dy in range(SS):
                    base = ((y * SS + dy) * sw + x * SS) * 3
                    for dx in range(SS):
                        i = base + dx * 3
                        r += self.px[i]; g += self.px[i + 1]; b += self.px[i + 2]
                o = (y * W + x) * 3; n = SS * SS
                out[o] = r // n; out[o + 1] = g // n; out[o + 2] = b // n
        return bytes(out)


def write_png(path, rgb, w, h):
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ---------------------------------------------------------------- palette
PAPER = (247, 241, 227)
PAPER2 = (239, 231, 210)
INK = (22, 20, 17)
SOFT = (74, 68, 58)
FAINT = (133, 124, 108)
RED = (178, 32, 26)
DARKRED = (128, 22, 18)
WHITE = (255, 253, 247)
CARD = (252, 248, 238)
NAVY = (16, 28, 52)
NAVY2 = (27, 45, 78)
SEA = (23, 58, 86)
ORANGE = (232, 116, 32)
AMBER = (245, 178, 60)
SMOKE = (120, 118, 112)
REGION_COLORS = [(39, 92, 160), (26, 140, 120), (178, 32, 26),
                 (224, 148, 32), (110, 70, 150), (70, 150, 60), (96, 96, 104)]

# ---------------------------------------------------------------- typeface
# Glyphs are stroke polylines on an 8-wide, 14-tall grid (y down, 0=top of
# cap height, 14=baseline). Strokes are drawn as filled polygons with round
# joints, so weight is controlled by stroke width alone.
def _g(*paths):
    out = []
    for p in paths:
        pts = []
        for tok in p.split():
            a, b = tok.split(",")
            pts.append((float(a), float(b)))
        out.append(pts)
    return out

GLYPHS = {}
GLYPHS['A'] = _g("0,14 4,0 8,14", "1.6,9.5 6.4,9.5")
GLYPHS['B'] = _g("0,0 0,14", "0,0 5,0 7,1.8 7,4.6 5,6.6 0,6.6",
                 "0,6.6 5.6,6.6 7.6,8.8 7.6,11.6 5.6,14 0,14")
GLYPHS['C'] = _g("7.6,3.4 5.6,0.8 3.4,0 1.2,1.6 0,4.6 0,9.4 1.2,12.4 3.4,14 5.6,13.2 7.6,10.6")
GLYPHS['D'] = _g("0,0 0,14", "0,0 4.4,0 7,2.4 7.6,6 7,11.6 4.4,14 0,14")
GLYPHS['E'] = _g("7.4,0 0,0 0,14 7.4,14", "0,7 5.4,7")
GLYPHS['F'] = _g("7.4,0 0,0 0,14", "0,7 5.2,7")
GLYPHS['G'] = _g("7.6,3.4 5.6,0.8 3.4,0 1.2,1.6 0,4.6 0,9.4 1.2,12.4 3.4,14 5.8,13.4 7.6,11.4 7.6,8 4.6,8")
GLYPHS['H'] = _g("0,0 0,14", "8,0 8,14", "0,7 8,7")
GLYPHS['I'] = _g("4,0 4,14", "1.4,0 6.6,0", "1.4,14 6.6,14")
GLYPHS['J'] = _g("7.4,0 7.4,10.4 5.8,13.4 3.4,14 1.2,12.6 0.4,10.4")
GLYPHS['K'] = _g("0,0 0,14", "7.6,0 0.6,7.4", "1.8,6 7.8,14")
GLYPHS['L'] = _g("0,0 0,14 7.4,14")
GLYPHS['M'] = _g("0,14 0,0 4,6.4 8,0 8,14")
GLYPHS['N'] = _g("0,14 0,0 8,14 8,0")
GLYPHS['O'] = _g("3.4,0 1.2,1.6 0,4.6 0,9.4 1.2,12.4 3.4,14 4.6,14 6.8,12.4 8,9.4 8,4.6 6.8,1.6 4.6,0 3.4,0")
GLYPHS['P'] = _g("0,14 0,0 5.2,0 7.4,2 7.4,5.2 5.2,7.4 0,7.4")
GLYPHS['Q'] = _g("3.4,0 1.2,1.6 0,4.6 0,9.4 1.2,12.4 3.4,14 4.6,14 6.8,12.4 8,9.4 8,4.6 6.8,1.6 4.6,0 3.4,0", "5,10.6 8.4,14.6")
GLYPHS['R'] = _g("0,14 0,0 5.2,0 7.4,2 7.4,5.2 5.2,7.4 0,7.4", "4.6,7.4 7.8,14")
GLYPHS['S'] = _g("7.4,2.8 5.4,0.4 3,0 1.2,1.8 1.2,4.2 3,6 5.6,7.2 7,9 6.8,12 5,14 2.6,13.8 0.6,11.4")
GLYPHS['T'] = _g("0,0 8,0", "4,0 4,14")
GLYPHS['U'] = _g("0,0 0,9.6 1.2,12.6 3.2,14 4.8,14 6.8,12.6 8,9.6 8,0")
GLYPHS['V'] = _g("0,0 4,14 8,0")
GLYPHS['W'] = _g("0,0 1.8,14 4,4.6 6.2,14 8,0")
GLYPHS['X'] = _g("0,0 8,14", "8,0 0,14")
GLYPHS['Y'] = _g("0,0 4,6.4 8,0", "4,6.4 4,14")
GLYPHS['Z'] = _g("0,0 7.6,0 0,14 7.6,14")
GLYPHS['0'] = _g("3.4,0 1.4,1.4 0.8,4.4 0.8,9.6 1.4,12.6 3.4,14 4.6,14 6.6,12.6 7.2,9.6 7.2,4.4 6.6,1.4 4.6,0 3.4,0", "1.6,11 6.4,3")
GLYPHS['1'] = _g("1.6,3.4 4.6,0.6 4.6,14", "1.6,14 7,14")
GLYPHS['2'] = _g("0.8,3.2 2,0.8 4.2,0 6.4,1.2 6.8,3.6 5.4,6.2 0.6,13.4", "0.6,14 7.2,14")
GLYPHS['3'] = _g("0.8,2.6 2.4,0.4 4.6,0 6.6,1.8 6.4,4.4 4.8,6.2 3,6.6", "3,6.6 5,6.8 6.8,8.8 6.6,12 4.8,14 2.4,13.6 0.8,11.4")
GLYPHS['4'] = _g("5.4,14 5.4,0 0.4,10 7.8,10")
GLYPHS['5'] = _g("6.8,0 1.2,0 0.8,5.6 3,4.6 5.4,5 7,7.4 6.6,11.4 4.8,13.8 2.2,14 0.6,12.2")
GLYPHS['6'] = _g("6.6,2.8 4.6,0.6 2.4,1.4 1,4.4 0.6,8.6 1.6,12.2 3.4,14 5.6,13.4 7,11 6.8,8.2 5,6.4 2.8,6.6 1,8.6")
GLYPHS['7'] = _g("0.4,0 7.6,0 3.4,14")
GLYPHS['8'] = _g("3,6.6 1.4,5 1.6,2 3.2,0.2 4.8,0.2 6.4,2 6.6,5 5,6.6 3,6.6 1.2,8.6 1.4,11.8 3,14 5,14 6.6,11.8 6.8,8.6 5,6.6")
GLYPHS['9'] = _g("1.4,11.2 3.4,13.4 5.6,12.6 7,9.6 7.4,5.4 6.4,1.8 4.6,0 2.4,0.6 1,3 1.2,5.8 3,7.6 5.2,7.4 7,5.4")
# lowercase: body sits y=5..14, ascenders rise to y=2, descenders to y=17.5
GLYPHS['a'] = _g("6.8,6.2 5,5.2 2.8,5.4 1.2,7.2 1,10.6 2.4,13.4 4.4,14 6.8,12.4", "6.8,5.4 6.8,14")
GLYPHS['b'] = _g("0.6,2 0.6,14", "0.6,8 2.6,5.6 5,5.4 6.8,7.4 6.8,11.4 5,13.8 2.6,13.6 0.6,11.4")
GLYPHS['c'] = _g("6.8,7 5,5.2 2.8,5.4 1.2,7.4 1,11 2.6,13.6 4.8,13.8 6.8,11.8")
GLYPHS['d'] = _g("6.8,2 6.8,14", "6.8,8 4.8,5.6 2.6,5.4 1,7.4 1,11.4 2.6,13.8 4.8,13.6 6.8,11.4")
GLYPHS['e'] = _g("1,9.4 6.8,9.4 6.4,6.8 4.8,5.2 2.6,5.4 1.2,7.4 1,11 2.6,13.6 4.8,13.8 6.8,11.8")
GLYPHS['f'] = _g("6.4,2.6 4.8,2 3.4,3 3.2,5.4 3.2,14", "1.2,7.4 5.6,7.4")
GLYPHS['g'] = _g("6.8,5.4 6.8,15 5.6,17.2 3.4,17.6 1.4,16.2", "6.8,8 4.8,5.6 2.6,5.4 1,7.4 1,11.4 2.6,13.8 4.8,13.6 6.8,11.4")
GLYPHS['h'] = _g("0.6,2 0.6,14", "0.6,9 2.4,6 4.8,5.4 6.6,7 6.6,14")
GLYPHS['i'] = _g("3.4,5.4 3.4,14")
GLYPHS['j'] = _g("3.6,5.4 3.6,15 2.4,17.2 0.8,17.4")
GLYPHS['k'] = _g("0.6,2 0.6,14", "6.6,5.4 1.2,10", "2.8,8.6 6.8,14")
GLYPHS['l'] = _g("3,2 3,14")
GLYPHS['m'] = _g("0.6,5.4 0.6,14", "0.6,8.6 2,6 4,5.4 5.4,7 5.4,14", "5.4,8.6 6.4,6.2 8,6.6 8.6,8.6 8.6,14")
GLYPHS['n'] = _g("0.6,5.4 0.6,14", "0.6,8.6 2.2,6 4.6,5.4 6.6,7 6.6,14")
GLYPHS['o'] = _g("3.4,5.4 1.6,6.6 0.8,9 1.4,12.4 3,14 5,14 6.6,12.4 7.2,9 6.4,6.6 5,5.4 3.4,5.4")
GLYPHS['p'] = _g("0.6,5.4 0.6,17.6", "0.6,8 2.6,5.6 5,5.4 6.8,7.4 6.8,11.4 5,13.8 2.6,13.6 0.6,11.4")
GLYPHS['q'] = _g("6.8,5.4 6.8,17.6", "6.8,8 4.8,5.6 2.6,5.4 1,7.4 1,11.4 2.6,13.8 4.8,13.6 6.8,11.4")
GLYPHS['r'] = _g("0.6,5.4 0.6,14", "0.6,8.8 2.2,6.2 4.4,5.4 6.4,6")
GLYPHS['s'] = _g("6.6,6.8 5,5.2 2.8,5.4 1.4,7 2.2,9 4.6,10 6.4,11.2 5.8,13.4 3.6,14.2 1.4,12.8")
GLYPHS['t'] = _g("3.4,2.8 3.4,11.6 4.6,13.8 6.6,14", "1.2,7.4 5.8,7.4")
GLYPHS['u'] = _g("0.8,5.4 0.8,11.4 2.4,13.8 4.8,13.6 6.8,11.4", "6.8,5.4 6.8,14")
GLYPHS['v'] = _g("0.4,5.4 3.6,14 7,5.4")
GLYPHS['w'] = _g("0.2,5.4 1.6,14 3.6,7.4 5.6,14 7.8,5.4")
GLYPHS['x'] = _g("0.6,5.4 7,14", "7,5.4 0.6,14")
GLYPHS['y'] = _g("0.4,5.4 3.6,12.4 7,5.4", "3.6,12.4 2.6,16 1,17.4")
GLYPHS['z'] = _g("0.8,5.4 6.8,5.4 0.8,14 6.8,14")
GLYPHS['.'] = _g("3.4,13.2 3.5,13.2")
GLYPHS[','] = _g("3.6,12.6 2.8,15.4")
GLYPHS[':'] = _g("3.4,6.4 3.5,6.4", "3.4,12.4 3.5,12.4")
GLYPHS[';'] = _g("3.4,6.4 3.5,6.4", "3.6,12.4 2.8,15.2")
GLYPHS['-'] = _g("0.8,9.6 6.4,9.6")
GLYPHS['\u2013'] = _g("0.4,9.6 7.2,9.6")
GLYPHS['\u2014'] = _g("0,9.6 8.4,9.6")
GLYPHS['/'] = _g("7.4,0 0.6,14")
GLYPHS['('] = _g("5.6,0.6 3.4,3 2.4,7 3.4,11 5.6,13.4")
GLYPHS[')'] = _g("2.4,0.6 4.6,3 5.6,7 4.6,11 2.4,13.4")
GLYPHS['\''] = _g("3.6,0.4 3.2,3")
GLYPHS['\u2019'] = _g("3.6,0.4 3.2,3")
GLYPHS['"'] = _g("1.8,0.4 1.4,3", "5.4,0.4 5,3")
GLYPHS['\u201c'] = _g("1.8,0.4 1.4,3", "5.4,0.4 5,3")
GLYPHS['\u201d'] = _g("1.8,0.4 1.4,3", "5.4,0.4 5,3")
GLYPHS['!'] = _g("3.6,0 3.6,9.6", "3.6,13.2 3.7,13.2")
GLYPHS['?'] = _g("1,3 2.4,0.6 4.8,0.2 6.6,1.8 6.2,4.4 4,6.4 3.8,8.6", "3.8,13.2 3.9,13.2")
GLYPHS['%'] = _g("7.4,0 0.6,14", "2.6,0.6 1.2,2 1.4,4.4 3,5 4.2,3.4 3.8,1 2.6,0.6", "5.6,9.2 4.2,10.6 4.4,13 6,13.6 7.2,12.2 6.8,9.8 5.6,9.2")
GLYPHS['&'] = _g("6.8,11.8 5,8.6 2.4,6.4 1.2,4 2,1.4 4,0.4 5.4,1.8 4.6,4.4 1.6,7.6 1,11 2.4,13.6 4.8,13.8 7.4,10.4")
GLYPHS['+'] = _g("3.8,3.4 3.8,10.6", "0.6,7 7,7")
GLYPHS['$'] = _g("4,0 4,14", "6.8,2.8 5,0.6 2.6,0.8 1.2,2.8 2.4,5.4 5.4,6.8 6.6,9.4 5.2,12.4 2.4,12.6 1,10.6")
GLYPHS['*'] = _g("4,2 4,8", "1.4,3.6 6.6,6.4", "6.6,3.6 1.4,6.4")
GLYPHS['\u00b7'] = _g("3.6,9 3.7,9")
GLYPHS['\u2026'] = _g("0.8,13.2 0.9,13.2", "3.8,13.2 3.9,13.2", "6.8,13.2 6.9,13.2")
GLYPHS['\u00fc'] = GLYPHS['u']
GLYPHS['\u00e9'] = GLYPHS['e']
GLYPHS['\u00e8'] = GLYPHS['e']
GLYPHS['\u00e1'] = GLYPHS['a']
GLYPHS['\u00ed'] = GLYPHS['i']
GLYPHS['\u00f3'] = GLYPHS['o']
GLYPHS['\u00fa'] = GLYPHS['u']
GLYPHS['\u00f1'] = GLYPHS['n']
DOTS = {'i': (3.4, 2.2), 'j': (3.6, 2.2)}

NARROW = set("iljtf.,:;'!|/()[] ")
WIDE = set("mwMW@%")

def char_adv(ch, size):
    if ch == ' ':
        return size * 0.37
    if ch in NARROW:
        return size * 0.38
    if ch in WIDE:
        return size * 0.76
    if ch.isupper() or ch.isdigit():
        return size * 0.64
    return size * 0.575

def text_width(s, size, tracking=0.0):
    return sum(char_adv(ch, size) for ch in s) + tracking * max(0, len(s) - 1)

def draw_text(cv, x, y, s, size, color, weight=1.0, align='left',
              tracking=0.0, italic=False, alpha=1.0):
    """y is the baseline. weight multiplies the base stroke width."""
    total = text_width(s, size, tracking)
    if align == 'center':
        x -= total / 2.0
    elif align == 'right':
        x -= total
    sw = max(0.9, size * 0.115 * weight)
    scale = size / 14.0
    cx = x
    for ch in s:
        adv = char_adv(ch, size)
        if ch != ' ':
            glyph = GLYPHS.get(ch)
            if glyph is None:
                glyph = GLYPHS.get(ch.upper(), GLYPHS['?'])
            shear = 0.16 if italic else 0.0
            for path in glyph:
                pts = []
                for (gx, gy) in path:
                    px = cx + gx * scale + (14.0 - gy) * scale * shear
                    py = y - (14.0 - gy) * scale
                    pts.append((px, py))
                if len(pts) == 1:
                    cv.circle(pts[0][0], pts[0][1], sw * 0.72, color, alpha)
                else:
                    cv.path(pts, sw, color, alpha)
            if ch in DOTS:
                dx, dy = DOTS[ch]
                px = cx + dx * scale + (14.0 - dy) * scale * (0.16 if italic else 0.0)
                py = y - (14.0 - dy) * scale
                cv.circle(px, py, sw * 0.62, color, alpha)
        cx += adv + tracking
    return cx

def wrap_text(s, size, maxw, tracking=0.0):
    words = s.split()
    lines = []
    cur = ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if text_width(trial, size, tracking) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur); cur = wd
    if cur:
        lines.append(cur)
    return lines

def draw_block(cv, x, y, s, size, lh, color, maxw, weight=1.0, italic=False,
               tracking=0.0, max_lines=None):
    """Draw wrapped text; y is the TOP of the first line's cap height.
    Returns the y just below the last baseline."""
    lines = wrap_text(s, size, maxw, tracking)
    if max_lines is not None:
        lines = lines[:max_lines]
    baseline = y + size
    for ln in lines:
        draw_text(cv, x, baseline, ln, size, color, weight, 'left', tracking, italic)
        baseline += lh
    return baseline - lh + size * 0.32

def fit_block(cv, x, y, s, size, lh_mult, color, maxw, maxh, weight=1.0,
              italic=False, min_size=5.5):
    """Shrink size until the wrapped block fits maxh; draw it; return bottom y."""
    sz = size
    while sz > min_size:
        lines = wrap_text(s, sz, maxw)
        if len(lines) * sz * lh_mult <= maxh + 0.5:
            break
        sz -= 0.5
    return draw_block(cv, x, y, s, sz, sz * lh_mult, color, maxw, weight, italic)

# ---------------------------------------------------------------- scenes
def clip_rect(cv, x, y, w, h, fn):
    """Run fn, then repaint outside the box with paper colour is wrong for
    cards; instead scenes are drawn to fit their boxes by construction."""
    fn()

def scene_gulf(cv, x, y, w, h):
    # night sky
    cv.rect(x, y, w, h, NAVY)
    cv.rect(x, y + h * 0.55, w, h * 0.45, SEA)
    # stars
    star_pts = [(0.06, 0.10), (0.18, 0.05), (0.31, 0.14), (0.47, 0.07),
                (0.62, 0.12), (0.78, 0.05), (0.90, 0.16), (0.24, 0.22),
                (0.55, 0.20), (0.84, 0.26), (0.40, 0.03), (0.70, 0.22)]
    for (fx, fy) in star_pts:
        cv.circle(x + fx * w, y + fy * h, 1.1, (210, 220, 240))
    # moon
    cv.circle(x + w * 0.88, y + h * 0.13, 9, (238, 232, 205))
    cv.circle(x + w * 0.855, y + h * 0.11, 7.5, NAVY)
    # distant skyline (left/centre)
    sky = [(0, 78), (0, 52), (26, 52), (26, 40), (34, 40), (34, 58), (52, 58),
           (52, 30), (60, 30), (60, 20), (66, 20), (66, 58), (88, 58),
           (88, 44), (104, 44), (104, 62), (128, 62), (128, 50), (150, 50),
           (150, 78)]
    pts = [(x + px * w / 170.0, y + h * 0.55 - (78 - py) * h * 0.004 - (78 - py)) for (px, py) in sky]
    # simpler: build skyline as rectangles
    towers = [(0.00, 0.30, 0.10, 0.25), (0.11, 0.38, 0.07, 0.17), (0.19, 0.26, 0.09, 0.29),
              (0.29, 0.42, 0.06, 0.13), (0.36, 0.33, 0.08, 0.22), (0.45, 0.40, 0.06, 0.15)]
    for (fx, fy, fw, fh) in towers:
        cv.rect(x + fx * w, y + fy * h, fw * w, fh * h, (8, 14, 28))
        for wy in range(3):
            for wx in range(2):
                if (wx * 3 + wy) % 2 == 0:
                    cv.rect(x + fx * w + 4 + wx * 9, y + fy * h + 5 + wy * 11, 3.4, 4.6, AMBER)
    # missile / drone arcs
    cv.bezier((x + w * 0.06, y + h * 0.10), (x + w * 0.30, y - h * 0.06),
              (x + w * 0.58, y + h * 0.02), (x + w * 0.80, y + h * 0.52), 2.6, RED)
    cv.bezier((x + w * 0.16, y + h * 0.06), (x + w * 0.42, y - h * 0.02),
              (x + w * 0.66, y + h * 0.10), (x + w * 0.86, y + h * 0.55), 2.0, ORANGE)
    cv.bezier((x + w * 0.02, y + h * 0.30), (x + w * 0.30, y + h * 0.16),
              (x + w * 0.55, y + h * 0.24), (x + w * 0.76, y + h * 0.53), 1.8, (240, 235, 220))
    # intercept bursts
    for (fx, fy, r) in [(0.52, 0.20, 13), (0.68, 0.30, 10), (0.38, 0.13, 8)]:
        cx = x + fx * w; cy = y + fy * h
        for k in range(8):
            ang = k * math.pi / 4.0
            cv.seg(cx, cy, cx + r * math.cos(ang), cy + r * math.sin(ang), 1.7, AMBER)
        cv.circle(cx, cy, 3.2, (255, 240, 200))
    # base silhouette on shore (right)
    cv.poly([(x + w * 0.62, y + h * 0.62), (x + w * 1.0, y + h * 0.62),
             (x + w * 1.0, y + h * 0.55), (x + w * 0.94, y + h * 0.55),
             (x + w * 0.94, y + h * 0.47), (x + w * 0.90, y + h * 0.47),
             (x + w * 0.90, y + h * 0.55), (x + w * 0.80, y + h * 0.55),
             (x + w * 0.80, y + h * 0.50), (x + w * 0.70, y + h * 0.50),
             (x + w * 0.70, y + h * 0.55), (x + w * 0.62, y + h * 0.55)], (6, 10, 20))
    # radar dish
    cv.seg(x + w * 0.85, y + h * 0.47, x + w * 0.85, y + h * 0.40, 2.2, (6, 10, 20))
    cv.poly([(x + w * 0.80, y + h * 0.36), (x + w * 0.90, y + h * 0.36),
             (x + w * 0.85, y + h * 0.42)], (6, 10, 20))
    # sea sparkle
    for i in range(9):
        fx = 0.05 + 0.10 * i
        cv.seg(x + fx * w, y + h * (0.70 + 0.07 * (i % 3)), x + (fx + 0.05) * w,
               y + h * (0.70 + 0.07 * (i % 3)), 1.4, (90, 140, 175))
    # explosion glow at shore
    cv.circle(x + w * 0.80, y + h * 0.55, 10, ORANGE, 0.55)
    cv.circle(x + w * 0.80, y + h * 0.55, 5.5, AMBER, 0.8)
    cv.circle(x + w * 0.80, y + h * 0.55, 2.6, (255, 246, 210))

def scene_cop(cv, x, y, w, h):
    cv.rect(x, y, w, h, (30, 74, 96))
    # globe
    cx = x + w * 0.30; cy = y + h * 0.52; r = h * 0.36
    cv.circle(cx, cy, r, (64, 140, 170))
    cv.circle(cx, cy, r, (64, 140, 170))
    cv.poly([(cx - r * 0.7, cy - r * 0.5), (cx - r * 0.2, cy - r * 0.75),
             (cx + r * 0.1, cy - r * 0.4), (cx - r * 0.3, cy - r * 0.1),
             (cx - r * 0.65, cy - r * 0.15)], (84, 168, 110))
    cv.poly([(cx + r * 0.25, cy + r * 0.05), (cx + r * 0.7, cy - r * 0.1),
             (cx + r * 0.75, cy + r * 0.4), (cx + r * 0.35, cy + r * 0.65),
             (cx + r * 0.15, cy + r * 0.3)], (84, 168, 110))
    cv.poly([(cx - r * 0.55, cy + r * 0.35), (cx - r * 0.1, cy + r * 0.25),
             (cx + r * 0.05, cy + r * 0.6), (cx - r * 0.4, cy + r * 0.72)], (96, 178, 118))
    cv.ring(cx, cy, r, 1.6, (180, 225, 235))
    # flags row
    flag_cols = [RED, (240, 180, 40), (40, 110, 190), (40, 160, 90), (240, 240, 240), (200, 60, 140)]
    for i, fc in enumerate(flag_cols):
        fx = x + w * 0.56 + i * w * 0.068
        cv.seg(fx, y + h * 0.18, fx, y + h * 0.52, 1.6, (225, 225, 215))
        cv.poly([(fx, y + h * 0.18), (fx + w * 0.052, y + h * 0.225),
                 (fx, y + h * 0.27)], fc)
    # conference table
    cv.rect(x + w * 0.54, y + h * 0.62, w * 0.30, h * 0.08, (16, 40, 58))
    for i in range(4):
        hx = x + w * 0.575 + i * w * 0.072
        cv.circle(hx, y + h * 0.575, 4.2, (232, 200, 165))
        cv.rect(hx - 4.2, y + h * 0.615, 8.4, h * 0.09, (20, 48, 70))
    # clock at 06:00
    kx = x + w * 0.925; ky = y + h * 0.80; kr = h * 0.14
    cv.circle(kx, ky, kr, WHITE)
    cv.ring(kx, ky, kr, 1.8, INK)
    cv.seg(kx, ky, kx, ky - kr * 0.78, 2.0, INK)          # minute hand to 12
    cv.seg(kx, ky, kx, ky + kr * 0.55, 2.4, RED)           # hour hand to 6
    cv.circle(kx, ky, 1.8, INK)
    draw_text(cv, x + w * 0.545, y + h * 0.94, "06:00 GMT", h * 0.115, WHITE, 1.2)

def scene_baltic(cv, x, y, w, h):
    cv.rect(x, y, w, h, (96, 122, 140))
    cv.rect(x, y + h * 0.58, w, h * 0.42, (38, 74, 102))
    # smoke
    for (fx, fy, r, a) in [(0.52, 0.16, 15, 0.75), (0.60, 0.10, 19, 0.6),
                           (0.70, 0.07, 23, 0.45), (0.44, 0.22, 11, 0.8)]:
        cv.circle(x + fx * w, y + fy * h, r, SMOKE, a)
    # ship hull + superstructure
    hx = x + w * 0.14; hy = y + h * 0.52
    cv.poly([(hx, hy), (hx + w * 0.62, hy), (hx + w * 0.56, hy + h * 0.13),
             (hx + w * 0.07, hy + h * 0.13)], (52, 54, 58))
    cv.rect(hx + w * 0.10, hy - h * 0.16, w * 0.13, h * 0.16, (70, 72, 76))
    cv.rect(hx + w * 0.40, hy - h * 0.11, w * 0.16, h * 0.11, (70, 72, 76))
    cv.rect(hx + w * 0.26, hy - h * 0.07, w * 0.09, h * 0.07, (88, 90, 94))
    for i in range(6):
        cv.rect(hx + w * 0.05 + i * w * 0.095, hy + h * 0.035, w * 0.05, h * 0.045, (120, 60, 40))
    # fire amidships
    fx = hx + w * 0.30; fy = hy - h * 0.02
    cv.poly([(fx - 13, fy), (fx - 4, fy - h * 0.30), (fx + 3, fy - h * 0.13),
             (fx + 8, fy - h * 0.34), (fx + 15, fy)], ORANGE)
    cv.poly([(fx - 7, fy), (fx, fy - h * 0.20), (fx + 7, fy)], AMBER)
    cv.poly([(fx - 3, fy), (fx + 1, fy - h * 0.11), (fx + 4, fy)], (255, 240, 190))
    # lifeboat
    bx = x + w * 0.80; by = y + h * 0.70
    cv.poly([(bx, by), (bx + w * 0.13, by), (bx + w * 0.105, by + h * 0.07),
             (bx + w * 0.025, by + h * 0.07)], (238, 120, 30))
    cv.rect(bx + w * 0.02, by - h * 0.035, w * 0.09, h * 0.035, (250, 245, 235))
    for i in range(3):
        cv.circle(bx + w * 0.035 + i * w * 0.03, by - h * 0.055, 2.6, (232, 200, 165))
    # waves
    for i in range(7):
        fx2 = 0.04 + 0.13 * i
        cv.seg(x + fx2 * w, y + h * (0.82 + 0.06 * (i % 2)), x + (fx2 + 0.07) * w,
               y + h * (0.82 + 0.06 * (i % 2)), 1.5, (130, 175, 200))
    # distant escort vessel, far left
    cv.poly([(x + w * 0.03, y + h * 0.55), (x + w * 0.11, y + h * 0.55),
             (x + w * 0.095, y + h * 0.60), (x + w * 0.045, y + h * 0.60)], (44, 52, 60))
    cv.rect(x + w * 0.055, y + h * 0.50, w * 0.03, h * 0.05, (44, 52, 60))

def _star(cv, cx, cy, r, c):
    pts = []
    for i in range(10):
        ang = -math.pi / 2.0 + i * math.pi / 5.0
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    cv.poly(pts, c)

def _mine(cv, cx, cy, r, c=(26, 28, 32)):
    for k in range(8):
        ang = k * math.pi / 4.0
        cv.seg(cx, cy, cx + r * 1.55 * math.cos(ang), cy + r * 1.55 * math.sin(ang), 1.3, c)
    cv.circle(cx, cy, r, c)
    cv.circle(cx - r * 0.3, cy - r * 0.3, r * 0.28, (120, 124, 130))

def banner_hormuz(cv, x, y, w, h):
    cv.rect(x, y, w, h * 0.58, (178, 200, 216))
    cv.rect(x, y + h * 0.58, w, h * 0.42, (52, 92, 124))
    hx = x + w * 0.14; hy = y + h * 0.50; hw = w * 0.54; hh = h * 0.30
    cols = [(178, 52, 40), (224, 148, 32), (39, 92, 160), (26, 140, 120)]
    for i in range(4):
        cv.rect(hx + hw * 0.10 + i * hw * 0.17, hy - h * 0.22, hw * 0.14, h * 0.22, cols[i])
    cv.rect(hx + hw * 0.84, hy - h * 0.34, hw * 0.09, h * 0.34, (240, 238, 230))
    cv.poly([(hx, hy), (hx + hw, hy), (hx + hw * 0.92, hy + hh), (hx + hw * 0.08, hy + hh)], (34, 38, 46))
    cv.rect(hx + hw * 0.10, hy + hh * 0.52, hw * 0.80, hh * 0.34, (168, 52, 40))
    cv.seg(x + w * 0.06, y + h * 0.80, x + w * 0.20, y + h * 0.80, 1.2, (170, 205, 225))
    cv.seg(x + w * 0.30, y + h * 0.88, x + w * 0.46, y + h * 0.88, 1.2, (170, 205, 225))
    _mine(cv, x + w * 0.87, y + h * 0.74, h * 0.15)

def banner_sudan(cv, x, y, w, h):
    cv.rect(x, y, w, h, (233, 206, 152))
    cv.poly([(x, y + h), (x + w * 0.52, y + h * 0.42), (x + w * 0.72, y + h * 0.42),
             (x + w * 0.34, y + h)], (122, 116, 106))
    cv.seg(x + w * 0.10, y + h * 0.90, x + w * 0.56, y + h * 0.50, 1.2, (240, 236, 220))
    _mine(cv, x + w * 0.44, y + h * 0.60, h * 0.13, (40, 36, 30))
    tx = x + w * 0.80; ty = y + h * 0.50; tr = h * 0.34
    cv.poly([(tx, ty - tr), (tx + tr * 0.95, ty + tr * 0.8), (tx - tr * 0.95, ty + tr * 0.8)], (250, 246, 235))
    pts = [(tx, ty - tr), (tx + tr * 0.95, ty + tr * 0.8), (tx - tr * 0.95, ty + tr * 0.8), (tx, ty - tr)]
    cv.path(pts, 2.0, RED)
    cv.seg(tx, ty - tr * 0.25, tx, ty + tr * 0.32, 2.2, RED)
    cv.circle(tx, ty + tr * 0.58, 1.6, RED)
    cv.circle(x + w * 0.08, y + h * 0.22, h * 0.16, (245, 178, 60))

def banner_gaza(cv, x, y, w, h):
    cv.rect(x, y, w, h, (216, 226, 208))
    cv.rect(x, y + h * 0.78, w, h * 0.22, (168, 160, 138))
    vx = x + w * 0.30; vy = y + h * 0.34; vw = w * 0.40; vh = h * 0.44
    cv.rect(vx, vy, vw * 0.72, vh, (250, 248, 242))
    cv.poly([(vx + vw * 0.72, vy + vh * 0.28), (vx + vw, vy + vh * 0.62),
             (vx + vw, vy + vh), (vx + vw * 0.72, vy + vh)], (240, 238, 232))
    cv.rect(vx + vw * 0.80, vy + vh * 0.42, vw * 0.13, vh * 0.26, (150, 180, 200))
    cv.rect(vx + vw * 0.30 - 1.6, vy + vh * 0.20, 3.2, vh * 0.5, RED)
    cv.rect(vx + vw * 0.30 - vh * 0.25, vy + vh * 0.45 - 1.6, vh * 0.5, 3.2, RED)
    cv.circle(vx + vw * 0.20, vy + vh, h * 0.11, (30, 30, 32))
    cv.circle(vx + vw * 0.82, vy + vh, h * 0.11, (30, 30, 32))
    dx = x + w * 0.86; dy = y + h * 0.26
    cv.rect(dx - w * 0.035, dy - 1.2, w * 0.07, 2.4, (40, 42, 48))
    for (sx, sy) in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
        cv.seg(dx, dy, dx + sx * w * 0.055, dy + sy * h * 0.20, 1.4, (40, 42, 48))
        cv.circle(dx + sx * w * 0.055, dy + sy * h * 0.20, 1.7, (40, 42, 48))

def banner_iran(cv, x, y, w, h):
    cv.rect(x, y, w, h, NAVY2)
    px = x + w * 0.30; top = y + h * 0.10; bot = y + h * 0.94
    cv.seg(px - w * 0.055, bot, px, top, 1.8, (10, 16, 26))
    cv.seg(px + w * 0.055, bot, px, top, 1.8, (10, 16, 26))
    cv.seg(px - w * 0.13, y + h * 0.30, px + w * 0.13, y + h * 0.30, 1.8, (10, 16, 26))
    cv.seg(px - w * 0.10, y + h * 0.52, px + w * 0.10, y + h * 0.52, 1.8, (10, 16, 26))
    cv.seg(px - w * 0.13, y + h * 0.30, px + w * 0.10, y + h * 0.52, 1.1, (10, 16, 26))
    cv.seg(px + w * 0.13, y + h * 0.30, px - w * 0.10, y + h * 0.52, 1.1, (10, 16, 26))
    cv.seg(x + w * 0.04, y + h * 0.22, px - w * 0.13, y + h * 0.30, 1.1, (120, 140, 175))
    cv.seg(px + w * 0.13, y + h * 0.30, x + w * 0.58, y + h * 0.18, 1.1, (120, 140, 175))
    bx = x + w * 0.74; by = y + h * 0.50; br = h * 0.36
    cv.poly([(bx + br * 0.28, by - br), (bx - br * 0.42, by + br * 0.18), (bx - br * 0.02, by + br * 0.18),
             (bx - br * 0.28, by + br), (bx + br * 0.46, by - br * 0.14), (bx + br * 0.06, by - br * 0.14)], AMBER)

def banner_poland(cv, x, y, w, h):
    cv.rect(x, y, w, h, (240, 238, 232))
    cv.rect(x, y + h * 0.72, w, h * 0.28, (196, 44, 38))
    cx = x + w * 0.50; cy = y + h * 0.46; sw2 = w * 0.10; sh = h * 0.40
    shield = [(cx - sw2, cy - sh), (cx + sw2, cy - sh), (cx + sw2, cy + sh * 0.25),
              (cx, cy + sh), (cx - sw2, cy + sh * 0.25)]
    cv.poly(shield, (39, 92, 160))
    for i in range(len(shield)):
        a = shield[i]; b = shield[(i + 1) % len(shield)]
        cv.seg(a[0], a[1], b[0], b[1], 1.4, INK)
    _star(cv, cx, cy - sh * 0.08, sh * 0.42, WHITE)
    _star(cv, x + w * 0.16, y + h * 0.34, h * 0.14, (39, 92, 160))
    _star(cv, x + w * 0.84, y + h * 0.34, h * 0.14, (39, 92, 160))

def banner_mexico(cv, x, y, w, h):
    cv.rect(x, y, w, h, (238, 220, 190))
    cv.rect(x, y + h * 0.80, w, h * 0.20, (196, 172, 128))
    bx = x + w * 0.10; bw = w * 0.26; btop = y + h * 0.22
    cv.rect(bx, btop, bw, y + h * 0.80 - btop, (74, 62, 50))
    cv.rect(bx + bw * 0.14, btop - h * 0.10, bw * 0.72, h * 0.10, (74, 62, 50))
    for r in range(2):
        for cc in range(3):
            cv.rect(bx + bw * 0.14 + cc * bw * 0.26, btop + h * 0.10 + r * h * 0.24, bw * 0.16, h * 0.14, AMBER)
    hx = x + w * 0.66; hy = y + h * 0.52; hr = h * 0.30
    cv.ring(hx - hr * 0.72, hy, hr, 2.4, (96, 96, 104))
    cv.ring(hx + hr * 0.72, hy, hr, 2.4, (96, 96, 104))
    cv.seg(hx - hr * 0.30, hy - hr * 0.92, hx + hr * 0.30, hy - hr * 0.92, 2.0, (96, 96, 104))
    cv.seg(hx - hr * 0.72, hy - hr * 0.9, hx - hr * 0.72, hy - hr * 1.25, 2.2, (96, 96, 104))
    cv.seg(hx + hr * 0.72, hy - hr * 0.9, hx + hr * 0.72, hy - hr * 1.25, 2.2, (96, 96, 104))

def banner_peru(cv, x, y, w, h):
    cv.rect(x, y, w, h, (196, 214, 226))
    cv.poly([(x + w * 0.04, y + h * 0.82), (x + w * 0.30, y + h * 0.16),
             (x + w * 0.54, y + h * 0.82)], (110, 120, 130))
    cv.poly([(x + w * 0.235, y + h * 0.335), (x + w * 0.30, y + h * 0.16),
             (x + w * 0.365, y + h * 0.335), (x + w * 0.30, y + h * 0.42)], WHITE)
    cv.poly([(x + w * 0.44, y + h * 0.82), (x + w * 0.68, y + h * 0.26),
             (x + w * 0.94, y + h * 0.82)], (128, 136, 142))
    cv.poly([(x + w * 0.615, y + h * 0.415), (x + w * 0.68, y + h * 0.26),
             (x + w * 0.745, y + h * 0.415), (x + w * 0.68, y + h * 0.48)], WHITE)
    cv.rect(x, y + h * 0.82, w, h * 0.18, (150, 138, 112))
    crack = [(x + w * 0.40, y + h * 0.83), (x + w * 0.47, y + h * 0.90),
             (x + w * 0.44, y + h * 0.94), (x + w * 0.53, y + h * 0.99)]
    cv.path(crack, 1.8, (52, 44, 34))
    crack2 = [(x + w * 0.62, y + h * 0.84), (x + w * 0.67, y + h * 0.91), (x + w * 0.65, y + h * 0.97)]
    cv.path(crack2, 1.4, (52, 44, 34))

def banner_belgium(cv, x, y, w, h):
    cv.rect(x, y, w, h, (178, 200, 216))
    cv.ellipse(x + w * 0.16, y + h * 0.30, w * 0.075, h * 0.15, WHITE)
    cv.ellipse(x + w * 0.86, y + h * 0.24, w * 0.06, h * 0.12, WHITE)
    px = x + w * 0.50; py = y + h * 0.52
    cv.poly([(px - w * 0.26, py), (px - w * 0.05, py - h * 0.13), (px + w * 0.20, py - h * 0.10),
             (px + w * 0.28, py), (px + w * 0.20, py + h * 0.09), (px - w * 0.05, py + h * 0.11)], (34, 42, 56))
    cv.poly([(px - w * 0.24, py - h * 0.02), (px - w * 0.33, py - h * 0.30),
             (px - w * 0.26, py - h * 0.30), (px - w * 0.13, py - h * 0.04)], (34, 42, 56))
    cv.poly([(px + w * 0.02, py + h * 0.10), (px - w * 0.06, py + h * 0.30),
             (px + w * 0.03, py + h * 0.30), (px + w * 0.12, py + h * 0.08)], (34, 42, 56))
    for i in range(5):
        cv.circle(px - w * 0.10 + i * w * 0.055, py - h * 0.045, 1.3, (200, 220, 235))
    cv.poly([(x + w * 0.70, y), (x + w * 0.86, y), (x + w * 0.42, y + h), (x + w * 0.26, y + h)], RED, 0.88)

# coarse world-map continent polygons in a 300x150 box (x,y = top-left)
CONTINENTS = [
    [(6, 40), (24, 24), (48, 15), (74, 14), (88, 22), (86, 36), (74, 42),
     (70, 54), (60, 62), (50, 58), (44, 66), (36, 58), (24, 56), (10, 52)],  # North America
    [(48, 78), (62, 74), (72, 84), (70, 104), (63, 126), (56, 140),
     (51, 118), (45, 96)],                                                  # South America
    [(126, 36), (132, 22), (146, 17), (160, 22), (178, 14), (214, 13),
     (244, 16), (264, 24), (262, 38), (246, 40), (238, 48), (242, 60),
     (235, 73), (227, 58), (220, 46), (205, 44), (194, 50), (182, 43),
     (168, 46), (160, 38), (146, 44), (132, 42)],                           # Eurasia
    [(136, 54), (156, 50), (172, 56), (176, 74), (168, 98), (158, 116),
     (148, 118), (140, 96), (134, 72)],                                     # Africa
    [(240, 94), (262, 90), (278, 98), (272, 116), (250, 118), (238, 106)],  # Australia
    [(282, 122), (292, 118), (294, 128), (286, 136), (281, 130)],           # New Zealand
]
PINS = [  # (fx, fy) inside map box, for stories 1..13
    (0.605, 0.39),  # 1 Gulf (Bahrain/Kuwait)
    (0.55, 0.27),  # 2 COP31 Antalya
    (0.50, 0.125),  # 3 Baltic / Gulf of Finland
    (0.66, 0.43),  # 4 Hormuz
    (0.52, 0.56),  # 5 Sudan
    (0.56, 0.35),  # 6 Gaza
    (0.655, 0.30),  # 7 Iran power (Tehran)
    (0.475, 0.225),  # 8 Poland
    (0.155, 0.44),  # 9 Mexico
    (0.185, 0.74),  # 10 Peru
    (0.435, 0.165),  # 11 Belgium
    (0.085, 0.37),  # 12 Las Vegas
    (0.80, 0.35),  # 13 Hong Kong
]

def scene_map(cv, x, y, w, h):
    cv.rect(x, y, w, h, (233, 226, 205))
    sx = w / 300.0; sy = h / 150.0
    for cont in CONTINENTS:
        pts = [(x + px * sx, y + py * sy) for (px, py) in cont]
        cv.poly(pts, (168, 158, 128))
        pts2 = [(x + px * sx, y + py * sy) for (px, py) in cont]
        for i in range(len(pts2)):
            a = pts2[i]; b = pts2[(i + 1) % len(pts2)]
            cv.seg(a[0], a[1], b[0], b[1], 1.0, (120, 110, 84))
    for idx, (fx, fy) in enumerate(PINS, start=1):
        px = x + fx * w; py = y + fy * h
        cv.circle(px, py, 6.6, RED)
        cv.ring(px, py, 6.6, 1.1, WHITE)
        label = str(idx)
        tw = text_width(label, 7.8)
        draw_text(cv, px - tw / 2.0, py + 2.7, label, 7.8, WHITE, 1.6)

# ---------------------------------------------------------------- page
def hline(cv, x, y, w, t, c=INK):
    cv.rect(x, y, w, t, c)

def card_box(cv, x, y, w, h, fill=CARD):
    cv.rect(x, y, w, h, fill)
    cv.rect(x, y, w, 1.4, INK); cv.rect(x, y + h - 1.4, w, 1.4, INK)
    cv.rect(x, y, 1.4, h, INK); cv.rect(x + w - 1.4, y, 1.4, h, INK)

def kicker_loc(cv, x, y, kick, loc, ksize=10.0):
    draw_text(cv, x, y + ksize, kick, ksize, RED, 1.35)
    if loc:
        draw_text(cv, x, y + ksize + ksize * 1.45, loc, ksize * 0.82, SOFT, 1.0)
    return y + ksize * (2.55 if loc else 1.35)

def build():
    cv = Canvas(W, H, PAPER)
    MX = 28.0; CW = W - 2 * MX
    # ---- masthead
    draw_text(cv, MX, 27, "THE WORLD IN ONE DAY", 10.5, INK, 1.4)
    draw_text(cv, W - MX, 27, "36 STORIES \u00b7 7 REGIONS \u00b7 AS REPORTED ON SUNDAY 22 NOVEMBER 2026",
              8.2, SOFT, 1.1, align='right')
    hline(cv, MX, 33, CW, 3.2)
    draw_text(cv, MX - 2, 92, "Sunday 22 November 2026", 55, INK, 1.55)
    hline(cv, MX, 100, CW, 1.2)
    draw_block(cv, MX, 106,
               "Iran strikes US bases in the Gulf \u00b7 COP31 nears a deal in Antalya \u00b7 "
               "Russian ship ablaze in the Baltic \u00b7 Sudan landmine kills 22",
               13.5, 18, SOFT, CW, 1.05, italic=True)
    hline(cv, MX, 136, CW, 1.0, FAINT)
    # ---- stat band
    stats = [
        ("2", "tankers struck leaving Hormuz \u00b7 UKMTO"),
        ("16", "crew off the burning Sparta II \u00b7 Finland"),
        ("0600", "GMT: COP31 session to approve the deal \u00b7 Reuters"),
        ("22", "killed by a landmine in N. Kordofan \u00b7 Darfur24"),
        ("2 hrs", "daily power cuts begin in Iran \u00b7 Tavanir"),
        ("1,671", "killed in Gaza since the 2025 truce \u00b7 ministry"),
    ]
    sw = CW / 6.0
    for i, (num, cap) in enumerate(stats):
        sx = MX + i * sw
        if i:
            cv.rect(sx, 144, 1.0, 44, FAINT)
        draw_text(cv, sx + 8, 166, num, 25, RED if i in (0, 3) else INK, 1.5)
        draw_block(cv, sx + 8, 172, cap, 7.8, 10.2, SOFT, sw - 16, 0.95)
    hline(cv, MX, 192, CW, 1.0, FAINT)
    # ---- region bar (tally of the 36 stories on this page)
    regions = [("EUROPE 10", 10), ("ASIA 8", 8), ("MIDDLE EAST 7", 7),
               ("AMERICAS 6", 6), ("AF 2", 2), ("OC 1", 1), ("GL 2", 2)]
    rx = MX
    total = sum(n for _, n in regions)
    for i, (label, n) in enumerate(regions):
        segw = CW * n / total
        cv.rect(rx, 198, segw - 2, 17, REGION_COLORS[i])
        tsize = 8.6 if n > 1 else 7.0
        tw = text_width(label, tsize)
        draw_text(cv, rx + (segw - 2 - tw) / 2.0, 210.5, label, tsize, WHITE, 1.25)
        rx += segw
    draw_text(cv, MX, 222, "STORIES BY REGION \u00b7 TALLIED FROM THE 36 STORIES BELOW", 6.8, FAINT, 1.0)
    # ---- hero
    HY = 227.0; HH = 170.0
    card_box(cv, MX, HY, CW, HH)
    cv.rect(MX, HY, CW, 4, RED)
    scene_gulf(cv, MX + CW - 330, HY + 10, 320, HH - 20)
    hx = MX + 14
    ky = kicker_loc(cv, hx, HY + 12, "1 \u00b7 GULF: STRIKES", "BAHRAIN \u00b7 KUWAIT \u2014 WAR", 11.5)
    bend = draw_block(cv, hx, ky + 2,
                      "Iran strikes US bases in Bahrain and Kuwait in missile-and-drone barrage",
                      25.5, 30, INK, 592, 1.35)
    fit_block(cv, hx, bend + 8,
              "The IRGC says it destroyed two Patriot radars at al-Riffa and Awali; Bahrain says an "
              "Iranian attack set an industrial site ablaze in Sitra. CENTCOM calls the claims false: "
              "no US casualties, no base damage. (Reuters, Al Jazeera)",
              11, 1.36, SOFT, 592, HY + HH - (bend + 8) - 10, 1.0)
    # ---- two half cards
    TY = 402.0; TH = 156.0; TW2 = (CW - 14) / 2.0
    halves = [
        ("2 \u00b7 COP31: NEAR A DEAL", "ANTALYA, T\u00dcRKIYE \u00b7 CLIMATE",
         "COP31 nears a deal as a new text is tabled after overtime talks",
         "Turkish and Australian hosts say the fossil-fuel and finance gaps are now bridged; "
         "objections were due by 0300 GMT, adoption session set for 0600 GMT Sunday. "
         "Not yet adopted when drawn. (Reuters)", scene_cop),
        ("3 \u00b7 BALTIC: SHIP ABLAZE", "GULF OF FINLAND \u00b7 UKRAINE WAR",
         "Russian military cargo ship ablaze in the Baltic after drone strike",
         "Sparta II, bound for Kaliningrad, was hit west of Gogland and drifted into Finnish "
         "waters; all 16 crew evacuated. Finland leads the firefighting and warns the war is "
         "spilling over. (Reuters, Finnish Defence Forces)", scene_baltic),
    ]
    for i, (kick, loc, head, deck, scene) in enumerate(halves):
        cx0 = MX + i * (TW2 + 14)
        card_box(cv, cx0, TY, TW2, TH)
        ky = kicker_loc(cv, cx0 + 12, TY + 10, kick, loc, 10.5)
        bend = draw_block(cv, cx0 + 12, ky + 1, head, 17.2, 20.5, INK, TW2 - 24, 1.32)
        scene_h = 44.0
        fit_block(cv, cx0 + 12, bend + 5, deck, 9.8, 1.34, SOFT, TW2 - 24,
                  TY + TH - scene_h - 12 - (bend + 5), 0.95)
        scene(cv, cx0 + 12, TY + TH - scene_h - 8, TW2 - 24, scene_h)
    # ---- three cards
    RY = 563.0; RH = 129.0; RW3 = (CW - 16) / 3.0
    triples = [
        ("4 \u00b7 HORMUZ: TANKERS HIT", "STRAIT OF HORMUZ \u00b7 IRAN WAR",
         "Two tankers hit leaving Hormuz as Iran tightens its grip on shipping",
         "One struck at the stern, one in the engine room, no casualties. Tehran says ships must "
         "coordinate with Iran; the IRGC claims the tankers hit mines. (UKMTO, Al Jazeera)",
         banner_hormuz),
        ("5 \u00b7 SUDAN: LANDMINE", "NORTH KORDOFAN \u00b7 SUDAN WAR",
         "Landmine kills 22 on a road to El-Obeid",
         "A passenger tuk-tuk hit the mine; women and children are among the dead. (Darfur24)",
         banner_sudan),
        ("6 \u00b7 GAZA: AID VAN HIT", "GAZA CITY \u00b7 CEASEFIRE",
         "Drone strike on a Gaza food-aid van kills three",
         "The IDF says it targeted Islamic Jihad members. (Al Jazeera, Gaza ministry)",
         banner_gaza),
    ]
    for i, (kick, loc, head, deck, banner) in enumerate(triples):
        cx0 = MX + i * (RW3 + 8)
        card_box(cv, cx0, RY, RW3, RH)
        banner(cv, cx0 + 1.4, RY + 1.4, RW3 - 2.8, 21)
        ky = kicker_loc(cv, cx0 + 10, RY + 26, kick, loc, 8.8)
        bend = draw_block(cv, cx0 + 10, ky, head, 14.2, 17, INK, RW3 - 20, 1.3)
        fit_block(cv, cx0 + 10, bend + 4, deck, 8.8, 1.3, SOFT, RW3 - 20,
                  RY + RH - (bend + 4) - 6, 0.95)
    # ---- five small cards
    FY = 697.0; FH = 108.0; FW5 = (CW - 28) / 5.0
    fives = [
        ("7 \u00b7 IRAN: POWER", "TEHRAN \u00b7 ENERGY",
         "Iran begins rationing electricity from Sunday",
         "Cuts of up to two hours a day as gas output lags. (RFE/RL)", banner_iran),
        ("8 \u00b7 POLAND: NATO", "WARSAW \u00b7 NATO",
         "Rutte in Warsaw: all of NATO stands with Poland",
         "The visit follows Friday's Russian missile incursion. (TVP World, AFP)", banner_poland),
        ("9 \u00b7 MEXICO: CARTEL", "SINALOA \u00b7 CRIME",
         "Mexico captures cartel boss 'El Chapo Isidro'",
         "Taken with two other leaders of his gang. (Reuters)", banner_mexico),
        ("10 \u00b7 PERU: QUAKE", "JUN\u00cdN \u00b7 EARTHQUAKE",
         "Peru quake toll reaches one dead, 16 injured",
         "Officials update the count from Friday's M6.7 Andes quake, felt in Lima. (Officials)", banner_peru),
        ("11 \u00b7 BELGIUM: SKIES", "BRUSSELS \u00b7 LABOUR",
         "Belgian national strike to ground flights on Monday",
         "No regular air traffic 07:00\u201321:00, Skeyes says. (AFP)", banner_belgium),
    ]
    for i, (kick, loc, head, deck, banner) in enumerate(fives):
        cx0 = MX + i * (FW5 + 7)
        card_box(cv, cx0, FY, FW5, FH)
        banner(cv, cx0 + 1.4, FY + 1.4, FW5 - 2.8, 19)
        ky = kicker_loc(cv, cx0 + 8, FY + 23, kick, loc, 7.9)
        bend = draw_block(cv, cx0 + 8, ky, head, 11.6, 14, INK, FW5 - 16, 1.3)
        fit_block(cv, cx0 + 8, bend + 3, deck, 8.2, 1.28, SOFT, FW5 - 16,
                  FY + FH - (bend + 3) - 5, 0.95)
    # ---- bottom band: map + briefs
    BY = 810.0; BH = 114.0
    hline(cv, MX, BY - 4, CW, 1.6)
    draw_text(cv, MX, BY + 10, "WHERE IT HAPPENED", 9.5, INK, 1.3)
    scene_map(cv, MX, BY + 14, 296, 80)
    draw_text(cv, MX, BY + 106, "NUMBERED AS THE STORIES ABOVE \u00b7 PINS 1\u201313", 6.6, FAINT, 1.0)
    bx = MX + 312
    draw_text(cv, bx, BY + 10, "ALSO ON SUNDAY 22 NOVEMBER", 9.5, RED, 1.3)
    briefs_a = [
        "12 Las Vegas: Verstappen on pole for GP; Antonelli -5 places (F1)",
        "13 Hong Kong: Election Committee voting opens; 5,700 voters (AFP)",
        "14 Doha: Iran talks to Qatari mediators; Trump wants deal (AJ)",
        "15 Finland: Russian helicopter suspected in airspace (MoD)",
        "16 Helsinki: PM Orpo - Ukraine has right to fight back (Reuters)",
        "17 Washington: 900,000 AI chips cleared for China (Reuters)",
        "18 Washington: Trump downplays reported FBI hack (Reuters)",
        "19 Berlin: Coalition of the Willing presses Moscow (DW)",
        "20 Geneva: 1 in 4 women cannot refuse sex (UNFPA)",
        "21 Manila: China bomber turns back 170 km out (AFP)",
        "22 Brussels: EU 3% big-tech levy proposed; France rejects (AFP)",
        "23 Paris: police probe Depardieu, Houellebecq (AFP)",
    ]
    briefs_b = [
        "24 Delhi: India hockey coach Bhangu dies at 86 (PTI)",
        "25 Jeddah: Air India extends suspension to Nov 24 (ANI)",
        "26 Toronto: two men shot dead outside Walmart (AFP)",
        "27 Wellington: India battle wind, NZ in first Test (PTI)",
        "28 Ranchi: Cyclone Akvan remnants cancel 14 flights (ANI)",
        "29 Philippines: M5.9 quake, 586 km deep, off Palawan (EMSC)",
        "30 Japan poll: record 62% feel friendly to S. Korea (JKN)",
        "31 Nigeria: toll in funeral-boat capsize reaches 24 (AP)",
        "32 Basra: power-station fire kills 4, injures 35 (Reuters)",
        "33 Kyiv: Zelenskiy says Abu Dhabi talks resume (Reuters)",
        "34 Lisbon: thousands march over living costs (Reuters)",
        "35 Banda Sea: M6.8 quake NE of Dili, no tsunami (GFZ)",
        "36 Geneva: 'killer robot' talks pledge 2028 rules (Reuters)",
    ]
    colw = (W - MX - bx - 10) / 2.0
    for j, items in enumerate((briefs_a, briefs_b)):
        cx0 = bx + j * (colw + 10)
        yy = BY + 15
        for it in items:
            yy = draw_block(cv, cx0, yy, it, 7.4, 10.8, SOFT, colw, 0.95) + 0.7
    # ---- date check
    DY = 964.0
    cv.rect(MX, DY, CW, 33, PAPER2)
    cv.rect(MX, DY, CW, 1.4, RED); cv.rect(MX, DY + 31.6, CW, 1.4, RED)
    cv.rect(MX, DY, 1.4, 33, RED); cv.rect(MX + CW - 1.4, DY, 1.4, 33, RED)
    draw_block(cv, MX + 8, DY + 4,
               "DATE CHECK \u00b7 Left out as earlier news: Kryvyi Rih 'triple-tap' strike (Fri 20) \u00b7 Wall Street's AI "
               "sell-off (Fri 20) \u00b7 Kerch Bridge strike (Wed) \u00b7 Xi\u2013Trump\u2013Putin Shenzhen summit (19 Nov). The Peru quake "
               "was Friday evening's; only Sunday's toll update counts. The Nigeria boat sank Friday; only the "
               "weekend toll of 24 counts. Not confirmed when drawn (~03:00 UTC): COP31 "
               "adoption (0600 GMT session) \u00b7 Las Vegas GP result (~04:00 UTC) \u00b7 IRGC radar claims (CENTCOM denies).",
               6.9, 9.4, SOFT, CW - 16, 0.95)
    # ---- footer
    hline(cv, MX, 1003, CW, 1.2)
    draw_text(cv, MX, 1016,
              "Every story here happened, or was first reported, on Sunday 22 November 2026 in at least one time zone. "
              "Officials' counts and claims are attributed.",
              7.3, SOFT, 1.0)
    draw_text(cv, W - MX, 1016, "Sources named beside each story \u00b7 Original drawings", 7.3, INK, 1.1, align='right')
    return cv

def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    cv = build()
    rgb = cv.downscale_png_rows()
    path = os.path.join(outdir, "entry.png")
    n = write_png(path, rgb, W, H)
    print("wrote", path, n, "bytes")

if __name__ == "__main__":
    main()
