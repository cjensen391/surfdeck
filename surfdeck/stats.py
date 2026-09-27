"""System stats, htop-style, via psutil (works on Linux and macOS).

`Sampler` keeps the previous counters so network and disk I/O can be reported
as rates rather than monotonic totals, which is what htop-ish output wants.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import psutil


@dataclass
class ProcInfo:
    pid: int
    user: str
    cpu_percent: float
    mem_percent: float
    cpu_time_s: float
    name: str
    command: str


@dataclass
class SystemStats:
    cpu_total: float = 0.0
    cpu_per_core: list[float] = field(default_factory=list)
    cpu_freq_mhz: float | None = None
    load: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mem_used: int = 0
    mem_total: int = 0
    mem_percent: float = 0.0
    swap_used: int = 0
    swap_total: int = 0
    swap_percent: float = 0.0
    uptime_s: float = 0.0
    tasks: int = 0
    threads: int = 0
    running: int = 0
    top: list[ProcInfo] = field(default_factory=list)
    net_up_bps: float = 0.0
    net_down_bps: float = 0.0
    disk_read_bps: float = 0.0
    disk_write_bps: float = 0.0
    disks: list[tuple[str, float, int, int]] = field(default_factory=list)
    temps_c: dict[str, float] = field(default_factory=dict)
    host: str = ""


def format_bytes(value: float) -> str:
    """Bytes -> short human string (htop-ish: 1 decimal, binary units)."""
    value = float(value)
    for unit in ("B", "K", "M", "G", "T"):
        if abs(value) < 1024 or unit == "T":
            if unit == "B":
                return f"{value:.0f}B"
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}T"


def format_rate(bytes_per_s: float) -> str:
    return f"{format_bytes(bytes_per_s)}/s"


def format_duration(seconds: float) -> str:
    """Seconds -> `3d 04:12:07` / `04:12:07` / `12:07`."""
    seconds = int(max(0, seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_cpu_time(seconds: float) -> str:
    """htop's TIME+ column: minutes:seconds.hundredths."""
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}:{secs:05.2f}"


class Sampler:
    """Repeatedly snapshots the machine. Call `sample()` on a timer."""

    def __init__(self, top_n: int = 8) -> None:
        self.top_n = top_n
        self._last_time = time.monotonic()
        self._last_net = self._net_counters()
        self._last_disk = self._disk_counters()
        self._primed = False
        # Prime psutil's per-process CPU deltas so the first real sample is
        # not a meaningless since-boot average.
        psutil.cpu_percent(percpu=True)
        for proc in psutil.process_iter():
            try:
                proc.cpu_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    @staticmethod
    def _net_counters() -> tuple[int, int]:
        try:
            counters = psutil.net_io_counters()
        except (RuntimeError, OSError):
            return (0, 0)
        if counters is None:
            return (0, 0)
        return (counters.bytes_sent, counters.bytes_recv)

    @staticmethod
    def _disk_counters() -> tuple[int, int]:
        try:
            counters = psutil.disk_io_counters()
        except (RuntimeError, OSError):
            return (0, 0)
        if counters is None:
            return (0, 0)
        return (counters.read_bytes, counters.write_bytes)

    def sample(self) -> SystemStats:
        stats = SystemStats()
        now = time.monotonic()
        elapsed = max(now - self._last_time, 1e-6)
        self._last_time = now

        stats.cpu_per_core = psutil.cpu_percent(percpu=True)
        stats.cpu_total = (
            sum(stats.cpu_per_core) / len(stats.cpu_per_core)
            if stats.cpu_per_core
            else 0.0
        )
        try:
            freq = psutil.cpu_freq()
            stats.cpu_freq_mhz = freq.current if freq else None
        except (AttributeError, NotImplementedError, OSError):
            stats.cpu_freq_mhz = None

        try:
            stats.load = tuple(os.getloadavg())  # type: ignore[assignment]
        except (OSError, AttributeError):
            stats.load = (0.0, 0.0, 0.0)

        mem = psutil.virtual_memory()
        stats.mem_used = mem.total - mem.available
        stats.mem_total = mem.total
        stats.mem_percent = 100.0 * stats.mem_used / mem.total if mem.total else 0.0
        swap = psutil.swap_memory()
        stats.swap_used, stats.swap_total = swap.used, swap.total
        stats.swap_percent = swap.percent

        stats.uptime_s = max(0.0, time.time() - psutil.boot_time())
        stats.host = os.uname().nodename if hasattr(os, "uname") else ""

        stats.tasks, stats.threads, stats.running, stats.top = self._processes()

        sent, recv = self._net_counters()
        last_sent, last_recv = self._last_net
        stats.net_up_bps = max(0, sent - last_sent) / elapsed
        stats.net_down_bps = max(0, recv - last_recv) / elapsed
        self._last_net = (sent, recv)

        read, write = self._disk_counters()
        last_read, last_write = self._last_disk
        stats.disk_read_bps = max(0, read - last_read) / elapsed
        stats.disk_write_bps = max(0, write - last_write) / elapsed
        self._last_disk = (read, write)

        stats.disks = self._disks()
        stats.temps_c = self._temps()

        if not self._primed:
            # First sample's rates span the Sampler's construction, not a real
            # interval; zero them rather than report a spike.
            stats.net_up_bps = stats.net_down_bps = 0.0
            stats.disk_read_bps = stats.disk_write_bps = 0.0
            self._primed = True
        return stats

    def _processes(self) -> tuple[int, int, int, list[ProcInfo]]:
        procs: list[ProcInfo] = []
        tasks = threads = running = 0
        attrs = [
            "pid", "name", "username", "cpu_percent", "memory_percent",
            "cpu_times", "num_threads", "status", "cmdline",
        ]
        for proc in psutil.process_iter(attrs=attrs, ad_value=None):
            info = proc.info
            tasks += 1
            threads += info.get("num_threads") or 0
            if info.get("status") == psutil.STATUS_RUNNING:
                running += 1
            times = info.get("cpu_times")
            cmdline = info.get("cmdline") or []
            procs.append(
                ProcInfo(
                    pid=info.get("pid") or 0,
                    user=(info.get("username") or "?").split("\\")[-1][:8],
                    cpu_percent=info.get("cpu_percent") or 0.0,
                    mem_percent=info.get("memory_percent") or 0.0,
                    cpu_time_s=(times.user + times.system) if times else 0.0,
                    name=info.get("name") or "?",
                    command=" ".join(cmdline) if cmdline else (info.get("name") or "?"),
                )
            )
        procs.sort(key=lambda p: (p.cpu_percent, p.mem_percent), reverse=True)
        return tasks, threads, running, procs[: self.top_n]

    @staticmethod
    def _disks() -> list[tuple[str, float, int, int]]:
        seen: set[str] = set()
        out: list[tuple[str, float, int, int]] = []
        for part in psutil.disk_partitions(all=False):
            if part.mountpoint in seen or "loop" in part.device:
                continue
            seen.add(part.mountpoint)
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            out.append((part.mountpoint, usage.percent, usage.used, usage.total))
        out.sort(key=lambda row: row[3], reverse=True)
        return out[:3]

    @staticmethod
    def _temps() -> dict[str, float]:
        getter = getattr(psutil, "sensors_temperatures", None)
        if getter is None:
            return {}
        try:
            raw = getter()
        except (OSError, RuntimeError, NotImplementedError):
            return {}
        temps: dict[str, float] = {}
        for chip, entries in (raw or {}).items():
            for entry in entries:
                if entry.current:
                    label = entry.label or chip
                    temps.setdefault(label[:12], float(entry.current))
        return dict(list(temps.items())[:3])
