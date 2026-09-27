"""Frame generation: canvas compositing, ocean scene, rain, tickers, bars.

Everything here is a pure function of (size, phase, conditions) so frames are
reproducible and testable without a terminal. The curses layer only paints
what these return.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import art

SPARK_CHARS = "▁▂▃▄▅▆▇█"
RAIN_GLYPHS = "01│░·abcdef§≡xz#$%&*"


class Canvas:
    """A grid of characters, each tagged with a theme colour key."""

    def __init__(self, width: int, height: int, key: str = "text") -> None:
        self.width = max(0, width)
        self.height = max(0, height)
        self.chars = [[" "] * self.width for _ in range(self.height)]
        self.keys = [[key] * self.width for _ in range(self.height)]

    def put(self, x: int, y: int, text: str, key: str = "text",
            transparent: str | None = None) -> None:
        """Draw `text` at (x, y); cells equal to `transparent` are skipped."""
        if not (0 <= y < self.height):
            return
        for i, char in enumerate(text):
            col = x + i
            if col < 0 or col >= self.width:
                continue
            if transparent is not None and char == transparent:
                continue
            self.chars[y][col] = char
            self.keys[y][col] = key

    def blit(self, x: int, y: int, lines: list[str], key: str = "text",
             transparent: str | None = " ") -> None:
        for row, line in enumerate(lines):
            self.put(x, y + row, line, key, transparent=transparent)

    def runs(self) -> list[list[tuple[int, str, str]]]:
        """Per row, contiguous (x, text, key) runs - one curses call each."""
        out: list[list[tuple[int, str, str]]] = []
        for y in range(self.height):
            row: list[tuple[int, str, str]] = []
            start = 0
            while start < self.width:
                key = self.keys[y][start]
                end = start
                while end < self.width and self.keys[y][end] == key:
                    end += 1
                text = "".join(self.chars[y][start:end])
                if text.strip():
                    row.append((start, text, key))
                start = end
            out.append(row)
        return out

    def to_text(self) -> str:
        return "\n".join("".join(row).rstrip() for row in self.chars)


def _lcg(seed: int) -> int:
    """Deterministic 31-bit pseudo-random step - no global random state."""
    return (seed * 1103515245 + 12345) & 0x7FFFFFFF


def noise(*parts: int) -> float:
    """Stable 0..1 noise for a tuple of ints."""
    seed = 0
    for part in parts:
        seed = _lcg(seed ^ (part * 2654435761 & 0x7FFFFFFF))
    return seed / 0x7FFFFFFF


# --------------------------------------------------------------------------
# ocean scene
# --------------------------------------------------------------------------

@dataclass
class SeaState:
    """What the animation should look like, derived from the real report."""

    wave_ft: float = 2.0
    period_s: float = 8.0
    wind_kn: float = 6.0
    onshore: bool = False
    score: int = 3
    pirate: bool = True
    daytime: bool = True
    sprites: tuple[str, ...] = field(default_factory=lambda: ("ship", "surfer"))

    @property
    def amplitude(self) -> float:
        # 0 ft -> flat line, 10 ft -> 3 rows of swing.
        return min(3.0, max(0.35, self.wave_ft / 3.2))

    @property
    def wavelength(self) -> float:
        # Long-period groundswell draws longer, lazier waves.
        return max(6.0, min(28.0, self.period_s * 2.2))

    @property
    def speed(self) -> float:
        return 0.55 + min(1.4, self.wave_ft / 6.0)


def surface(width: int, phase: float, sea: SeaState) -> list[float]:
    """Height (rows above the waterline) of the sea surface per column."""
    k = 2 * math.pi / sea.wavelength
    chop = min(1.0, sea.wind_kn / 18.0) * (1.0 if sea.onshore else 0.45)
    out = []
    for x in range(width):
        value = math.sin(x * k + phase)
        value += 0.35 * math.sin(x * k * 2.3 - phase * 1.7)
        value += chop * 0.5 * math.sin(x * 0.9 + phase * 2.9)
        out.append(value * sea.amplitude)
    return out


def ocean_scene(width: int, height: int, frame: int, sea: SeaState) -> Canvas:
    """The animated water, with a ship and a surfer riding it."""
    canvas = Canvas(width, height, key="sky")
    if width <= 0 or height <= 0:
        return canvas

    phase = -frame * 0.18 * sea.speed
    heights = surface(width, phase, sea)
    # Keep a body of water on screen whatever the swell, with the crests
    # oscillating around a waterline a few rows up from the bottom.
    body_rows = max(3, min(height - 2, int(sea.amplitude) + 3))
    waterline = max(1, height - body_rows)

    # Sky: sun or moon, gulls, and spindrift when it's windy.
    canvas.put(width - 4, 0, "\u2600" if sea.daytime else "\u263e", "sun")
    if sea.daytime and width > 30:
        for gull in range(2):
            gx = (width - 6 - (frame // (4 + gull * 3) + gull * 17) % (width + 8))
            gy = 1 + gull
            if 0 <= gy < waterline - 1:
                canvas.put(gx, gy, art.SEAGULL[(frame // 4 + gull) % 2], "gull")
    if sea.wind_kn >= 10:
        for x in range(width):
            if noise(x, frame // 2) > 0.985:
                canvas.put(x, max(0, waterline - 2), art.FOAM_CHARS[frame % 4], "foam")

    for x in range(width):
        crest = waterline - int(round(heights[x]))
        crest = max(0, min(height - 1, crest))
        glyph_shift = int((x - frame * sea.speed) // 2) % len(art.WAVE_CHARS)
        canvas.put(x, crest, art.WAVE_CHARS[glyph_shift], "crest")
        for y in range(crest + 1, height):
            depth = min(3, y - crest - 1)
            canvas.put(x, y, art.CREST_CHARS[depth], "sea")
        # Whitecaps on the steep faces when it's big or blown out.
        if sea.wave_ft >= 3 or sea.wind_kn >= 14:
            if heights[x] > sea.amplitude * 0.75 and noise(x, frame) > 0.6:
                canvas.put(x, crest, "≈", "foam")

    def crest_at(column: int) -> int:
        column = max(0, min(width - 1, column))
        return max(0, min(height - 1, waterline - int(round(heights[column]))))

    if "ship" in sea.sprites:
        ship = art.sprite("ship")
        ship_w, ship_h = art.sprite_size("ship")
        if width > ship_w + 4 and height > ship_h + 1:
            travel = width + ship_w
            ship_x = width - ((frame // 2) % travel)
            bob = crest_at(ship_x + ship_w // 2)
            ship_top = bob - ship_h + 1
            canvas.blit(ship_x, ship_top, ship, "ship")
            if sea.pirate:
                # Jolly Roger snapping at the top of the mainmast.
                flag = "\u2620\u2500" if frame % 8 < 4 else "\u2620\u2550"
                canvas.put(ship_x + 5, ship_top - 1, flag, "flag")

    if "surfer" in sea.sprites and sea.score >= 2:
        surfer = art.sprite("surfer")
        surf_w, surf_h = art.sprite_size("surfer")
        if width > surf_w + 6 and height > surf_h:
            travel = width + surf_w
            surfer_x = (frame // 3) % travel - surf_w
            top = crest_at(surfer_x + surf_w // 2) - surf_h
            canvas.blit(surfer_x, top, surfer, "surfer")

    if "dolphin" in sea.sprites and height >= 8:
        cycle = 220
        tick = frame % cycle
        if tick < 40:
            dolphin = art.sprite("dolphin")
            dol_w, dol_h = art.sprite_size("dolphin")
            x = width - 8 - tick
            arc = int(3 * math.sin(math.pi * tick / 40))
            canvas.blit(x, crest_at(x) - dol_h - arc + 1, dolphin, "dolphin")
    return canvas


# --------------------------------------------------------------------------
# banner rain ("hacker" backdrop)
# --------------------------------------------------------------------------

def rain_canvas(width: int, height: int, frame: int, density: float = 0.22) -> Canvas:
    """Falling glyph columns behind the banner."""
    canvas = Canvas(width, height, key="rain_dim")
    for x in range(width):
        if noise(x, 7) > density:
            continue
        speed = 1 + int(noise(x, 11) * 3)
        head = (frame // max(1, 4 - min(3, speed)) + int(noise(x, 3) * height)) % (
            height + 4
        )
        for trail in range(4):
            y = head - trail
            if not (0 <= y < height):
                continue
            glyph = RAIN_GLYPHS[int(noise(x, y, frame // 3) * len(RAIN_GLYPHS))]
            canvas.put(x, y, glyph, "rain_head" if trail == 0 else "rain_dim")
    return canvas


# --------------------------------------------------------------------------
# text widgets
# --------------------------------------------------------------------------

def sparkline(values: list[float], width: int) -> str:
    """Values -> unicode bar sparkline, sampled to `width` columns."""
    if not values or width <= 0:
        return ""
    if len(values) > width:
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]
    low, high = min(values), max(values)
    span = high - low
    out = []
    for value in values:
        level = 0 if span < 1e-9 else (value - low) / span
        out.append(SPARK_CHARS[min(len(SPARK_CHARS) - 1, int(level * (len(SPARK_CHARS) - 1) + 0.5))])
    return "".join(out)


def meter(percent: float, width: int, fill: str = "|") -> list[tuple[str, str]]:
    """htop-style bar as coloured segments: [|||||     45.0%]."""
    width = max(4, width)
    inner = width - 2
    percent = max(0.0, min(100.0, float(percent)))
    filled = int(round(inner * percent / 100.0))
    label = f"{percent:4.1f}%"
    green = int(inner * 0.5)
    amber = int(inner * 0.8)
    segments: list[tuple[str, str]] = [("[", "frame")]
    body = ""
    for i in range(filled):
        key = "bar_ok" if i < green else ("bar_warn" if i < amber else "bar_crit")
        if body and segments and segments[-1][1] == key:
            segments[-1] = (segments[-1][0] + fill, key)
        else:
            segments.append((fill, key))
        body += fill
    if filled < inner:
        segments.append((" " * (inner - filled), "frame"))
    # Overlay the numeric label on the bar's right edge, like htop.
    flat = "".join(text for text, _ in segments[1:])
    flat = flat[: inner - len(label)] + label
    rebuilt: list[tuple[str, str]] = [("[", "frame")]
    pos = 0
    for text, key in segments[1:]:
        chunk = flat[pos : pos + len(text)]
        pos += len(text)
        if chunk:
            rebuilt.append((chunk, key if pos <= filled else "label"))
    rebuilt.append(("]", "frame"))
    return rebuilt


TICKER_LINES = (
    "ahoy! decrypting the swell charts with a cutlass...",
    "wind be a fickle wench - trust the period, not the hype",
    "no kook left behind // paddle harder, matey",
    "sudo make me a barrel",
    "the tide waits for no root user",
    "dead men tell no lies about wave height",
    "offshore breeze == plunder conditions",
    "yo ho ho and a bottom turn",
    "uptime high, surf low - such is the sysadmin's curse",
    "keep yer boards waxed and yer backups current",
    "X marks the sandbar",
    "if ye can't read the buoy, ye can't ride the swell",
)


def ticker(width: int, frame: int, lines: tuple[str, ...] = TICKER_LINES,
           gap: str = "   ☠   ") -> str:
    """One scrolling marquee line of the given width."""
    if width <= 0:
        return ""
    strip = gap.join(lines) + gap
    offset = (frame // 2) % len(strip)
    doubled = strip + strip
    while len(doubled) < offset + width:
        doubled += strip
    return doubled[offset : offset + width]
