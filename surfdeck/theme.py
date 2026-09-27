"""Colour themes and curses colour-pair allocation.

Each colour is declared as (256-colour code, 8-colour fallback) so the themes
look right in a modern terminal and remain readable in a dumb one. Monochrome
terminals fall back to bold/dim attributes only.
"""

from __future__ import annotations

from dataclasses import dataclass

# name -> (xterm-256 code, 8-colour fallback)
COLORS: dict[str, tuple[int, int]] = {
    "black": (0, 0),
    "red": (196, 1),
    "blood": (124, 1),
    "green": (46, 2),
    "leaf": (34, 2),
    "yellow": (226, 3),
    "gold": (220, 3),
    "amber": (214, 3),
    "orange": (208, 3),
    "blue": (33, 4),
    "navy": (18, 4),
    "deep": (24, 4),
    "sea": (31, 6),
    "magenta": (201, 5),
    "flamingo": (205, 5),
    "purple": (99, 5),
    "violet": (57, 5),
    "cyan": (51, 6),
    "teal": (44, 6),
    "white": (255, 7),
    "bone": (230, 7),
    "sand": (180, 3),
    "gray": (245, 7),
    "slate": (240, 7),
}

BOLD = "bold"
DIM = "dim"
REVERSE = "reverse"


@dataclass(frozen=True)
class Theme:
    name: str
    styles: dict[str, tuple[str, str | None, tuple[str, ...]]]

    def style(self, key: str) -> tuple[str, str | None, tuple[str, ...]]:
        return self.styles.get(key, self.styles["text"])


def _base(extra: dict) -> dict:
    """Common keys every theme needs, overridable per theme."""
    base: dict[str, tuple[str, str | None, tuple[str, ...]]] = {
        "text": ("white", None, ()),
        "dim": ("slate", None, (DIM,)),
        "label": ("gray", None, ()),
        "value": ("white", None, (BOLD,)),
        "frame": ("slate", None, ()),
        "good": ("green", None, (BOLD,)),
        "warn": ("amber", None, (BOLD,)),
        "bad": ("red", None, (BOLD,)),
        "bar_ok": ("green", None, ()),
        "bar_warn": ("amber", None, ()),
        "bar_crit": ("red", None, (BOLD,)),
        "sky": ("black", None, ()),
        "gull": ("bone", None, ()),
        "dolphin": ("cyan", None, ()),
        "sun": ("gold", None, (BOLD,)),
        "foam": ("white", None, (BOLD,)),
    }
    base.update(extra)
    return base


THEMES: dict[str, Theme] = {
    "pirate": Theme(
        "pirate",
        _base(
            {
                "title": ("gold", None, (BOLD,)),
                "accent": ("amber", None, (BOLD,)),
                "header": ("bone", None, (BOLD,)),
                "status": ("gold", None, ()),
                "score": ("gold", None, (BOLD,)),
                "sea": ("deep", None, ()),
                "crest": ("sea", None, ()),
                "ship": ("sand", None, (BOLD,)),
                "flag": ("red", None, (BOLD,)),
                "surfer": ("bone", None, (BOLD,)),
                "rain_head": ("gold", None, (BOLD,)),
                "rain_dim": ("blood", None, (DIM,)),
                "label": ("sand", None, ()),
            }
        ),
    ),
    "hacker": Theme(
        "hacker",
        _base(
            {
                "title": ("green", None, (BOLD,)),
                "accent": ("teal", None, (BOLD,)),
                "header": ("green", None, (BOLD,)),
                "status": ("leaf", None, ()),
                "score": ("green", None, (BOLD,)),
                "sea": ("leaf", None, (DIM,)),
                "crest": ("green", None, ()),
                "ship": ("teal", None, ()),
                "flag": ("green", None, (BOLD,)),
                "surfer": ("white", None, (BOLD,)),
                "rain_head": ("white", None, (BOLD,)),
                "rain_dim": ("leaf", None, (DIM,)),
                "label": ("leaf", None, ()),
                "value": ("green", None, (BOLD,)),
                "sun": ("green", None, ()),
                "gull": ("leaf", None, (DIM,)),
            }
        ),
    ),
    "tropical": Theme(
        "tropical",
        _base(
            {
                "title": ("magenta", None, (BOLD,)),
                "accent": ("cyan", None, (BOLD,)),
                "header": ("cyan", None, (BOLD,)),
                "status": ("magenta", None, ()),
                "score": ("yellow", None, (BOLD,)),
                "sea": ("blue", None, ()),
                "crest": ("cyan", None, (BOLD,)),
                "ship": ("bone", None, ()),
                "flag": ("magenta", None, (BOLD,)),
                "surfer": ("yellow", None, (BOLD,)),
                "rain_head": ("cyan", None, (BOLD,)),
                "rain_dim": ("purple", None, (DIM,)),
                "label": ("teal", None, ()),
            }
        ),
    ),
    # Neon Miami at 2am: pink-and-cyan sunset with the hacker's green readout
    # bleeding through the numbers and the glyph rain.
    "miami-vice": Theme(
        "miami-vice",
        _base(
            {
                "title": ("magenta", None, (BOLD,)),
                "accent": ("cyan", None, (BOLD,)),
                "header": ("flamingo", None, (BOLD,)),
                "status": ("teal", None, ()),
                "score": ("green", None, (BOLD,)),
                "value": ("green", None, (BOLD,)),
                "sea": ("violet", None, ()),
                "crest": ("magenta", None, (BOLD,)),
                "foam": ("cyan", None, (BOLD,)),
                "ship": ("bone", None, ()),
                "flag": ("flamingo", None, (BOLD,)),
                "surfer": ("cyan", None, (BOLD,)),
                "rain_head": ("green", None, (BOLD,)),
                "rain_dim": ("purple", None, (DIM,)),
                "label": ("teal", None, ()),
                "sun": ("flamingo", None, (BOLD,)),
                "gull": ("purple", None, (DIM,)),
                "dolphin": ("cyan", None, ()),
            }
        ),
    ),
}

