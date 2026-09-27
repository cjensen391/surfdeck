import pytest

from surfdeck import art
from surfdeck.animation import (
    Canvas,
    SeaState,
    meter,
    noise,
    ocean_scene,
    rain_canvas,
    sparkline,
    surface,
    ticker,
)


def test_canvas_put_and_read_back():
    canvas = Canvas(10, 3)
    canvas.put(2, 1, "ahoy", "flag")
    assert canvas.chars[1][2:6] == list("ahoy")
    assert canvas.keys[1][2] == "flag"
    assert canvas.to_text().split("\n")[1] == "  ahoy"


def test_canvas_clips_instead_of_raising():
    canvas = Canvas(6, 2)
    canvas.put(4, 0, "overflowing", "text")
    canvas.put(-3, 1, "negative", "text")
    canvas.put(0, 99, "offscreen", "text")
    assert "".join(canvas.chars[0]) == "    ov"
    assert "".join(canvas.chars[1]) == "ative "


def test_blit_treats_spaces_as_transparent():
    canvas = Canvas(6, 2)
    canvas.put(0, 0, "######", "sea")
    canvas.put(0, 1, "######", "sea")
    canvas.blit(1, 0, ["a b", " c "], "ship")
    assert "".join(canvas.chars[0]) == "#a#b##"
    assert "".join(canvas.chars[1]) == "##c###"
    assert canvas.keys[0][1] == "ship"
    assert canvas.keys[0][2] == "sea"


def test_blit_can_paint_spaces_when_asked():
    canvas = Canvas(4, 1)
    canvas.put(0, 0, "####", "sea")
    canvas.blit(1, 0, ["a b"], "ship", transparent=None)
    assert "".join(canvas.chars[0]) == "#a b"


def test_runs_group_by_key_and_skip_blanks():
    canvas = Canvas(12, 1)
    canvas.put(0, 0, "aa", "one")
    canvas.put(2, 0, "bb", "two")
    canvas.put(8, 0, "cc", "one")
    runs = canvas.runs()[0]
    assert runs[0] == (0, "aa", "one")
    assert runs[1] == (2, "bb", "two")
    assert runs[-1][2] == "one" and runs[-1][1].endswith("cc")


def test_noise_is_deterministic_and_bounded():
    assert noise(3, 4) == noise(3, 4)
    assert noise(3, 4) != noise(4, 3)
    assert all(0.0 <= noise(x, y) <= 1.0 for x in range(20) for y in range(5))


def test_surface_amplitude_tracks_wave_height():
    small = surface(60, 0.0, SeaState(wave_ft=1.0))
    big = surface(60, 0.0, SeaState(wave_ft=9.0))
    assert max(abs(v) for v in big) > max(abs(v) for v in small)
    assert SeaState(wave_ft=0.0).amplitude >= 0.35  # never a dead flat line
    assert SeaState(wave_ft=99.0).amplitude <= 3.0  # and never off the screen


def test_long_period_swell_draws_longer_waves():
    assert SeaState(period_s=14).wavelength > SeaState(period_s=5).wavelength


def test_ocean_scene_is_deterministic_and_fits_its_box():
    sea = SeaState(wave_ft=3.0, period_s=10.0, wind_kn=8.0, score=5)
    first = ocean_scene(70, 10, 12, sea)
    again = ocean_scene(70, 10, 12, sea)
    assert first.to_text() == again.to_text()
    assert len(first.chars) == 10
    assert all(len(row) == 70 for row in first.chars)


def test_ocean_scene_moves_between_frames():
    sea = SeaState(wave_ft=3.0, period_s=10.0, score=5)
    assert ocean_scene(70, 10, 0, sea).to_text() != ocean_scene(70, 10, 6, sea).to_text()


def test_ocean_scene_keeps_water_on_screen_even_when_flat():
    flat = ocean_scene(40, 9, 3, SeaState(wave_ft=0.0, period_s=4.0, score=0))
    water_rows = [row for row in flat.chars if any(ch in art.CREST_CHARS for ch in row)]
    assert len(water_rows) >= 2


def test_ship_and_flag_appear_for_a_pirate_sea():
    sea = SeaState(wave_ft=2.0, score=5, pirate=True, sprites=("ship",))
    text = "".join(
        ocean_scene(80, 12, frame, sea).to_text() for frame in range(0, 40, 4)
    )
    assert ")_)" in text          # the ship's sails
    assert "\u2620" in text       # the Jolly Roger


def test_no_flag_when_not_in_pirate_mode():
    sea = SeaState(wave_ft=2.0, score=5, pirate=False, sprites=("ship",))
    text = "".join(ocean_scene(80, 12, f, sea).to_text() for f in range(0, 40, 4))
    assert ")_)" in text
    assert "\u2620" not in text


def test_surfer_only_shows_up_when_it_is_rideable():
    flat = SeaState(wave_ft=0.2, score=1, sprites=("surfer",))
    rideable = SeaState(wave_ft=4.0, score=6, sprites=("surfer",))
    flat_text = "".join(ocean_scene(70, 10, f, flat).to_text() for f in range(0, 30, 3))
    good_text = "".join(ocean_scene(70, 10, f, rideable).to_text() for f in range(0, 30, 3))
    assert "\\o/" not in flat_text
    assert "\\o/" in good_text


def test_scene_survives_a_tiny_box():
    assert ocean_scene(0, 0, 5, SeaState()).to_text() == ""
    tiny = ocean_scene(8, 3, 5, SeaState(wave_ft=6.0))
    assert len(tiny.chars) == 3 and all(len(row) == 8 for row in tiny.chars)


def test_rain_is_deterministic_and_bounded():
    first = rain_canvas(40, 5, 9)
    assert first.to_text() == rain_canvas(40, 5, 9).to_text()
    assert len(first.chars) == 5
    assert rain_canvas(40, 5, 9).to_text() != rain_canvas(40, 5, 30).to_text()


def test_sparkline_scales_and_resamples():
    assert sparkline([], 10) == ""
    assert sparkline([1, 2, 3], 0) == ""
    line = sparkline([1, 2, 3, 4], 4)
    assert len(line) == 4
    assert line[0] == "\u2581" and line[-1] == "\u2588"
    assert sparkline([5, 5, 5], 3) == "\u2581\u2581\u2581"  # flat data, flat line
    assert len(sparkline(list(range(50)), 12)) == 12


@pytest.mark.parametrize("percent", [0, 0.4, 42, 99.9, 100, 150, -20])
def test_meter_width_is_exact_and_labelled(percent):
    width = 30
    segments = meter(percent, width)
    text = "".join(chunk for chunk, _ in segments)
    assert len(text) == width
    assert text.startswith("[") and text.endswith("]")
    assert "%" in text
    assert all(key for _, key in segments)


def test_meter_fill_grows_with_the_value():
    low = "".join(t for t, _ in meter(10, 40)).count("|")
    high = "".join(t for t, _ in meter(90, 40)).count("|")
    assert high > low


def test_meter_colours_escalate():
    keys = {key for _, key in meter(100, 40)}
    assert {"bar_ok", "bar_warn", "bar_crit"} <= keys


def test_ticker_scrolls_and_keeps_its_width():
    assert len(ticker(50, 0)) == 50
    assert len(ticker(50, 999)) == 50
    assert ticker(50, 0) != ticker(50, 10)
    assert ticker(0, 3) == ""
    # It wraps rather than running dry on a very wide terminal.
    assert len(ticker(400, 5)) == 400
