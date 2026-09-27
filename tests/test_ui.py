"""Dashboard tests against a stub curses, so no terminal is needed."""

import pytest

from surfdeck import surf as surf_mod, ui
from surfdeck.spots import get_spot


class FakeScreen:
    def __init__(self, height, width):
        self.height, self.width = height, width
        self.writes = []
        self.attempts = []  # every call, including ones curses would reject
        self.keys = []
        self.erased = 0

    def getmaxyx(self):
        return (self.height, self.width)

    def erase(self):
        self.erased += 1

    def addstr(self, y, x, text, attr=0):
        # Recorded before validating: Dashboard.addstr swallows curses errors,
        # so the test has to see what it tried to paint, not just what stuck.
        self.attempts.append((y, x, text, attr))
        if not (0 <= y < self.height and 0 <= x < self.width):
            raise FakeCurses.error("out of bounds")
        if x + len(text) > self.width:
            raise FakeCurses.error("would wrap")
        if y == self.height - 1 and x + len(text) >= self.width:
            raise FakeCurses.error("bottom right cell")
        self.writes.append((y, x, text, attr))

    def rejected(self):
        """Attempted writes that a real curses window would refuse."""
        bad = []
        for y, x, text, attr in self.attempts:
            if not (0 <= y < self.height and 0 <= x < self.width):
                bad.append((y, x, text))
            elif x + len(text) > self.width:
                bad.append((y, x, text))
            elif y == self.height - 1 and x + len(text) >= self.width:
                bad.append((y, x, text))
        return bad

    def noutrefresh(self):
        pass

    def nodelay(self, flag):
        pass

    def timeout(self, ms):
        self.timeout_ms = ms

    def getch(self):
        return self.keys.pop(0) if self.keys else -1


class FakeCurses:
    A_BOLD, A_DIM, A_REVERSE = 1, 2, 4
    COLORS = 256
    COLOR_PAIRS = 64
    KEY_RESIZE = 546
    error = type("error", (Exception,), {})

    def __init__(self):
        self.pairs = {}
        self.cursor = None
        self.updates = 0

    def has_colors(self):
        return True

    def start_color(self):
        pass

    def use_default_colors(self):
        pass

    def init_pair(self, index, fg, bg):
        self.pairs[index] = (fg, bg)

    def color_pair(self, index):
        return index << 8

    def curs_set(self, value):
        self.cursor = value

    def doupdate(self):
        self.updates += 1


