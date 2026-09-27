"""The curses dashboard.

Layout (wide terminal):

    +-------------------------------------------------+
    |  block-font banner over falling-glyph rain      |
    |  scrolling pirate ticker                        |
    |  SURF REPORT            |  SHIP'S SYSTEMS       |
    |  (score, wave, swell,   |  (htop-style meters,  |
    |   wind, temps, trend)   |   tasks, net, procs)  |
    |  animated ocean: galleon + surfer riding swell  |
    |  status / key hints                             |
    +-------------------------------------------------+

Narrow terminals stack the two panels; short ones drop the banner, then the
ocean, keeping the numbers visible.
"""

from __future__ import annotations

import curses
import threading
import time

from . import animation, art, format as fmt, surf as surf_mod, theme as theme_mod
from .spots import SPOTS, Spot
from .stats import Sampler
from .surf import SurfReport

STATS_INTERVAL = 1.5
SURF_INTERVAL = 600.0
BANNER_MIN_HEIGHT = 27
# Rows the panels need before the ocean gets any: the surf numbers plus a
# usable slice of the process list.
MIN_BODY_STACKED = 15
MIN_BODY_SPLIT = 12
MIN_SCENE = 4
MAX_SCENE = 12
# Rows the full (non-compact) system panel wants before the ocean grows.
BODY_WANT_EXTRA = 6
RULE_MIN_HEIGHT = 26
HELP_LINES = (
    "  q / ESC  abandon ship (quit)",
    "  r        re-read the buoys now",
    "  t        cycle theme: pirate / hacker / tropical / miami-vice",
    "  s        next spot",
    "  u        toggle imperial / metric",
    "  space    freeze the animation",
    "  + / -    animation speed",
    "  ?        close this parley",
)
# The overlay sizes itself to its longest line so a theme name never clips.
HELP_WIDTH = max(len(line) for line in HELP_LINES) + 4


class SurfFetcher:
    """Keeps the newest report for the current spot, fetched off the UI thread."""

    def __init__(self, spot: Spot, timeout: float = 8.0) -> None:
        self._lock = threading.Lock()
        self._spot = spot
        self._timeout = timeout
        self._report: SurfReport | None = surf_mod.load_cache(spot.key)
        self._fetching = False
        self._last_fetch = 0.0
        self.request()

    @property
    def report(self) -> SurfReport | None:
        with self._lock:
            return self._report

    @property
    def fetching(self) -> bool:
        with self._lock:
            return self._fetching

    def set_spot(self, spot: Spot) -> None:
        with self._lock:
            self._spot = spot
            self._report = surf_mod.load_cache(spot.key)
        self.request(force=True)

    def request(self, force: bool = False) -> None:
        now = time.monotonic()
        with self._lock:
            if self._fetching:
                return
            if not force and now - self._last_fetch < SURF_INTERVAL:
                return
            self._fetching = True
            self._last_fetch = now
            spot = self._spot
        thread = threading.Thread(target=self._run, args=(spot,), daemon=True)
        thread.start()

    def _run(self, spot: Spot) -> None:
        report = surf_mod.get_report(spot, timeout=self._timeout)
        with self._lock:
            # Ignore a late reply for a spot we have since navigated away from.
            if spot.key == self._spot.key:
                self._report = report
            self._fetching = False

    def tick(self) -> None:
        self.request()


