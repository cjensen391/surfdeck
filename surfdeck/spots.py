"""Surf spot registry.

`facing_deg` is the compass bearing the beach looks out toward. It is what
makes the offshore / onshore wind call possible: South Beach faces roughly
east, so a wind out of the west is offshore (clean) and a wind out of the
east is onshore (mush).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Spot:
    key: str
    name: str
    latitude: float
    longitude: float
    facing_deg: float
    timezone: str

    @property
    def label(self) -> str:
        return self.name.upper()


SPOTS: dict[str, Spot] = {
    "south-beach": Spot(
        key="south-beach",
        name="South Beach, FL",
        latitude=25.7826,
        longitude=-80.1341,
        facing_deg=95.0,
        timezone="America/New_York",
    ),
    # Handy neighbors for when South Beach is a lake.
    "haulover": Spot(
        key="haulover",
        name="Haulover Inlet, FL",
        latitude=25.9079,
        longitude=-80.1220,
        facing_deg=100.0,
        timezone="America/New_York",
    ),
    "sebastian-inlet": Spot(
        key="sebastian-inlet",
        name="Sebastian Inlet, FL",
        latitude=27.8608,
        longitude=-80.4470,
        facing_deg=95.0,
        timezone="America/New_York",
    ),
}

DEFAULT_SPOT = "south-beach"


def get_spot(key: str) -> Spot:
    try:
        return SPOTS[key]
    except KeyError:
        raise KeyError(
            f"unknown spot {key!r}; known spots: {', '.join(sorted(SPOTS))}"
        ) from None
