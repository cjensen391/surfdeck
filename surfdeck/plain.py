"""One-shot, non-interactive output for `surfdeck --once`.

Useful for scripts, MOTDs and terminals without curses. Colour is emitted as
ANSI escapes using the same theme keys as the curses UI, or omitted entirely
with `color=False`.
"""

from __future__ import annotations

from . import animation, art, format as fmt, theme as theme_mod
from .stats import SystemStats
from .surf import SurfReport

RESET = "\033[0m"


def _ansi(key: str, theme: theme_mod.Theme, color: bool) -> str:
    if not color:
        return ""
    name, _bg, flags = theme.style(key)
    code = theme_mod.COLORS.get(name, theme_mod.COLORS["white"])[0]
    out = f"\033[38;5;{code}m"
    if theme_mod.BOLD in flags:
        out += "\033[1m"
    if theme_mod.DIM in flags:
        out += "\033[2m"
    return out


def render_rows(rows: list[fmt.Row], theme: theme_mod.Theme, color: bool) -> str:
    lines = []
    for row in rows:
        if color:
            line = "".join(f"{_ansi(key, theme, color)}{text}{RESET}" for text, key in row)
        else:
            line = "".join(text for text, _ in row)
        lines.append(line.rstrip())
    return "\n".join(lines)


def render_canvas(canvas: animation.Canvas, theme: theme_mod.Theme,
                  color: bool) -> str:
    if not color:
        return canvas.to_text()
    lines = []
    for row in canvas.runs():
        line = ""
        cursor = 0
        for x, text, key in row:
            line += " " * max(0, x - cursor)
            line += f"{_ansi(key, theme, color)}{text}{RESET}"
            cursor = x + len(text)
        lines.append(line)
    return "\n".join(lines)


def render(report: SurfReport, stats: SystemStats, theme_name: str = "pirate",
           units: str = "imperial", width: int = 80, color: bool = True,
           scene: bool = True, frame: int = 7) -> str:
    theme = theme_mod.get_theme(theme_name)
    blocks: list[str] = []

    title = art.big_text("SURFDECK")
    pad = max(0, (width - max(len(line) for line in title)) // 2)
    blocks.append(
        "\n".join(
            f"{_ansi('title', theme, color)}{' ' * pad}{line}{RESET if color else ''}"
            for line in title
        )
    )
    blocks.append(
        f"{_ansi('status', theme, color)}"
        f"{animation.ticker(width - 1, 0)}{RESET if color else ''}"
    )
    blocks.append(f"{_ansi('frame', theme, color)}{'-' * (width - 1)}{RESET if color else ''}")
    blocks.append(render_rows(fmt.surf_rows(report, width, units), theme, color))
    blocks.append("")
    blocks.append(render_rows(fmt.stats_rows(stats, width, top_n=8), theme, color))
    if scene:
        sea = _sea_state(report, theme_name)
        # Pick the frame that parks the galleon in view rather than half off
        # the right edge, since a static render gets exactly one frame.
        ship_w = art.sprite_size("ship")[0]
        travel = width + ship_w
        target_x = max(2, width // 2 - ship_w)
        scene_frame = 2 * ((width - 1 - target_x) % travel) + (frame % 2)
        blocks.append("")
        blocks.append(
            render_canvas(
                animation.ocean_scene(width - 1, 10, scene_frame, sea), theme, color
            )
        )
    return "\n".join(blocks) + ("\n" if color else "\n")


def _sea_state(report: SurfReport, theme_name: str) -> animation.SeaState:
    from . import surf as surf_mod

    if not report.ok:
        return animation.SeaState(pirate=theme_name == "pirate", sprites=("ship",))
    score = surf_mod.surf_score(report)
    relation = surf_mod.wind_relation(report.wind_direction_deg, report.facing_deg)
    return animation.SeaState(
        wave_ft=report.wave_height_ft or 1.0,
        period_s=report.swell_period_s or report.wave_period_s or 8.0,
        wind_kn=report.wind_speed_kn or 0.0,
        onshore=relation == "ONSHORE",
        score=score,
        pirate=theme_name == "pirate",
        sprites=("ship", "surfer") if score >= 2 else ("ship",),
    )
