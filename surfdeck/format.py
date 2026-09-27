"""Panel content builders shared by the curses UI and the plain text output.

A panel is a list of rows; a row is a list of (text, theme_key) segments. The
curses layer paints the segments, the plain renderer just concatenates them.
"""

from __future__ import annotations

from . import animation, stats as stats_mod, surf as surf_mod
from .stats import SystemStats, format_bytes, format_cpu_time, format_duration, format_rate
from .surf import SurfReport

Row = list[tuple[str, str]]

# "  NN " label ahead of each CPU meter, and the narrowest useful meter.
CPU_LABEL_WIDTH = 6
MIN_METER = 12

FT_TO_M = 0.3048
KN_TO_KMH = 1.852


def f_to_c(value: float) -> float:
    return (value - 32) * 5 / 9


def fmt_height(feet: float | None, units: str) -> str:
    if feet is None:
        return "--"
    if units == "metric":
        return f"{feet * FT_TO_M:.1f} m"
    return f"{feet:.1f} ft"


def fmt_speed(knots: float | None, units: str) -> str:
    if knots is None:
        return "--"
    if units == "metric":
        return f"{knots * KN_TO_KMH:.0f} km/h"
    return f"{knots:.1f} kn"


def fmt_temp(fahrenheit: float | None, units: str) -> str:
    if fahrenheit is None:
        return "--"
    if units == "metric":
        return f"{f_to_c(fahrenheit):.0f}°C"
    return f"{fahrenheit:.0f}°F"


def fmt_period(seconds: float | None) -> str:
    return "--" if seconds is None else f"{seconds:.1f}s"


def fmt_direction(degrees: float | None) -> str:
    if degrees is None:
        return "--"
    return f"{surf_mod.compass(degrees)} {degrees:.0f}°"


def score_key(score: int) -> str:
    if score >= 6:
        return "good"
    if score >= 3:
        return "warn"
    return "bad"


def wind_key(relation: str) -> str:
    return {"OFFSHORE": "good", "CROSS-SHORE": "warn", "ONSHORE": "bad"}.get(
        relation, "dim"
    )


def load_key(load1: float, cores: int) -> str:
    ratio = load1 / max(1, cores)
    if ratio >= 1.0:
        return "bad"
    if ratio >= 0.6:
        return "warn"
    return "good"


def _pct_key(percent: float) -> str:
    if percent >= 90:
        return "bad"
    if percent >= 70:
        return "warn"
    return "good"


# --------------------------------------------------------------------------
# surf panel
# --------------------------------------------------------------------------

def surf_rows(report: SurfReport, width: int, units: str = "imperial") -> list[Row]:
    rows: list[Row] = []
    score = surf_mod.surf_score(report)
    relation = surf_mod.wind_relation(report.wind_direction_deg, report.facing_deg)

    stamp = (report.observed_at or "").replace("T", " ")
    header: Row = [(report.spot_name.upper(), "header")]
    if stamp:
        header.append(("  " + stamp, "dim"))
    if report.stale:
        header.append(("  [STALE CHART]", "bad"))
    elif report.error:
        header.append(("  [OFFLINE]", "bad"))
    else:
        header.append(("  ⚑ live", "good"))
    rows.append(header)

    if report.error and not report.ok:
        rows.append([("", "text")])
        rows.append([("  " + report.error, "bad")])
        rows.append([("  run again once ye have signal, matey.", "dim")])
        return [clip_row(row, width) for row in rows]

    filled = "█" * score + "░" * (10 - score)
    rows.append(
        [
            ("  SCORE ", "label"),
            (filled, score_key(score)),
            (f"  {score}/10", "score"),
        ]
    )
    rows.append([("  " + surf_mod.verdict(score), "accent")])
    rows.append([("", "text")])

    trend = animation.sparkline([row[1] for row in report.trend], 12)
    rows.append(
        [
            ("  WAVE  ", "label"),
            (f"{fmt_height(report.wave_height_ft, units):>8}", "value"),
            (f" @ {fmt_period(report.wave_period_s):>5}", "value"),
            (f"  from {fmt_direction(report.wave_direction_deg):<8}", "text"),
            (f" {surf_mod.arrow(report.wave_direction_deg)}", "accent"),
        ]
    )
    rows.append(
        [
            ("  SWELL ", "label"),
            (f"{fmt_height(report.swell_height_ft, units):>8}", "value"),
            (f" @ {fmt_period(report.swell_period_s):>5}", "value"),
            (f"  from {fmt_direction(report.swell_direction_deg):<8}", "text"),
            (f" {surf_mod.arrow(report.swell_direction_deg)}", "accent"),
        ]
    )
    gust = "" if report.wind_gust_kn is None else f" G {fmt_speed(report.wind_gust_kn, units)}"
    rows.append(
        [
            ("  WIND  ", "label"),
            (f"{fmt_speed(report.wind_speed_kn, units):>8}", "value"),
            (f"{gust:<12}", "text"),
            (f" from {fmt_direction(report.wind_direction_deg):<8}", "text"),
            (f" {relation}", wind_key(relation)),
        ]
    )
    rows.append(
        [
            ("  TEMP  ", "label"),
            (f"water {fmt_temp(report.water_temp_f, units)}", "value"),
            (f"   air {fmt_temp(report.air_temp_f, units)}", "value"),
        ]
    )
    sun: Row = [("  SUN   ", "label")]
    sun.append((f"rise {report.sunrise or '--:--'}", "text"))
    sun.append((f"   set {report.sunset or '--:--'}", "text"))
    rows.append(sun)
    if trend:
        rows.append(
            [
                ("  TREND ", "label"),
                (trend, "accent"),
                ("  wave height, next 12h", "dim"),
            ]
        )
    return [clip_row(row, width) for row in rows]