class Dashboard:
    def __init__(self, stdscr, spot: Spot, theme_name: str, units: str,
                 fps: int = 12, use_color: bool = True) -> None:
        self.stdscr = stdscr
        self.spot = spot
        self.spot_keys = list(SPOTS)
        self.units = units
        self.fps = max(1, min(30, fps))
        self.paused = False
        self.show_help = False
        self.frame = 0
        self.message = ""
        self.message_until = 0.0

        self.palette = theme_mod.Palette(
            curses, theme_mod.get_theme(theme_name), use_color=use_color
        )
        self.sampler = Sampler(top_n=10)
        self.stats = self.sampler.sample()
        self._last_stats = time.monotonic()
        self.fetcher = SurfFetcher(spot)

        curses.curs_set(0)
        stdscr.nodelay(True)

    # ---------------------------------------------------------------- drawing

    def addstr(self, y: int, x: int, text: str, key: str = "text") -> None:
        """Clipped, exception-proof write. Curses hates the last cell."""
        height, width = self.stdscr.getmaxyx()
        if not (0 <= y < height) or x >= width or not text:
            return
        if x < 0:
            text = text[-x:]
            x = 0
        room = width - x
        if y == height - 1:
            room -= 1
        if room <= 0:
            return
        try:
            self.stdscr.addstr(y, x, text[:room], self.palette.attr(key))
        except curses.error:
            pass

    def draw_rows(self, rows: list[fmt.Row], top: int, left: int, width: int,
                  max_rows: int) -> None:
        for index, row in enumerate(rows[:max_rows]):
            x = left
            for text, key in row:
                if x - left >= width:
                    break
                self.addstr(top + index, x, text[: max(0, width - (x - left))], key)
                x += len(text)

    def draw_canvas(self, canvas: animation.Canvas, top: int, left: int) -> None:
        for y, row in enumerate(canvas.runs()):
            for x, text, key in row:
                self.addstr(top + y, left + x, text, key)

    def draw_banner(self, top: int, width: int) -> int:
        rain = animation.rain_canvas(width, art.BANNER_HEIGHT, self.frame)
        self.draw_canvas(rain, top, 0)
        title = art.big_text("SURFDECK")
        title_width = max(len(line) for line in title)
        if title_width + 4 <= width:
            left = (width - title_width) // 2
            for index, line in enumerate(title):
                self.addstr(top + index, left, line, "title")
            tag = "surf report + system watch"
            if len(tag) + 4 < width:
                self.addstr(top + art.BANNER_HEIGHT - 1,
                            max(0, (width - len(tag)) // 2 + title_width // 2 - 8),
                            "", "dim")
        else:
            self.addstr(top + 2, max(0, (width - 8) // 2), "SURFDECK", "title")
        return art.BANNER_HEIGHT

    def sea_state(self, report: SurfReport | None) -> animation.SeaState:
        if report is None or not report.ok:
            return animation.SeaState(
                wave_ft=1.0, period_s=7.0, wind_kn=4.0, score=1,
                pirate=self.palette.theme.name == "pirate",
                sprites=("ship",),
            )
        score = surf_mod.surf_score(report)
        relation = surf_mod.wind_relation(report.wind_direction_deg, report.facing_deg)
        daytime = True
        if report.sunrise and report.sunset and report.observed_at:
            now = report.observed_at[11:16]
            daytime = report.sunrise <= now <= report.sunset
        sprites = ["ship", "surfer"]
        if score >= 4:
            sprites.append("dolphin")
        return animation.SeaState(
            wave_ft=report.wave_height_ft or 1.0,
            period_s=report.swell_period_s or report.wave_period_s or 8.0,
            wind_kn=report.wind_speed_kn or 0.0,
            onshore=relation == "ONSHORE",
            score=score,
            pirate=self.palette.theme.name == "pirate",
            daytime=daytime,
            sprites=tuple(sprites),
        )

    def surf_panel(self, report: SurfReport | None, width: int,
                   placard: bool = True) -> list[fmt.Row]:
        """Surf rows, plus a placard filling the dead space underneath.

        The placard is only worth drawing in the side-by-side layout, where the
        left column has rows to spare; stacked, those rows belong to htop.
        """
        if report is None:
            return [[("  hailing the buoys...", "dim")]]
        rows = fmt.surf_rows(report, width, self.units)
        score = surf_mod.surf_score(report) if report.ok else 0
        if placard and width >= 26:
            placard = art.sprite("skull" if score < 3 else "palm")
            caption = "no swell worth plunderin'" if score < 3 else "wax up, ye sea dog"
            rows.append([("", "text")])
            for line in placard:
                rows.append([("     " + line, "bad" if score < 3 else "good")])
            rows.append([("   " + caption, "dim")])
        return rows


    def draw_help(self) -> None:
        height, width = self.stdscr.getmaxyx()
        box_w = min(max(52, HELP_WIDTH), width - 4)
        box_h = min(len(HELP_LINES) + 4, height - 2)
        top = max(0, (height - box_h) // 2)
        left = max(0, (width - box_w) // 2)
        self.addstr(top, left, "┌" + "─" * (box_w - 2) + "┐", "frame")
        self.addstr(top, left + 2, " PARLEY: THE ARTICLES ", "title")
        for index in range(1, box_h - 1):
            self.addstr(top + index, left, "│", "frame")
            self.addstr(top + index, left + box_w - 1, "│", "frame")
            self.addstr(top + index, left + 1, " " * (box_w - 2), "sky")
        for index, line in enumerate(HELP_LINES[: box_h - 3]):
            self.addstr(top + 2 + index, left + 1, line[: box_w - 2], "text")
        self.addstr(top + box_h - 1, left,
                    "└" + "─" * (box_w - 2) + "┘", "frame")

    def draw(self) -> None:
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        if height < 8 or width < 34:
            self.addstr(0, 0, "terminal too wee - give me 34x8", "bad")
            self.stdscr.noutrefresh()
            curses.doupdate()
            return

        report = self.fetcher.report
        row = 0
        if height >= BANNER_MIN_HEIGHT:
            row += self.draw_banner(row, width)
        self.addstr(row, 0, animation.ticker(width - 1, self.frame), "status")
        row += 1
        if height >= RULE_MIN_HEIGHT:
            self.addstr(row, 0, "─" * (width - 1), "frame")
            row += 1

        # Budget rows: the panels get what they need, the ocean gets a strip,
        # and only real surplus makes the ocean taller.
        available = height - row - 1
        min_body = MIN_BODY_SPLIT if width >= 96 else MIN_BODY_STACKED
        scene_height = MIN_SCENE if available >= min_body + MIN_SCENE else 0
        body_height = available - scene_height
        surplus = max(0, body_height - (min_body + BODY_WANT_EXTRA))
        grow = min(MAX_SCENE - MIN_SCENE, surplus) if scene_height else 0
        scene_height += grow
        body_height = max(3, body_height - grow)

        # Panels are built at their own column width, not the screen width,
        # or the htop meters overflow the divider.
        if width >= 96:
            split = max(42, width // 2 - 2)
            left_width = split - 2
            right_width = width - split - 3
            surf_panel = self.surf_panel(report, left_width)
            stats_panel = fmt.stats_rows(
                self.stats, right_width,
                top_n=max(2, body_height - 14),
                compact=body_height < 12,
            )
            self.draw_rows(surf_panel, row, 1, left_width, body_height)
            for y in range(row, row + body_height):
                self.addstr(y, split, "│", "frame")
            self.draw_rows(stats_panel, row, split + 2, right_width, body_height)
        else:
            panel_width = width - 1
            surf_panel = self.surf_panel(report, panel_width, placard=False)
            # The surf numbers run to ~10 rows; never cut into them to make
            # room for process rows.
            surf_height = min(len(surf_panel), max(10, body_height - 6))
            stats_budget = body_height - surf_height - 1
            stats_panel = fmt.stats_rows(
                self.stats, panel_width,
                top_n=max(1, stats_budget - 5),
                compact=stats_budget < 12,
            )
            self.draw_rows(surf_panel, row, 0, panel_width, surf_height)
            self.addstr(row + surf_height, 0, "─" * panel_width, "frame")
            self.draw_rows(
                stats_panel, row + surf_height + 1, 0, panel_width,
                body_height - surf_height - 1,
            )
        row += body_height

        if scene_height > 0:
            scene = animation.ocean_scene(
                width - 1, scene_height, self.frame, self.sea_state(report)
            )
            self.draw_canvas(scene, row, 0)
            row += scene_height

        self.draw_status(height - 1, width, report)
        if self.show_help:
            self.draw_help()
        self.stdscr.noutrefresh()
        curses.doupdate()

    def draw_status(self, y: int, width: int, report: SurfReport | None) -> None:
        if self.message and time.monotonic() < self.message_until:
            self.addstr(y, 0, self.message[: width - 1], "accent")
            return
        bits = [
            ("q", "quit"),
            ("r", "refresh"),
            ("t", self.palette.theme.name),
            ("s", self.spot.key),
            ("u", self.units),
            ("?", "keys"),
        ]
        x = 0
        for key, label in bits:
            self.addstr(y, x, f" {key}", "accent")
            self.addstr(y, x + 2, f":{label} ", "dim")
            x += 4 + len(label)
        flag = "fetching..." if self.fetcher.fetching else (
            "paused" if self.paused else f"{self.fps}fps"
        )
        if report and report.stale:
            flag = "stale chart - no signal"
        self.addstr(y, max(x + 1, width - len(flag) - 2), flag, "status")

    # ------------------------------------------------------------------ input

    def notify(self, text: str, seconds: float = 2.5) -> None:
        self.message = text
        self.message_until = time.monotonic() + seconds

    def handle_key(self, key: int) -> bool:
        """Returns False when it's time to quit."""
        if key in (ord("q"), ord("Q"), 27):
            return False
        if key in (ord("r"), ord("R")):
            self.fetcher.request(force=True)
            self.notify("re-reading the buoys...")
        elif key in (ord("t"), ord("T")):
            name = theme_mod.next_theme(self.palette.theme.name)
            self.palette.retheme(theme_mod.get_theme(name))
            self.notify(f"colours struck: {name}")
        elif key in (ord("s"), ord("S")):
            index = (self.spot_keys.index(self.spot.key) + 1) % len(self.spot_keys)
            self.spot = SPOTS[self.spot_keys[index]]
            self.fetcher.set_spot(self.spot)
            self.notify(f"setting course for {self.spot.name}")
        elif key in (ord("u"), ord("U")):
            self.units = "metric" if self.units == "imperial" else "imperial"
            self.notify(f"units: {self.units}")
        elif key == ord(" "):
            self.paused = not self.paused
        elif key in (ord("+"), ord("=")):
            self.fps = min(30, self.fps + 2)
        elif key in (ord("-"), ord("_")):
            self.fps = max(1, self.fps - 2)
        elif key in (ord("?"), ord("h"), ord("H")):
            self.show_help = not self.show_help
        elif key == curses.KEY_RESIZE:
            self.stdscr.erase()
        return True

    # ------------------------------------------------------------------- loop

    def run(self) -> None:
        while True:
            self.draw()
            self.stdscr.timeout(int(1000 / self.fps))
            key = self.stdscr.getch()
            if key != -1 and not self.handle_key(key):
                return
            now = time.monotonic()
            if now - self._last_stats >= STATS_INTERVAL:
                self.stats = self.sampler.sample()
                self._last_stats = now
            self.fetcher.tick()
            if not self.paused:
                self.frame += 1


def run(spot: Spot, theme_name: str, units: str, fps: int, use_color: bool) -> None:
    def _main(stdscr):
        Dashboard(stdscr, spot, theme_name, units, fps, use_color).run()

    curses.wrapper(_main)
