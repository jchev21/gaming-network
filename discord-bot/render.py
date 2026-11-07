"""Draws the dashboard image: a month calendar, a This week list, and Important days."""
import calendar
import io
import math
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 700
BG = (12, 10, 24)
PANEL = (23, 19, 44)
CELL = (35, 29, 66)
LINE = (58, 50, 98)
TEXT = (240, 238, 252)
MUTED = (172, 166, 205)
GOLD = (255, 205, 112)
PURPLE = (150, 100, 245)
BLUE = (96, 135, 255)


def _hex(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _font(size, bold=False):
    names = (["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"] if bold
             else ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _fit(draw, text, font, width):
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "...", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "..."


def _star(draw, cx, cy, r, fill):
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = r if i % 2 == 0 else r * 0.45
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=fill)


def _clock(dt):
    return dt.strftime("%I:%M %p").lstrip("0")


def _bar(img, box, c1, c2, height=6, radius=20):
    """Purple-to-blue gradient strip across the top of a rounded panel."""
    x1, y1, x2, y2 = box
    w = x2 - x1
    grad = Image.new("RGB", (w, height))
    gd = ImageDraw.Draw(grad)
    for i in range(w):
        t = i / max(w - 1, 1)
        gd.line((i, 0, i, height), fill=tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)))
    mask = Image.new("L", (w, y2 - y1), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, y2 - y1 - 1), radius=radius, fill=255)
    img.paste(grad, (x1, y1), mask.crop((0, 0, w, height)))


def render_calendar(events, now, accent="#a78bfa"):
    """events: dicts with start (unix ts), title, source, important. now: aware datetime."""
    acc = _hex(accent)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    items = []
    for e in events:
        items.append({**e, "dt": datetime.fromtimestamp(e["start"], now.tzinfo)})
    items.sort(key=lambda e: e["dt"])
    by_day = {}
    for e in items:
        by_day.setdefault(e["dt"].date(), []).append(e)

    # ----- left: month grid -----
    d.rounded_rectangle((24, 24, 744, H - 24), radius=20, fill=PANEL)
    _bar(img, (24, 24, 744, H - 24), PURPLE, BLUE)
    d.text((52, 40), now.strftime("%B %Y"), font=_font(34, True), fill=TEXT)
    x0, y0, cw, ch = 52, 126, 96, 100
    d.text((724 - d.textlength("Next 5 weeks", font=_font(14)), 54), "Next 5 weeks",
           font=_font(14), fill=MUTED)
    for i, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]):
        d.text((x0 + i * cw + 14, 98), name, font=_font(13, True), fill=MUTED)

    today = now.date()
    start = today - timedelta(days=(today.weekday() + 1) % 7)  # Sunday of this week
    weeks = [[start + timedelta(days=7 * r + c) for c in range(7)] for r in range(5)]
    for r, week in enumerate(weeks):
        for c, day in enumerate(week):
            x, y = x0 + c * cw, y0 + r * ch
            past = day < today
            day_events = by_day.get(day, [])
            important = any(e.get("important") for e in day_events)
            box = (x + 3, y + 3, x + cw - 3, y + ch - 3)
            outline = GOLD if important else (BLUE if day == today else None)
            d.rounded_rectangle(box, radius=12, fill=CELL, outline=outline, width=2 if outline else 0)
            number = f"{day.strftime('%b')} 1" if day.day == 1 else str(day.day)
            d.text((x + 14, y + 12), number, font=_font(18, True),
                   fill=BLUE if day == today else (MUTED if past else TEXT))
            if important:
                _star(d, x + cw - 20, y + 22, 8, GOLD)
            for i, e in enumerate(day_events[:3]):
                color = GOLD if e.get("important") else acc
                cx = x + 18 + i * 16
                d.ellipse((cx - 5, y + ch - 28, cx + 5, y + ch - 18), fill=color)
            if len(day_events) > 3:
                d.text((x + 18 + 3 * 16, y + ch - 32), f"+{len(day_events) - 3}",
                       font=_font(13, True), fill=MUTED)

    # ----- right: this week -----
    px = 768
    right = W - 24
    d.rounded_rectangle((px, 24, right, H - 24), radius=20, fill=PANEL)
    _bar(img, (px, 24, right, H - 24), BLUE, PURPLE)
    tx = px + 28
    width = right - tx - 28
    d.text((tx, 40), "This week", font=_font(26, True), fill=TEXT)

    week_end = today + timedelta(days=7)
    week = [e for e in items if today <= e["dt"].date() < week_end][:5]
    y = 92
    if not week:
        d.text((tx, y + 8), "Nothing scheduled this week.", font=_font(16), fill=MUTED)
    for e in week:
        label = e["dt"].strftime("%a %b %d").upper()
        d.text((tx, y), label, font=_font(13, True), fill=GOLD if e.get("important") else acc)
        d.text((tx, y + 20), _fit(d, e["title"], _font(18, True), width - 26),
               font=_font(18, True), fill=TEXT)
        sub = f"{_clock(e['dt'])} · {e['source']}"
        d.text((tx, y + 46), _fit(d, sub, _font(14), width), font=_font(14), fill=MUTED)
        if e.get("important"):
            _star(d, right - 40, y + 32, 9, GOLD)
        d.line((tx, y + 70, right - 28, y + 70), fill=LINE, width=1)
        y += 78

    # ----- right: important days -----
    iy = 92 + 5 * 78 + 10
    d.text((tx, iy), "Important days", font=_font(22, True), fill=GOLD)
    horizon = today + timedelta(days=45)
    big = [e for e in items if e.get("important") and today <= e["dt"].date() < horizon][:3]
    iy += 40
    if not big:
        d.text((tx, iy), "None starred yet.", font=_font(16), fill=MUTED)
    for e in big:
        _star(d, tx + 9, iy + 12, 9, GOLD)
        line = f"{e['dt'].strftime('%b %d').upper()}  {e['title']}"
        d.text((tx + 28, iy), _fit(d, line, _font(16, True), width - 28),
               font=_font(16, True), fill=TEXT)
        iy += 34

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf
