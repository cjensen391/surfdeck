import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from surfdeck.spots import get_spot
from surfdeck.stats import ProcInfo, SystemStats
from surfdeck.surf import SurfReport

MARINE_PAYLOAD = {
    "current": {
        "time": "2026-09-27T13:00",
        "wave_height": 4.2,
        "wave_period": 11.5,
        "wave_direction": 80,
        "swell_wave_height": 3.9,
        "swell_wave_period": 12.5,
        "swell_wave_direction": 75,
        "sea_surface_temperature": 25.0,
    },
    "hourly": {
        "time": [
            "2026-09-27T11:00",
            "2026-09-27T12:00",
            "2026-09-27T13:00",
            "2026-09-27T14:00",
            "2026-09-27T15:00",
        ],
        "wave_height": [1.0, 2.0, 4.2, 4.5, 5.0],
        "wave_period": [9.0, 10.0, 11.5, 11.8, 12.0],
    },
}

WEATHER_PAYLOAD = {
    "current": {
        "time": "2026-09-27T13:00",
        "temperature_2m": 82.0,
        "wind_speed_10m": 9.0,
        "wind_direction_10m": 275,
        "wind_gusts_10m": 14.0,
    },
    "daily": {
        "time": ["2026-09-27"],
        "sunrise": ["2026-09-27T07:11"],
        "sunset": ["2026-09-27T19:11"],
    },
}


@pytest.fixture
def spot():
    return get_spot("south-beach")


@pytest.fixture
def marine_payload():
    return {
        "current": dict(MARINE_PAYLOAD["current"]),
        "hourly": {k: list(v) for k, v in MARINE_PAYLOAD["hourly"].items()},
    }


@pytest.fixture
def weather_payload():
    return {
        "current": dict(WEATHER_PAYLOAD["current"]),
        "daily": {k: list(v) for k, v in WEATHER_PAYLOAD["daily"].items()},
    }


@pytest.fixture
def report(spot):
    """A solid, clean, offshore day at South Beach."""
    return SurfReport(
        spot_key=spot.key,
        spot_name=spot.name,
        facing_deg=spot.facing_deg,
        observed_at="2026-09-27T13:00",
        wave_height_ft=4.2,
        wave_period_s=11.5,
        wave_direction_deg=80,
        swell_height_ft=3.9,
        swell_period_s=12.5,
        swell_direction_deg=75,
        water_temp_f=77.0,
        air_temp_f=82.0,
        wind_speed_kn=9.0,
        wind_gust_kn=14.0,
        wind_direction_deg=275,
        sunrise="07:11",
        sunset="19:11",
        trend=[("2026-09-27T13:00", 4.2, 11.5), ("2026-09-27T14:00", 4.5, 11.8)],
    )


@pytest.fixture
def system_stats():
    return SystemStats(
        cpu_total=25.0,
        cpu_per_core=[10.0, 20.0, 30.0, 40.0],
        cpu_freq_mhz=2400.0,
        load=(1.5, 1.2, 0.9),
        mem_used=3 * 1024**3,
        mem_total=8 * 1024**3,
        mem_percent=37.5,
        swap_used=0,
        swap_total=2 * 1024**3,
        swap_percent=0.0,
        uptime_s=90061.0,
        tasks=204,
        threads=811,
        running=2,
        top=[
            ProcInfo(1234, "cjensen", 12.5, 3.25, 65.5, "python3", "python3 -m surfdeck"),
            ProcInfo(1, "root", 0.0, 0.1, 12.0, "systemd", "/sbin/init"),
        ],
        net_up_bps=2048.0,
        net_down_bps=10240.0,
        disk_read_bps=0.0,
        disk_write_bps=4096.0,
        disks=[("/", 27.1, 14 * 1024**3, 52 * 1024**3)],
        temps_c={"cpu_thermal": 59.5},
        host="jerrycan",
    )
