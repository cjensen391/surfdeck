import re

from surfdeck import plain
from surfdeck.surf import SurfReport

ANSI = re.compile(r"\033\[[0-9;]*m")


def test_plain_render_without_colour_has_no_escapes(report, system_stats):
    text = plain.render(report, system_stats, color=False, width=90)
    assert "\033[" not in text
    assert "SOUTH BEACH, FL" in text
    assert "SHIP'S SYSTEMS" in text
    assert ")_)" in text  # the galleon made it into the static frame
    for line in text.split("\n"):
        assert len(line) <= 90


def test_plain_render_with_colour_still_reads_the_same(report, system_stats):
    coloured = plain.render(report, system_stats, color=True, width=90)
    assert "\033[38;5;" in coloured
    stripped = ANSI.sub("", coloured)
    assert "4.2 ft" in stripped and "12.5s" in stripped and "9.0 kn" in stripped
    assert "OFFSHORE" in stripped


def test_scene_can_be_switched_off(report, system_stats):
    text = plain.render(report, system_stats, color=False, scene=False)
    assert ")_)" not in text
    assert "WAVE" in text


def test_ship_is_parked_in_view_at_any_width(report, system_stats):
    for width in (60, 80, 100, 140):
        text = plain.render(report, system_stats, color=False, width=width)
        assert ")_)" in text, f"ship missing at width {width}"


def test_offline_report_renders_an_explanation(report, system_stats):
    broken = SurfReport(report.spot_key, report.spot_name, report.facing_deg)
    broken.error = "no signal from the crow's nest: URLError"
    text = plain.render(broken, system_stats, color=False, width=80)
    assert "OFFLINE" in text and "crow's nest" in text
    assert "SHIP'S SYSTEMS" in text  # system stats still work offline


def test_each_theme_renders(report, system_stats):
    from surfdeck.theme import THEME_ORDER

    for name in THEME_ORDER:
        text = plain.render(report, system_stats, theme_name=name, color=True, width=80)
        assert "SOUTH BEACH" in ANSI.sub("", text)


def test_metric_units(report, system_stats):
    text = plain.render(report, system_stats, units="metric", color=False, width=80)
    assert "1.3 m" in text and "km/h" in text