THEME_ORDER = ("pirate", "hacker", "tropical", "miami-vice")
DEFAULT_THEME = "pirate"


def get_theme(name: str) -> Theme:
    try:
        return THEMES[name]
    except KeyError:
        raise KeyError(
            f"unknown theme {name!r}; known themes: {', '.join(THEME_ORDER)}"
        ) from None


def next_theme(name: str) -> str:
    try:
        index = THEME_ORDER.index(name)
    except ValueError:
        return DEFAULT_THEME
    return THEME_ORDER[(index + 1) % len(THEME_ORDER)]


class Palette:
    """Resolves theme keys to curses attributes, allocating pairs on demand."""

    def __init__(self, curses_mod, theme: Theme, use_color: bool = True) -> None:
        self._curses = curses_mod
        self.theme = theme
        self._attrs: dict[str, int] = {}
        self._pairs: dict[tuple[int, int], int] = {}
        self._next_pair = 1
        self.use_color = use_color and curses_mod.has_colors()
        if self.use_color:
            curses_mod.start_color()
            try:
                curses_mod.use_default_colors()
            except self._curses.error:
                pass
        self._colors = getattr(curses_mod, "COLORS", 8) if self.use_color else 0

    def _code(self, name: str) -> int:
        code256, fallback = COLORS.get(name, COLORS["white"])
        return code256 if self._colors >= 256 else fallback

    def _pair(self, fg: int, bg: int) -> int:
        key = (fg, bg)
        if key not in self._pairs:
            if self._next_pair >= min(getattr(self._curses, "COLOR_PAIRS", 64), 256):
                return 0
            try:
                self._curses.init_pair(self._next_pair, fg, bg)
            except self._curses.error:
                return 0
            self._pairs[key] = self._next_pair
            self._next_pair += 1
        return self._pairs[key]

    def attr(self, key: str) -> int:
        if key in self._attrs:
            return self._attrs[key]
        fg_name, bg_name, flags = self.theme.style(key)
        attr = 0
        for flag in flags:
            attr |= {
                BOLD: self._curses.A_BOLD,
                DIM: self._curses.A_DIM,
                REVERSE: self._curses.A_REVERSE,
            }[flag]
        if self.use_color:
            fg = self._code(fg_name)
            bg = -1 if bg_name is None else self._code(bg_name)
            pair = self._pair(fg, bg)
            if pair:
                attr |= self._curses.color_pair(pair)
        self._attrs[key] = attr
        return attr

    def retheme(self, theme: Theme) -> None:
        self.theme = theme
        self._attrs.clear()