@pytest.fixture
def dashboard(monkeypatch, tmp_path, report):
    """A Dashboard wired to a stub screen and an offline, fixed report."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(ui, "curses", FakeCurses())
    monkeypatch.setattr(surf_mod, "fetch_report", lambda spot, timeout=8.0: report)

    def make(height=34, width=120):
        screen = FakeScreen(height, width)
        board = ui.Dashboard(screen, get_spot("south-beach"), "pirate", "imperial", fps=12)
        # The fetch runs in a thread; wait for it so draws are deterministic.
        for _ in range(200):
            if board.fetcher.report is not None and not board.fetcher.fetching:
                break
            import time

            time.sleep(0.01)
        return board, screen

    return make


@pytest.mark.parametrize(
    "height,width",
    [(34, 120), (24, 80), (40, 200), (20, 96), (16, 60), (12, 45), (9, 40), (8, 34), (6, 20)],
)
def test_draw_stays_inside_the_terminal(dashboard, height, width):
    board, screen = dashboard(height, width)
    board.draw()
    assert screen.erased >= 1
    assert screen.writes, "nothing was painted"
    assert not screen.rejected(), f"curses would reject: {screen.rejected()[:3]}"


def test_draw_shows_surf_and_system_data_side_by_side(dashboard):
    board, screen = dashboard(34, 120)
    board.draw()
    painted = " ".join(text for _y, _x, text, _a in screen.writes)
    assert "SOUTH BEACH, FL" in painted
    assert "SHIP'S SYSTEMS" in painted
    assert "WAVE" in painted and "SWELL" in painted and "WIND" in painted
    assert "PID" in painted
    assert "quit" in painted


def test_tiny_terminal_says_so_instead_of_crashing(dashboard):
    board, screen = dashboard(6, 20)
    board.draw()
    painted = " ".join(text for _y, _x, text, _a in screen.writes)
    assert "too wee" in painted


def test_animation_advances_only_when_running(dashboard):
    board, screen = dashboard(30, 110)
    screen.keys = [-1]
    start = board.frame
    board.stdscr.timeout(80)
    board.handle_key(ord(" "))
    assert board.paused
    board.handle_key(ord(" "))
    assert not board.paused
    board.frame += 1
    assert board.frame == start + 1


def test_keys_change_theme_units_spot_and_speed(dashboard):
    board, _screen = dashboard(30, 110)
    board.handle_key(ord("t"))
    assert board.palette.theme.name == "hacker"
    board.handle_key(ord("u"))
    assert board.units == "metric"
    first_spot = board.spot.key
    board.handle_key(ord("s"))
    assert board.spot.key != first_spot
    board.handle_key(ord("+"))
    assert board.fps == 14
    board.handle_key(ord("-"))
    assert board.fps == 12
    board.handle_key(ord("?"))
    assert board.show_help
    board.draw()  # the help overlay must also paint inside the screen
    assert not board.stdscr.rejected()
    board.handle_key(ord("?"))
    assert not board.show_help


def test_quit_keys_stop_the_loop(dashboard):
    board, _screen = dashboard(30, 110)
    assert board.handle_key(ord("r")) is True
    assert board.handle_key(ord("q")) is False
    assert board.handle_key(27) is False


def test_resize_is_handled(dashboard):
    board, screen = dashboard(30, 110)
    assert board.handle_key(FakeCurses.KEY_RESIZE) is True
    screen.height, screen.width = 18, 70
    screen.attempts.clear()
    board.draw()
    assert not screen.rejected()


def test_sea_state_follows_the_report(dashboard, report):
    board, _screen = dashboard(30, 110)
    sea = board.sea_state(report)
    assert sea.wave_ft == report.wave_height_ft
    assert sea.period_s == report.swell_period_s
    assert sea.onshore is False  # the fixture day is offshore
    assert "ship" in sea.sprites
    assert sea.pirate is True
    assert sea.daytime is True

    night = surf_mod.SurfReport(**{**report.__dict__, "observed_at": "2026-09-27T04:00"})
    assert board.sea_state(night).daytime is False

    broken = surf_mod.SurfReport(report.spot_key, report.spot_name, report.facing_deg)
    fallback = board.sea_state(broken)
    assert fallback.sprites == ("ship",)


def test_placard_appears_under_the_surf_panel(dashboard, report):
    board, _screen = dashboard(30, 110)
    from surfdeck.format import rows_to_text

    good = rows_to_text(board.surf_panel(report, 50))
    assert "wax up" in good
    flat = surf_mod.SurfReport(
        **{**report.__dict__, "wave_height_ft": 0.2, "swell_period_s": 4.0}
    )
    assert "plunderin" in rows_to_text(board.surf_panel(flat, 50))
    assert "hailing the buoys" in rows_to_text(board.surf_panel(None, 50))


def test_run_loop_exits_on_q(dashboard):
    board, screen = dashboard(28, 100)
    screen.keys = [-1, ord("t"), -1, ord("q")]
    board.run()
    assert screen.erased >= 3


def test_fetcher_ignores_a_reply_for_an_abandoned_spot(monkeypatch, tmp_path, report):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(surf_mod, "fetch_report", lambda spot, timeout=8.0: report)
    fetcher = ui.SurfFetcher(get_spot("haulover"))
    fetcher._spot = get_spot("sebastian-inlet")
    fetcher._run(get_spot("haulover"))
    assert fetcher.report is None or fetcher.report.spot_key != "south-beach"
    assert not fetcher.fetching


def test_stacked_layout_drops_the_placard_for_process_rows(dashboard, report):
    from surfdeck.format import rows_to_text

    board, screen = dashboard(24, 80)
    assert "plunderin" not in rows_to_text(board.surf_panel(report, 79, placard=False))
    board.draw()
    painted = " ".join(text for _y, _x, text, _a in screen.writes)
    assert "WAVE" in painted and "WIND" in painted  # surf numbers kept
    assert "PID" in painted                          # and htop still gets rows
    assert "TREND" in painted


def test_wide_layout_uses_both_columns(dashboard):
    board, screen = dashboard(34, 120)
    board.draw()
    columns = {x for _y, x, _t, _a in screen.writes}
    assert any(x > 60 for x in columns), "right column never painted"
    assert any(x < 10 for x in columns), "left column never painted"
