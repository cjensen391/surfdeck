"""Surf spot registry.

`facing_deg` is the compass bearing the beach looks out toward. It is what
makes the offshore / onshore wind call possible: South Beach faces roughly
east, so a wind out of the west is offshore (clean) and a wind out of the
east is onshore (mush).

Spots are listed south to north so that cycling with `s` in the dashboard
walks up the Florida east coast the way you would drive it.
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
    # Handy neighbours for when South Beach is a lake, then onward up the coast.
    "41st-street": Spot(
        key="41st-street",
        name="41st Street, Miami FL",
        latitude=25.8148,
        longitude=-80.1213,
        facing_deg=95.0,
        timezone="America/New_York",
    ),
    "haulover": Spot(
        key="haulover",
        name="Haulover Inlet, FL",
        latitude=25.9079,
        longitude=-80.1220,
        facing_deg=100.0,
        timezone="America/New_York",
    ),
    "dania-beach": Spot(
        key="dania-beach",
        name="Dania Beach Pier, FL",
        latitude=26.0575,
        longitude=-80.1097,
        facing_deg=100.0,
        timezone="America/New_York",
    ),
    "deerfield-beach": Spot(
        key="deerfield-beach",
        name="Deerfield Beach, FL",
        latitude=26.3186,
        longitude=-80.0724,
        facing_deg=95.0,
        timezone="America/New_York",
    ),
    "boca-raton": Spot(
        key="boca-raton",
        name="Boca Raton Inlet, FL",
        latitude=26.3355,
        longitude=-80.0714,
        facing_deg=95.0,
        timezone="America/New_York",
    ),
    "reef-road": Spot(
        key="reef-road",
        name="Reef Road, Palm Beach FL",
        latitude=26.6839,
        longitude=-80.0340,
        facing_deg=100.0,
        timezone="America/New_York",
    ),
    "jupiter-inlet": Spot(
        key="jupiter-inlet",
        name="Jupiter Inlet, FL",
        latitude=26.9385,
        longitude=-80.0716,
        facing_deg=90.0,
        timezone="America/New_York",
    ),
    "fort-pierce-inlet": Spot(
        key="fort-pierce-inlet",
        name="Fort Pierce Inlet, FL",
        latitude=27.4728,
        longitude=-80.2930,
        facing_deg=90.0,
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
    "cocoa-beach": Spot(
        key="cocoa-beach",
        name="Cocoa Beach Pier, FL",
        latitude=28.3662,
        longitude=-80.6009,
        facing_deg=95.0,
        timezone="America/New_York",
    ),
    "new-smyrna": Spot(
        key="new-smyrna",
        name="New Smyrna Beach, FL",
        latitude=29.0619,
        longitude=-80.9126,
        facing_deg=100.0,
        timezone="America/New_York",
    ),
    "jacksonville-beach": Spot(
        key="jacksonville-beach",
        name="Jacksonville Beach, FL",
        latitude=30.2877,
        longitude=-81.3880,
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
