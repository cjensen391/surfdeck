"""Command line entry point."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time

from . import __version__, plain, spots, stats as stats_mod, surf as surf_mod, theme


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="surfdeck",
        description=(
            "Pirate-flavoured surf report and system monitor for the terminal. "
            "Defaults to South Beach, FL."
        ),
    )
    parser.add_argument(
        "--spot", default=spots.DEFAULT_SPOT,
        help=f"spot to report (default: {spots.DEFAULT_SPOT})",
    )
    parser.add_argument("--list-spots", action="store_true", help="list known spots and exit")
    parser.add_argument(
        "--theme", default=theme.DEFAULT_THEME, choices=theme.THEME_ORDER,
        help=f"colour theme (default: {theme.DEFAULT_THEME})",
    )
    parser.add_argument(
        "--units", default="imperial", choices=("imperial", "metric"),
        help="feet/knots/Fahrenheit or metres/km-h/Celsius",
    )
    parser.add_argument("--fps", type=int, default=12, help="animation frames per second (1-30)")
    parser.add_argument("--no-color", action="store_true", help="disable colour")
    parser.add_argument(
        "--once", action="store_true",
        help="print one static report and exit (no curses, scriptable)",
    )
    parser.add_argument("--no-scene", action="store_true", help="with --once, skip the ocean art")
    parser.add_argument("--width", type=int, default=0, help="with --once, output width")
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout in seconds")
    parser.add_argument("--version", action="version", version=f"surfdeck {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_spots:
        # Columns size themselves so a long spot name never shunts the bearing.
        key_width = max(len(key) for key in spots.SPOTS)
        name_width = max(len(spot.name) for spot in spots.SPOTS.values())
        for key, spot in spots.SPOTS.items():
            marker = "*" if key == spots.DEFAULT_SPOT else " "
            print(
                f"{marker} {key:<{key_width}}  {spot.name:<{name_width}}  "
                f"faces {spot.facing_deg:.0f}°"
            )
        return 0

    try:
        spot = spots.get_spot(args.spot)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2

    use_color = not args.no_color and os.environ.get("NO_COLOR") is None

    if args.once:
        width = args.width or shutil.get_terminal_size((80, 24)).columns
        report = surf_mod.get_report(spot, timeout=args.timeout)
        sampler = stats_mod.Sampler(top_n=8)
        # psutil needs a short interval between samples for real CPU percentages.
        time.sleep(0.4)
        snapshot = sampler.sample()
        print(
            plain.render(
                report, snapshot, theme_name=args.theme, units=args.units,
                width=max(48, min(width, 200)), color=use_color and sys.stdout.isatty(),
                scene=not args.no_scene,
            ),
            end="",
        )
        return 0 if report.ok else 1

    if not sys.stdout.isatty():
        print(
            "surfdeck needs a terminal; use --once for pipe-friendly output.",
            file=sys.stderr,
        )
        return 2

    from . import ui  # imported late so --once works without a tty

    try:
        ui.run(spot, args.theme, args.units, args.fps, use_color)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
