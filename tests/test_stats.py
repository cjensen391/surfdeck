import time

import pytest

from surfdeck import stats as stats_mod
from surfdeck.stats import Sampler, format_bytes, format_cpu_time, format_duration, format_rate


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "0B"),
        (512, "512B"),
        (1024, "1.0K"),
        (1536, "1.5K"),
        (5 * 1024**2, "5.0M"),
        (3 * 1024**3, "3.0G"),
        (2 * 1024**4, "2.0T"),
        (5 * 1024**5, "5120.0T"),
    ],
)
def test_format_bytes(value, expected):
    assert format_bytes(value) == expected


def test_format_rate_appends_per_second():
    assert format_rate(2048) == "2.0K/s"


@pytest.mark.parametrize(
    "seconds,expected",
    [(0, "00:00"), (61, "01:01"), (3600, "01:00:00"), (90061, "1d 01:01:01"), (-5, "00:00")],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_format_cpu_time_matches_htop_style():
    assert format_cpu_time(0) == "0:00.00"
    assert format_cpu_time(65.5) == "1:05.50"
    assert format_cpu_time(3725.25) == "62:05.25"


def test_sample_reports_plausible_machine_state():
    sampler = Sampler(top_n=5)
    time.sleep(0.25)
    stats = sampler.sample()

    assert stats.cpu_per_core, "expected at least one core"
    assert all(0.0 <= value <= 100.0 for value in stats.cpu_per_core)
    assert 0.0 <= stats.cpu_total <= 100.0
    assert stats.mem_total > 0
    assert 0 <= stats.mem_used <= stats.mem_total
    assert 0.0 <= stats.mem_percent <= 100.0
    assert stats.uptime_s > 0
    assert stats.tasks >= 1
    assert stats.threads >= stats.tasks
    assert len(stats.top) <= 5
    assert stats.top == sorted(
        stats.top, key=lambda p: (p.cpu_percent, p.mem_percent), reverse=True
    )
    for proc in stats.top:
        assert proc.pid >= 0
        assert proc.command


def test_first_sample_zeroes_io_rates():
    # Rates on the first sample would otherwise cover the Sampler's own setup.
    stats = Sampler(top_n=1).sample()
    assert stats.net_up_bps == 0.0
    assert stats.net_down_bps == 0.0
    assert stats.disk_read_bps == 0.0
    assert stats.disk_write_bps == 0.0


def test_later_samples_report_non_negative_rates():
    sampler = Sampler(top_n=1)
    sampler.sample()
    time.sleep(0.2)
    stats = sampler.sample()
    assert stats.net_up_bps >= 0.0 and stats.net_down_bps >= 0.0
    assert stats.disk_read_bps >= 0.0 and stats.disk_write_bps >= 0.0


def test_counter_reset_does_not_produce_negative_rates(monkeypatch):
    sampler = Sampler(top_n=1)
    sampler.sample()
    # Pretend the interface counters wrapped or the device was re-plugged.
    sampler._last_net = (10**12, 10**12)
    sampler._last_disk = (10**12, 10**12)
    stats = sampler.sample()
    assert stats.net_up_bps == 0.0 and stats.disk_write_bps == 0.0


def test_missing_sensors_are_tolerated(monkeypatch):
    monkeypatch.setattr(stats_mod.psutil, "sensors_temperatures", lambda: {}, raising=False)
    assert Sampler(top_n=1)._temps() == {}

    def unsupported():
        raise NotImplementedError

    monkeypatch.setattr(stats_mod.psutil, "sensors_temperatures", unsupported, raising=False)
    assert Sampler(top_n=1)._temps() == {}
