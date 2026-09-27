"""Surf report fetching, parsing and scoring.

Data comes from the Open-Meteo marine + forecast APIs, which need no API key.
Fetching (network) is kept separate from parsing (pure) so the parsing and
scoring logic is testable without a socket.

Canonical units inside a SurfReport are imperial: feet, seconds, knots,
degrees Fahrenheit, compass degrees. Conversion to metric happens at format
time in `format.py`.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .spots import Spot

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "surfdeck/0.1 (+terminal surf report)"

COMPASS_POINTS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)


@dataclass
class SurfReport:
    """One snapshot of conditions at a spot."""

    spot_key: str
    spot_name: str
    facing_deg: float
    observed_at: str | None = None
    wave_height_ft: float | None = None
    wave_period_s: float | None = None
    wave_direction_deg: float | None = None
    swell_height_ft: float | None = None
    swell_period_s: float | None = None
    swell_direction_deg: float | None = None
    water_temp_f: float | None = None
    air_temp_f: float | None = None
    wind_speed_kn: float | None = None
    wind_gust_kn: float | None = None
    wind_direction_deg: float | None = None
    sunrise: str | None = None
    sunset: str | None = None
    # (iso hour, wave height ft, wave period s) for the trend sparkline.
    trend: list[tuple[str, float, float]] = field(default_factory=list)
    fetched_at: float = 0.0
    stale: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.wave_height_ft is not None

    def to_json(self) -> dict:
        data = asdict(self)
        data["trend"] = [list(row) for row in self.trend]
        return data

    @classmethod
    def from_json(cls, data: dict) -> "SurfReport":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        clean["trend"] = [tuple(row) for row in clean.get("trend") or []]
        return cls(**clean)


# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------

def compass(deg: float | None) -> str:
    """Bearing in degrees -> 16-point compass abbreviation."""
    if deg is None:
        return "--"
    idx = int((float(deg) % 360) / 22.5 + 0.5) % 16
    return COMPASS_POINTS[idx]


def arrow(deg: float | None) -> str:
    """Bearing -> arrow pointing the way the wind/swell is heading."""
    if deg is None:
        return " "
    arrows = "↓↙←↖↑↗→↘"
    idx = int((float(deg) % 360) / 45 + 0.5) % 8
    return arrows[idx]


def angle_delta(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings, 0-180."""
    return abs((a - b + 180) % 360 - 180)


def wind_relation(wind_from_deg: float | None, facing_deg: float) -> str:
    """OFFSHORE / ONSHORE / CROSS-SHORE for a wind blowing *from* a bearing.

    A beach facing 95 deg with wind from 275 deg (the opposite side, i.e. off
    the land) is offshore and grooms the face; wind from 95 deg is onshore.
    """
    if wind_from_deg is None:
        return "UNKNOWN"
    offshore_source = (facing_deg + 180) % 360
    if angle_delta(wind_from_deg, offshore_source) <= 55:
        return "OFFSHORE"
    if angle_delta(wind_from_deg, facing_deg) <= 55:
        return "ONSHORE"
    return "CROSS-SHORE"


def c_to_f(celsius: float | None) -> float | None:
    return None if celsius is None else celsius * 9 / 5 + 32


def raw_score(report: SurfReport) -> float:
    """Unrounded 0-10 surf score from size, period and wind."""
    if not report.ok:
        return 0.0
    height = report.wave_height_ft or 0.0
    period = report.swell_period_s or report.wave_period_s or 0.0

    # Size: flat to 8ft+ maps onto 0-6.
    size = min(height / 8.0, 1.0) * 6.0
    # Period: 4s wind slop to 14s groundswell maps onto 0-3.
    groom = max(0.0, min((period - 4.0) / 10.0, 1.0)) * 3.0
    score = size + groom

    relation = wind_relation(report.wind_direction_deg, report.facing_deg)
    wind = report.wind_speed_kn or 0.0
    if relation == "OFFSHORE":
        score += 1.0 if wind >= 4 else 0.5
    elif relation == "ONSHORE":
        score -= min(wind / 8.0, 3.0)
    else:
        score -= min(wind / 16.0, 1.5)

    return max(0.0, min(score, 10.0))


def surf_score(report: SurfReport) -> int:
    """`raw_score` rounded to the 0-10 integer the UI shows."""
    return int(round(raw_score(report)))


VERDICTS = (
    (0, "DEAD FLAT - the sea be a millpond, ye landlubber"),
    (1, "ANKLE BITERS - bring a boogie board and low standards"),
    (3, "KNEE TO WAIST - rideable, barely. Log it."),
    (5, "CHEST HIGH AND CLEAN - hoist the colors, she be surfable"),
    (7, "SHOULDER HIGH PLUS - all hands on deck, tide's callin'"),
    (9, "OVERHEAD MAYHEM - batten down, only the bold paddle out"),
)


