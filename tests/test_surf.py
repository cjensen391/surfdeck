import json

import pytest

from surfdeck import surf
from surfdeck.surf import SurfReport


def test_compass_covers_all_sixteen_points():
    assert surf.compass(0) == "N"
    assert surf.compass(90) == "E"
    assert surf.compass(180) == "S"
    assert surf.compass(270) == "W"
    assert surf.compass(32) == "NNE"
    assert surf.compass(359) == "N"
    assert surf.compass(None) == "--"
    # Every bearing maps to one of the known points.
    assert {surf.compass(d) for d in range(0, 360, 3)} == set(surf.COMPASS_POINTS)


def test_arrow_points_where_the_flow_is_headed():
    assert surf.arrow(0) == "↓"   # from the north -> heading south
    assert surf.arrow(270) == "→"  # from the west -> heading east
    assert surf.arrow(None) == " "


def test_angle_delta_wraps():
    assert surf.angle_delta(10, 350) == 20
    assert surf.angle_delta(0, 180) == 180


@pytest.mark.parametrize(
    "wind_from,expected",
    [
        (275, "OFFSHORE"),    # off the land for a beach facing 95
        (95, "ONSHORE"),
        (58, "ONSHORE"),      # within 55 deg of the facing bearing
        (5, "CROSS-SHORE"),
        (185, "CROSS-SHORE"),
        (None, "UNKNOWN"),
    ],
)
def test_wind_relation(wind_from, expected):
    assert surf.wind_relation(wind_from, 95.0) == expected


def test_surf_score_rises_with_size_and_period(report):
    baseline = surf.raw_score(report)
    bigger = SurfReport(**{**report.__dict__, "wave_height_ft": 8.0})
    assert surf.raw_score(bigger) > baseline
    shorter = SurfReport(**{**report.__dict__, "swell_period_s": 5.0})
    assert surf.raw_score(shorter) < baseline


def test_onshore_wind_costs_more_than_cross_shore(report):
    onshore = SurfReport(**{**report.__dict__, "wind_direction_deg": 95})
    cross = SurfReport(**{**report.__dict__, "wind_direction_deg": 5})
    offshore = SurfReport(**{**report.__dict__, "wind_direction_deg": 275})
    # Compared on the unrounded score: the integer the UI shows can tie.
    assert surf.raw_score(onshore) < surf.raw_score(cross) < surf.raw_score(offshore)
    assert surf.surf_score(onshore) <= surf.surf_score(cross) < surf.surf_score(offshore)


def test_score_is_clamped_to_zero_ten(report):
    huge = SurfReport(**{**report.__dict__, "wave_height_ft": 60.0, "swell_period_s": 22.0})
    assert surf.surf_score(huge) == 10
    blown = SurfReport(
        **{
            **report.__dict__,
            "wave_height_ft": 0.1,
            "swell_period_s": 3.0,
            "wind_speed_kn": 40.0,
            "wind_direction_deg": 95,
        }
    )
    assert surf.surf_score(blown) == 0


def test_score_of_a_broken_report_is_zero(report):
    broken = SurfReport(**{**report.__dict__, "wave_height_ft": None})
    assert surf.surf_score(broken) == 0
    assert not broken.ok


def test_verdict_climbs_with_score():
    phrases = [surf.verdict(score) for score in range(11)]
    assert phrases[0] != phrases[5] != phrases[10]
    assert "FLAT" in phrases[0]
    assert phrases[10] == surf.VERDICTS[-1][1]


def test_parse_marine_converts_water_temp_and_windows_the_trend(marine_payload, spot):
    report = surf.SurfReport(spot.key, spot.name, spot.facing_deg)
    surf.parse_marine(marine_payload, report)
    assert report.wave_height_ft == 4.2
    assert report.swell_period_s == 12.5
    # 25 C water is 77 F.
    assert report.water_temp_f == pytest.approx(77.0)
    # The trend starts at the observed hour, dropping the two earlier rows.
    assert [row[0] for row in report.trend] == [
        "2026-09-27T13:00",
        "2026-09-27T14:00",
        "2026-09-27T15:00",
    ]
    assert report.trend[0][1] == 4.2


def test_parse_marine_tolerates_missing_hourly(spot):
    report = surf.SurfReport(spot.key, spot.name, spot.facing_deg)
    surf.parse_marine({"current": {"wave_height": 2.0}}, report)
    assert report.wave_height_ft == 2.0
    assert report.trend == []


def test_parse_weather_trims_sun_times(weather_payload, spot):
    report = surf.SurfReport(spot.key, spot.name, spot.facing_deg)
    surf.parse_weather(weather_payload, report)
    assert (report.sunrise, report.sunset) == ("07:11", "19:11")
    assert report.wind_gust_kn == 14.0


def test_report_json_round_trip(report):
    restored = SurfReport.from_json(json.loads(json.dumps(report.to_json())))
    assert restored == report


def test_from_json_ignores_unknown_fields(report):
    payload = report.to_json()
    payload["a_new_field_from_the_future"] = 1
    assert SurfReport.from_json(payload).wave_height_ft == report.wave_height_ft


def test_fetch_report_records_network_failure(monkeypatch, spot):
    def boom(*_args, **_kwargs):
        raise OSError("no route to the sea")

    monkeypatch.setattr(surf, "_get_json", boom)
    report = surf.fetch_report(spot, timeout=0.1)
    assert not report.ok
    assert "crow's nest" in report.error


def test_get_report_falls_back_to_cache(monkeypatch, tmp_path, spot, report):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    surf.save_cache(report)
    assert surf.cache_path(spot.key).exists()

    def offline(_spot, timeout=8.0):
        broken = SurfReport(_spot.key, _spot.name, _spot.facing_deg)
        broken.error = "no signal"
        return broken

    monkeypatch.setattr(surf, "fetch_report", offline)
    fallback = surf.get_report(spot)
    assert fallback.stale
    assert fallback.wave_height_ft == report.wave_height_ft
    assert fallback.error == "no signal"


def test_get_report_without_cache_returns_the_error(monkeypatch, tmp_path, spot):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def offline(_spot, timeout=8.0):
        broken = SurfReport(_spot.key, _spot.name, _spot.facing_deg)
        broken.error = "no signal"
        return broken

    monkeypatch.setattr(surf, "fetch_report", offline)
    result = surf.get_report(spot)
    assert not result.ok and not result.stale and result.error == "no signal"


def test_save_cache_skips_broken_reports(monkeypatch, tmp_path, spot):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    broken = SurfReport(spot.key, spot.name, spot.facing_deg)
    broken.error = "nope"
    surf.save_cache(broken)
    assert not surf.cache_path(spot.key).exists()
