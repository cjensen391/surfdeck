import pytest

from surfdeck import theme as theme_mod


def test_every_theme_defines_every_key_the_panels_use():
    from surfdeck import format as fmt

    keys = {
        "text", "dim", "label", "value", "frame", "good", "warn", "bad",
        "bar_ok", "bar_warn", "bar_crit", "title", "accent", "header", "status",
        "score", "sea", "crest", "foam", "ship", "flag", "surfer", "sky",
        "sun", "gull", "dolphin", "rain_head", "rain_dim",
    }
    for name in theme_mod.THEME_ORDER:
        theme = theme_mod.get_theme(name)
        missing = keys - set(theme.styles)
        assert not missing, f"{name} is missing {sorted(missing)}"
        for key, (fg, bg, flags) in theme.styles.items():
            assert fg in theme_mod.COLORS, f"{name}.{key} uses unknown colour {fg}"
            assert bg is None or bg in theme_mod.COLORS
            assert set(flags) <= {theme_mod.BOLD, theme_mod.DIM, theme_mod.REVERSE}
    assert fmt.score_key(10) in keys


def test_unknown_key_falls_back_to_text():
    theme = theme_mod.get_theme("pirate")
    assert theme.style("not-a-key") == theme.style("text")


def test_get_theme_rejects_unknown_names():
    with pytest.raises(KeyError) as excinfo:
        theme_mod.get_theme("disco")
    assert "pirate" in excinfo.value.args[0]


def test_next_theme_cycles():
    seen = [theme_mod.DEFAULT_THEME]
    for _ in range(len(theme_mod.THEME_ORDER)):
        seen.append(theme_mod.next_theme(seen[-1]))
    assert seen[0] == seen[-1]
    assert set(seen) == set(theme_mod.THEME_ORDER)
    assert theme_mod.next_theme("nonsense") == theme_mod.DEFAULT_THEME


class FakeCurses:
    """Just enough curses to exercise Palette's pair allocation."""

    A_BOLD, A_DIM, A_REVERSE = 1, 2, 4
    COLORS = 256
    COLOR_PAIRS = 8
    error = type("error", (Exception,), {})

    def __init__(self, colors=True):
        self._colors = colors
        self.pairs = {}
        self.started = False

    def has_colors(self):
        return self._colors

    def start_color(self):
        self.started = True

    def use_default_colors(self):
        pass

    def init_pair(self, index, fg, bg):
        self.pairs[index] = (fg, bg)

    def color_pair(self, index):
        return index << 8


def test_palette_allocates_one_pair_per_colour_combination():
    fake = FakeCurses()
    palette = theme_mod.Palette(fake, theme_mod.get_theme("pirate"))
    first = palette.attr("title")
    assert palette.attr("title") is first  # cached
    palette.attr("sea")
    assert fake.started
    assert len(fake.pairs) == 2


def test_palette_survives_running_out_of_pairs():
    fake = FakeCurses()
    palette = theme_mod.Palette(fake, theme_mod.get_theme("tropical"))
    attrs = [palette.attr(key) for key in theme_mod.get_theme("tropical").styles]
    assert len(attrs) == len(theme_mod.get_theme("tropical").styles)
    assert len(fake.pairs) <= fake.COLOR_PAIRS


def test_palette_falls_back_to_eight_colours():
    fake = FakeCurses()
    fake.COLORS = 8
    palette = theme_mod.Palette(fake, theme_mod.get_theme("hacker"))
    palette.attr("title")
    assert all(0 <= fg < 8 for fg, _bg in fake.pairs.values())


def test_palette_without_colour_uses_attributes_only():
    fake = FakeCurses(colors=False)
    palette = theme_mod.Palette(fake, theme_mod.get_theme("pirate"), use_color=False)
    assert palette.attr("title") == FakeCurses.A_BOLD
    assert palette.attr("dim") == FakeCurses.A_DIM
    assert palette.attr("text") == 0
    assert not fake.pairs


def test_retheme_clears_the_cache():
    fake = FakeCurses()
    palette = theme_mod.Palette(fake, theme_mod.get_theme("pirate"))
    before = palette.attr("sea")
    palette.retheme(theme_mod.get_theme("hacker"))
    assert palette.theme.name == "hacker"
    assert palette.attr("sea") != before
