"""Sample conversion and restoration scores at longitude-latitude points."""

import sys

from life_metric import sample

places = {
    "Madagascar highlands": (47.0, -19.5),
    "Cameroon highlands": (10.2, 5.6),
    "Borneo interior": (114.0, 1.5),
}
source = sys.argv[1] if len(sys.argv) > 1 else None
xy = list(places.values())
arable = sample("arable_0.25", xy, source=source)
restore = sample("restore_0.25", xy, source=source)
print(f"{'place':22s} {'convert':>12s} {'restore':>12s}")
for name, conversion, restoration in zip(places, arable, restore):
    print(f"{name:22s} {conversion:12.3e} {restoration:12.3e}")