# --------------------------------------------------------------------------
# system panel
# --------------------------------------------------------------------------

def stats_rows(stats: SystemStats, width: int, top_n: int = 6,
               compact: bool = False) -> list[Row]:
    """htop-style rows. `compact` drops to one aggregate CPU meter and skips
    the mount/temperature/IO detail, for terminals with few rows to spare."""
    rows: list[Row] = []
    cores = max(1, len(stats.cpu_per_core))

    header: Row = [(f"SHIP'S SYSTEMS  {stats.host}".rstrip(), "header")]
    header.append((f"   up {format_duration(stats.uptime_s)}", "dim"))
    header.append(("   load ", "label"))
    header.append(
        (
            " ".join(f"{value:.2f}" for value in stats.load),
            load_key(stats.load[0], cores),
        )
    )
    rows.append(header)

    if compact:
        return _compact_stats_rows(stats, width, top_n, rows)

    # Lay the CPU meters out like htop: add columns only when the panel is
    # wide enough, and only once a single column would run past ~8 rows.
    # CPU_LABEL_WIDTH + MIN_METER cells are needed per column.
    by_width = max(1, width // (CPU_LABEL_WIDTH + MIN_METER))
    by_cores = -(-cores // 8)
    columns = max(1, min(by_width, by_cores, 4))
    bar_width = max(MIN_METER, width // columns - CPU_LABEL_WIDTH)
    per_row = columns
    for start in range(0, cores, per_row):
        row: Row = []
        for index in range(start, min(start + per_row, cores)):
            row.append((f"  {index:>2} ", "label"))
            row.extend(animation.meter(stats.cpu_per_core[index], bar_width))
        rows.append(row)

    mem_label = f" {format_bytes(stats.mem_used)}/{format_bytes(stats.mem_total)}"
    swap_label = f" {format_bytes(stats.swap_used)}/{format_bytes(stats.swap_total)}"
    suffix = max(len(mem_label), len(swap_label))
    ram_bar = max(MIN_METER, min(bar_width, width - CPU_LABEL_WIDTH - suffix))
    rows.append(
        [("  MEM ", "label")]
        + animation.meter(stats.mem_percent, ram_bar)
        + [(mem_label, "value")]
    )
    rows.append(
        [("  SWP ", "label")]
        + animation.meter(stats.swap_percent, ram_bar)
        + [(swap_label, "value")]
    )

    rows.append(
        [
            ("  TASKS ", "label"),
            (f"{stats.tasks}", "value"),
            (f" ({stats.threads} thr, {stats.running} run)", "dim"),
            ("   NET ", "label"),
            (f"↑{format_rate(stats.net_up_bps)}", "value"),
            (f" ↓{format_rate(stats.net_down_bps)}", "value"),
        ]
    )
    io_row: Row = [
        ("  DISK ", "label"),
        (f"r {format_rate(stats.disk_read_bps)}", "value"),
        (f"  w {format_rate(stats.disk_write_bps)}", "value"),
    ]
    if stats.cpu_freq_mhz:
        io_row.append((f"   CLK {stats.cpu_freq_mhz / 1000:.2f}GHz", "value"))
    rows.append(io_row)

    for mount, percent, used, total in stats.disks[:2]:
        rows.append(
            [
                (f"  {mount[:10]:<10} ", "label"),
                (f"{percent:5.1f}%", _pct_key(percent)),
                (f"  {format_bytes(used)}/{format_bytes(total)}", "dim"),
            ]
        )
    if stats.temps_c:
        temp_row: Row = [("  TEMP ", "label")]
        for label, value in stats.temps_c.items():
            key = "bad" if value >= 80 else ("warn" if value >= 65 else "good")
            temp_row.append((f"{label} ", "dim"))
            temp_row.append((f"{value:.1f}°C  ", key))
        rows.append(temp_row)

    rows.append([("", "text")])
    rows.append(
        [
            (
                f"  {'PID':>6} {'USER':<8} {'CPU%':>5} {'MEM%':>5} "
                f"{'TIME+':>9}  COMMAND",
                "accent",
            )
        ]
    )
    name_width = max(8, width - 40)
    for proc in stats.top[:top_n]:
        rows.append(
            [
                (f"  {proc.pid:>6} ", "dim"),
                (f"{proc.user:<8} ", "text"),
                (f"{proc.cpu_percent:5.1f} ", _pct_key(proc.cpu_percent)),
                (f"{proc.mem_percent:5.1f} ", _pct_key(proc.mem_percent)),
                (f"{format_cpu_time(proc.cpu_time_s):>9}  ", "dim"),
                (proc.command[:name_width], "value"),
            ]
        )
    return [clip_row(row, width) for row in rows]


def _compact_stats_rows(stats: SystemStats, width: int, top_n: int,
                        rows: list[Row]) -> list[Row]:
    cores = max(1, len(stats.cpu_per_core))
    mem_label = f" {format_bytes(stats.mem_used)}/{format_bytes(stats.mem_total)}"
    bar = max(MIN_METER, width - CPU_LABEL_WIDTH - len(mem_label))
    rows.append(
        [(f"  CPU ", "label")]
        + animation.meter(stats.cpu_total, bar)
        + [(f" x{cores}", "dim")]
    )
    rows.append(
        [("  MEM ", "label")]
        + animation.meter(stats.mem_percent, bar)
        + [(mem_label, "value")]
    )
    rows.append(
        [
            ("  TASKS ", "label"),
            (f"{stats.tasks}", "value"),
            (f" ({stats.running} run)", "dim"),
            ("  NET ", "label"),
            (f"\u2191{format_rate(stats.net_up_bps)}", "value"),
            (f" \u2193{format_rate(stats.net_down_bps)}", "value"),
        ]
    )
    rows.append(
        [
            (
                f"  {'PID':>6} {'USER':<8} {'CPU%':>5} {'MEM%':>5}  COMMAND",
                "accent",
            )
        ]
    )
    name_width = max(6, width - 30)
    for proc in stats.top[:top_n]:
        rows.append(
            [
                (f"  {proc.pid:>6} ", "dim"),
                (f"{proc.user:<8} ", "text"),
                (f"{proc.cpu_percent:5.1f} ", _pct_key(proc.cpu_percent)),
                (f"{proc.mem_percent:5.1f}  ", _pct_key(proc.mem_percent)),
                (proc.command[:name_width], "value"),
            ]
        )
    return [clip_row(row, width) for row in rows]


def clip_row(row: Row, width: int) -> Row:
    """Trim a row's segments so the row is at most `width` cells wide."""
    out: Row = []
    used = 0
    for text, key in row:
        if used >= width:
            break
        if used + len(text) > width:
            text = text[: width - used]
        if text:
            out.append((text, key))
            used += len(text)
    return out


def rows_to_text(rows: list[Row]) -> str:
    return "\n".join("".join(text for text, _ in row).rstrip() for row in rows)
