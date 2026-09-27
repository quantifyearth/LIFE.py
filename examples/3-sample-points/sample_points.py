"""Sample the two published v1.01 scenarios at several points."""

import sys

from life_metric import open_store

# Rural places: under conversion a town or existing cropland holds NaN, since nothing there would change.
PLACES = {
    "Madagascar highlands": (-19.5, 47.0), "Cameroon highlands": (5.6, 10.2), "Borneo interior": (1.5, 114.0),
    "Ethiopian highlands": (9.0, 39.0), "Atlantic Forest": (-22.4, -44.6), "English fens": (52.45, 0.15),
}
store = open_store(*sys.argv[1:2])
arable, restore = store.layer("arable", "0.25"), store.layer("restore", "0.25")
lats = [p[0] for p in PLACES.values()]
lons = [p[1] for p in PLACES.values()]
a = arable.sample(lats, lons)
r = restore.sample(lats, lons)
print(f"{'place':22s} {'convert':>12s} {'restore':>12s}   ({arable.units}; NaN = nothing changes there)")
for name, x, y in zip(PLACES, a, r):
    print(f"{name:22s} {x:12.3e} {y:12.3e}")
