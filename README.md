# surfdeck

    ████ █  █ ████ ████ ███  ████ ████ █  █
    █    █  █ █  █ █    █  █ █    █    █ █
    ████ █  █ ████ ███  █  █ ███  █    ██
       █ █  █ █ █  █    █  █ █    █    █ █
    ████ ████ █  █ █    ███  ████ ████ █  █

A terminal surf report for **South Beach, Miami Beach FL** with everything you'd
read off `htop`, wrapped in an animated pirate ocean. One command, one screen:
is it worth paddling out, and is the box on fire?

Runs on Linux and macOS. Python 3.10+, ncurses from the standard library,
`psutil` for the system side. No API key — surf data comes from the free
[Open-Meteo](https://open-meteo.com) marine and forecast APIs.

```
 SOUTH BEACH, FL  2026-09-27 13:00  ⚑ live      │ SHIP'S SYSTEMS  jerrycan   up 1d 01:01:01   load 1.00 0.50 0.40
   SCORE ██████░░░░  6/10                       │    0 [|||||||||                              12.0%]
   SHOULDER HIGH PLUS - all hands on deck       │    1 [|||||||||||||||||||||||||              44.0%]
                                                │    2 [|||||||||||||||||||||||||||||||||||||||98.0%]
   WAVE    4.2 ft @ 11.5s  from E 80°  ←        │    3 [||                                      3.0%]
   SWELL   3.9 ft @ 12.5s  from ENE 75°  ←      │   MEM [|||||||||||||||||||||       37.5%] 3.0G/8.0G
   WIND    9.0 kn G 14.0 kn  from W 275°  →  OFFSHORE   SWP [                         0.0%] 0B/2.0G
   TEMP  water 77°F   air 82°F                  │   TASKS 204 (811 thr, 2 run)   NET ↑2.0K/s ↓10.0K/s
   SUN   rise 07:11   set 19:11                 │   DISK r 0B/s  w 4.0K/s   CLK 2.40GHz
   TREND ▁▂▃▄▅▆▆▇███  wave height, next 12h     │   TEMP cpu_thermal 59.5°C
                                                │     PID USER      CPU%  MEM%     TIME+  COMMAND
      \|/ /                                     │    1234 cjensen   12.5   3.2   1:05.50  python3 -m surfdeck
     --*--     wax up, ye sea dog               │
                    ☠─
                    |    |    |
                   )_)  )_)  )_)          \o/
                  )___))___))___)\         |
      ≈≈~      _____|____|____|____\\\__ __|__        ~~≈
 ~≈≈≈≈~~~~░░░≈≈≈~~~~≈≈≈≈~~~~≈≈≈≈~~~~≈≈≈≈~~~~░░░≈≈≈~~~~≈≈≈≈~~~~
 ░░░░░░░░░▒▒▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒░░░░░░░░░░░░░░
 q:quit  r:refresh  t:pirate  s:south-beach  u:imperial  ?:keys              12fps
```

## Install

```bash
git clone <this repo> surfdeck && cd surfdeck

# Option 1: pipx (puts `surfdeck` on your PATH)
pipx install .

# Option 2: a plain venv
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/surfdeck

# Option 3: no install at all, if you already have psutil
python3 -m surfdeck
```

macOS: `brew install python` gets you a Python with working ncurses; nothing
else is needed. Linux: `psutil` may already be packaged as `python3-psutil`.

## Use

```bash
surfdeck                        # the live dashboard (South Beach)
surfdeck --theme hacker         # green-on-black instead of gold-and-blood
surfdeck --units metric         # metres, km/h, Celsius
surfdeck --spot 41st-street     # another spot, south to north up the coast
surfdeck --list-spots           # South Beach through Jacksonville Beach
surfdeck --once                 # one static report, pipe/MOTD friendly
surfdeck --once --no-color --no-scene | mail -s "surf" me@example.com
```

### Keys

| key | does |
| --- | --- |
| `q` / `Esc` | quit |
| `r` | re-read the buoys now (otherwise every 10 min) |
| `t` | cycle theme: pirate → hacker → tropical |
| `s` | next spot |
| `u` | imperial ↔ metric |
| `space` | freeze the animation |
| `+` / `-` | animation speed |
| `?` | key help |

## What the surf panel means

- **WAVE** — combined sea state: height, period, and the direction it comes
  *from*. The arrow points the way the energy is travelling.
- **SWELL** — the groundswell component alone. Its **period** is the number that
  separates a real swell from local wind slop: under ~7s is chop, 10s+ has
  travelled and will stand up on the sandbar.
- **WIND** — speed, gusts, direction, and whether that direction is `OFFSHORE`
  (grooms the face), `ONSHORE` (mush) or `CROSS-SHORE`, computed from the
  beach's own orientation (South Beach looks out at ~95°).
- **SCORE** — 0-10, from size (up to 6 points), period (up to 3) and a wind
  bonus or penalty. `surfdeck.surf.raw_score` has the exact arithmetic; it is
  opinionated on purpose.
- **TREND** — hourly wave height for the next 12 hours, so you can see whether
  it's building or dying.

The animation reads the same numbers: wave amplitude tracks the real swell
height, wavelength tracks the period, chop and whitecaps track the wind, and
the surfer only paddles out once the score says it's rideable.

Conditions are cached to `~/.cache/surfdeck/<spot>.json`. With no network the
last known report is shown, flagged `STALE CHART`.

## The system panel

Per-core CPU meters, memory and swap, load average against core count, uptime,
task/thread counts, network and disk I/O rates, mount usage, sensor
temperatures where the platform exposes them, and the top processes by CPU with
htop's `TIME+` column. Layout adapts: meters go multi-column on wide terminals,
panels stack on narrow ones, and the banner and ocean drop out on short ones.

## Layout of the code

| file | job |
| --- | --- |
| `surfdeck/surf.py` | fetch + parse Open-Meteo, score, cache |
| `surfdeck/stats.py` | psutil sampling, htop-style formatting |
| `surfdeck/spots.py` | spot registry, incl. which way each beach faces |
| `surfdeck/animation.py` | canvas compositing, ocean scene, rain, meters, ticker |
| `surfdeck/art.py` | ASCII sprites and the block font |
| `surfdeck/theme.py` | themes, 256/8-colour fallback, curses pair allocation |
| `surfdeck/format.py` | the two panels, as (text, colour-key) rows |
| `surfdeck/ui.py` | curses dashboard: layout, keys, background fetch thread |
| `surfdeck/plain.py` | the same panels as ANSI text for `--once` |

Fetching, frame generation and layout are pure functions of their inputs, so
the whole thing is testable without a terminal or a socket:

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

## Adding a spot

Add an entry to `SPOTS` in `surfdeck/spots.py` with its latitude, longitude,
timezone, and `facing_deg` — the compass bearing the beach looks out toward.
That bearing is what makes the offshore/onshore call correct.

## License

MIT — see [LICENSE](LICENSE). Open source: use it, fork it, sell it, just keep
the copyright notice aboard.
