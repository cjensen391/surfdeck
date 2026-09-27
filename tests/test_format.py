import pytest

from surfdeck import format as fmt
from surfdeck.surf import SurfReport


def row_text(rows):
    return fmt.rows_to_text(rows)


def test_imperial_and_metric_formatting():
    assert fmt.fmt_height(3.0, "imperial") == "3.0 ft"
    assert fmt.fmt_height(3.0, "metric") == "0.9 m"
    assert fmt.fmt_speed(10.0, "imperial") == "10.0 kn"
    assert fmt.fmt_speed(10.0, "metric") == "19 km/h"
    assert fmt.fmt_temp(77.0, "imperial") == "77°F"
    assert fmt.fmt_temp(77.0, "metric") == "25°C"
    assert fmt.fmt_period(9.5) == "9.5s"
    assert fmt.fmt_direction(275) == "W 275°"


def test_missing_values_render_as_dashes():
    for formatter in (fmt.fmt_height, fmt.fmt_speed, fmt.fmt_temp):
        assert formatter(None, "imperial") == "--"
    assert fmt.fmt_period(None) == "--"
    assert fmt.fmt_direction(None) == "--"


@pytest.mark.parametrize(
    "score,key", [(0, "bad"), (2, "bad"), (3, "warn"), (5, "warn"), (6, "good"), (10, "good")]
)
def test_score_key_thresholds(score, key):
    assert fmt.score_key(score) == key


def test_wind_key_rewards_offshore():
    assert fmt.wind_key("OFFSHORE") == "good"
    assert fmt.wind_key("CROSS-SHORE") == "warn"
    assert fmt.wind_key("ONSHORE") == "bad"
    assert fmt.wind_key("UNKNOWN") == "dim"


def test_load_key_is_relative_to_core_count():
    assert fmt.load_key(0.5, 4) == "good"
    assert fmt.load_key(3.0, 4) == "warn"
    assert fmt.load_key(4.5, 4) == "bad"
    assert fmt.load_key(1.2, 1) == "bad"


def test_surf_rows_show_the_numbers_that_matter(report):
    text = row_text(fmt.surf_rows(report, 78))
    assert "SOUTH BEACH, FL" in text
    assert "live" in text
    assert "WAVE" in text and "4.2 ft" in text
    assert "11.5s" in text          # wave period
    assert "12.5s" in text          # swell period
    assert "9.0 kn" in text         # wind speed
    assert "G 14.0 kn" in text      # gust
    assert "OFFSHORE" in text
    assert "water 77°F" in text and "air 82°F" in text
    assert "rise 07:11" in text and "set 19:11" in text
    assert "TREND" in text


def test_surf_rows_in_metric(report):
    text = row_text(fmt.surf_rows(report, 78, units="metric"))
    assert "1.3 m" in text
    assert "km/h" in text
    assert "25°C" in text


def test_surf_rows_flag_a_stale_chart(report):
    report.stale = True
    assert "STALE CHART" in row_text(fmt.surf_rows(report, 78))


def test_surf_rows_explain_a_dead_connection(report):
    broken = SurfReport(report.spot_key, report.spot_name, report.facing_deg)
    broken.error = "no signal from the crow's nest: URLError"
    text = row_text(fmt.surf_rows(broken, 78))
    assert "OFFLINE" in text
    assert "crow's nest" in text
    assert "WAVE" not in text


def test_stats_rows_cover_the_htop_essentials(system_stats):
    text = row_text(fmt.stats_rows(system_stats, 96))
    assert "jerrycan" in text
    assert "up 1d 01:01:01" in text
    assert "load 1.50 1.20 0.90" in text
    assert "MEM" in text and "3.0G/8.0G" in text
    assert "SWP" in text
    assert "TASKS 204" in text and "811 thr" in text
    assert "2.0K/s" in text and "10.0K/s" in text
    assert "CLK 2.40GHz" in text
    assert "27.1%" in text
    assert "cpu_thermal" in text and "59.5" in text
    assert "PID" in text and "COMMAND" in text
    assert "1234" in text and "python3 -m surfdeck" in text
    assert "1:05.50" in text  # TIME+ of the top process


def test_every_core_gets_a_meter(system_stats):
    text = row_text(fmt.stats_rows(system_stats, 96))
    assert text.count("[") >= len(system_stats.cpu_per_core) + 2  # cores + MEM + SWP


@pytest.mark.parametrize("width", [38, 48, 59, 72, 96, 120, 200])
def test_panels_never_overflow_their_column(report, system_stats, width):
    # Regression: panels used to be built at screen width inside a split
    # layout, so the htop meters spilled across the divider.
    for rows in (fmt.surf_rows(report, width), fmt.stats_rows(system_stats, width)):
        for row in rows:
            assert sum(len(text) for text, _ in row) <= width, row


def test_top_n_limits_the_process_list(system_stats):
    rows = fmt.stats_rows(system_stats, 96, top_n=1)
    assert "1234" in row_text(rows)
    assert "systemd" not in row_text(rows)


def test_every_segment_has_a_theme_key(report, system_stats):
    from surfdeck.theme import get_theme

    theme = get_theme("pirate")
    for rows in (fmt.surf_rows(report, 80), fmt.stats_rows(system_stats, 80)):
        for row in rows:
            for _text, key in row:
                assert isinstance(key, str) and key
                assert theme.style(key)


def test_compact_stats_fit_a_short_panel(system_stats):
    rows = fmt.stats_rows(system_stats, 70, top_n=2, compact=True)
    text = row_text(rows)
    # One aggregate CPU meter instead of one per core, and no mount/temp detail.
    assert "CPU" in text and "x4" in text
    assert "MEM" in text and "TASKS" in text
    assert "cpu_thermal" not in text and "CLK" not in text
    assert "SWP" not in text
    assert "1234" in text  # the process list survives
    assert len(rows) < len(fmt.stats_rows(system_stats, 70, top_n=2))


@pytest.mark.parametrize("width", [38, 48, 70, 96, 200])
def test_compact_stats_respect_their_width(system_stats, width):
    for row in fmt.stats_rows(system_stats, width, compact=True):
        assert sum(len(text) for text, _ in row) <= width
