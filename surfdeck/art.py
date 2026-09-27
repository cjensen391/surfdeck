"""ASCII art assets and a tiny block font.

Sprites are stored as plain multi-line strings; a space is transparent when
blitted, so sprites layer over the ocean without punching holes in it.
"""

from __future__ import annotations

BANNER_FONT: dict[str, tuple[str, ...]] = {
    "S": ("####", "#   ", "####", "   #", "####"),
    "U": ("#  #", "#  #", "#  #", "#  #", "####"),
    "R": ("####", "#  #", "####", "# # ", "#  #"),
    "F": ("####", "#   ", "### ", "#   ", "#   "),
    "D": ("### ", "#  #", "#  #", "#  #", "### "),
    "E": ("####", "#   ", "### ", "#   ", "####"),
    "C": ("####", "#   ", "#   ", "#   ", "####"),
    "K": ("#  #", "# # ", "##  ", "# # ", "#  #"),
    " ": ("    ", "    ", "    ", "    ", "    "),
}

BANNER_HEIGHT = 5


def big_text(text: str, glyph: str = "█") -> list[str]:
    """Render text in the 5-row block font. Unknown letters become spaces."""
    rows = ["" for _ in range(BANNER_HEIGHT)]
    for char in text.upper():
        shape = BANNER_FONT.get(char, BANNER_FONT[" "])
        for i in range(BANNER_HEIGHT):
            rows[i] += shape[i].replace("#", glyph) + " "
    return [row.rstrip() for row in rows]


def big_text_width(text: str) -> int:
    return max((len(row) for row in big_text(text)), default=0)


# Jolly Roger galleon. Row 0 is the masthead; the hull sits on the waterline.
SHIP = r"""
     |    |    |
    )_)  )_)  )_)
   )___))___))___)\
  )____)____)_____)\\
_____|____|____|____\\\__
\                      /
"""

FLAG = r"""
 ___
|x x|
| ~ |
 ---
"""

SURFER = r"""
   \o/
    |
  __|__
"""

DOLPHIN = r"""
    _
  _/ \__
 (      \__
  \_______/
"""

PALM = r"""
  \|/ /
 --*--
   |
   |
  /|\
"""

SKULL = r'''
 .-"-.
/ x x \
| ___ |
\ |||| /
 '----'
'''

SEAGULL = ("~v~", "-v-")

# Flat art used in headers / footers.
CREST_CHARS = "░▒▓█"
WAVE_CHARS = "~≈≈~"
FOAM_CHARS = ".:°*"


def sprite(name: str) -> list[str]:
    """Named sprite as trimmed lines, blank leading/trailing rows removed."""
    raw = {
        "ship": SHIP,
        "flag": FLAG,
        "surfer": SURFER,
        "dolphin": DOLPHIN,
        "palm": PALM,
        "skull": SKULL,
    }[name]
    lines = raw.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def sprite_size(name: str) -> tuple[int, int]:
    lines = sprite(name)
    return (max((len(line) for line in lines), default=0), len(lines))