def verdict(score: int) -> str:
    text = VERDICTS[0][1]
    for threshold, phrase in VERDICTS:
        if score >= threshold:
            text = phrase
    return text


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def _num(value):
    return None if value is None else float(value)


def parse_marine(payload: dict, report: SurfReport) -> SurfReport:
    current = payload.get("current") or {}
    report.observed_at = current.get("time") or report.observed_at
    report.wave_height_ft = _num(current.get("wave_height"))
    report.wave_period_s = _num(current.get("wave_period"))
    report.wave_direction_deg = _num(current.get("wave_direction"))
    report.swell_height_ft = _num(current.get("swell_wave_height"))
    report.swell_period_s = _num(current.get("swell_wave_period"))
    report.swell_direction_deg = _num(current.get("swell_wave_direction"))
    # sea_surface_temperature is served in Celsius regardless of length_unit.
    report.water_temp_f = c_to_f(_num(current.get("sea_surface_temperature")))

    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    heights = hourly.get("wave_height") or []
    periods = hourly.get("wave_period") or []
    start = 0
    if report.observed_at:
        hour = report.observed_at[:13]
        for i, stamp in enumerate(times):
            if stamp[:13] >= hour:
                start = i
                break
    trend: list[tuple[str, float, float]] = []
    for i in range(start, min(start + 12, len(times))):
        height = heights[i] if i < len(heights) else None
        period = periods[i] if i < len(periods) else None
        if height is None:
            continue
        trend.append((times[i], float(height), float(period or 0.0)))
    report.trend = trend
    return report


def parse_weather(payload: dict, report: SurfReport) -> SurfReport:
    current = payload.get("current") or {}
    report.air_temp_f = _num(current.get("temperature_2m"))
    report.wind_speed_kn = _num(current.get("wind_speed_10m"))
    report.wind_gust_kn = _num(current.get("wind_gusts_10m"))
    report.wind_direction_deg = _num(current.get("wind_direction_10m"))

    daily = payload.get("daily") or {}
    sunrise = (daily.get("sunrise") or [None])[0]
    sunset = (daily.get("sunset") or [None])[0]
    report.sunrise = sunrise[11:16] if sunrise else None
    report.sunset = sunset[11:16] if sunset else None
    return report


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

def _get_json(url: str, params: dict, timeout: float) -> dict:
    query = urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(
        f"{url}?{query}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_report(spot: Spot, timeout: float = 8.0) -> SurfReport:
    """Fetch live conditions. Never raises: failures land in `report.error`."""
    report = SurfReport(
        spot_key=spot.key,
        spot_name=spot.name,
        facing_deg=spot.facing_deg,
        fetched_at=time.time(),
    )
    marine_params = {
        "latitude": spot.latitude,
        "longitude": spot.longitude,
        "current": ",".join(
            (
                "wave_height",
                "wave_period",
                "wave_direction",
                "swell_wave_height",
                "swell_wave_period",
                "swell_wave_direction",
                "sea_surface_temperature",
            )
        ),
        "hourly": "wave_height,wave_period",
        "length_unit": "imperial",
        "timezone": spot.timezone,
        "forecast_days": 2,
    }
    weather_params = {
        "latitude": spot.latitude,
        "longitude": spot.longitude,
        "current": "temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "daily": "sunrise,sunset",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "kn",
        "timezone": spot.timezone,
        "forecast_days": 1,
    }
    try:
        parse_marine(_get_json(MARINE_URL, marine_params, timeout), report)
        parse_weather(_get_json(FORECAST_URL, weather_params, timeout), report)
    except (urllib.error.URLError, OSError) as exc:
        report.error = f"no signal from the crow's nest: {exc.__class__.__name__}"
    except (ValueError, KeyError, TypeError) as exc:
        report.error = f"garbled chart data: {exc.__class__.__name__}"
    return report


# --------------------------------------------------------------------------
# cache (so an offline run still shows the last known conditions)
# --------------------------------------------------------------------------

def cache_path(spot_key: str) -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "surfdeck" / f"{spot_key}.json"


def save_cache(report: SurfReport) -> None:
    if not report.ok:
        return
    path = cache_path(report.spot_key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_json()), encoding="utf-8")
    except OSError:
        pass


def load_cache(spot_key: str) -> SurfReport | None:
    try:
        data = json.loads(cache_path(spot_key).read_text(encoding="utf-8"))
        report = SurfReport.from_json(data)
    except (OSError, ValueError, TypeError):
        return None
    report.stale = True
    return report


def get_report(spot: Spot, timeout: float = 8.0) -> SurfReport:
    """Live report if the net answers, else the cached one flagged stale."""
    report = fetch_report(spot, timeout=timeout)
    if report.ok:
        save_cache(report)
        return report
    cached = load_cache(spot.key)
    if cached is not None:
        cached.error = report.error
        return cached
    return report
