"""Read a bounded score raster and inspect its grid and values."""

import argparse

import numpy as np

from life_metric import BBox, open_store

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bbox", nargs=4, type=float, default=[43, -26, 51, -12], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
args = parser.parse_args()

box = BBox(*args.bbox)
store = open_store(args.source) if args.source else open_store()
layer = store.layer("restore", "0.25")
raster = layer.read("all", bbox=box)
valid = np.isfinite(raster.data)
print(layer.summary)
print("bounds:", raster.grid.bounds)
print(f"{raster.data.shape[1]} x {raster.data.shape[0]} pixels, {valid.sum():,} with data")
if valid.any():
    print(f"min {np.nanmin(raster.data):.3g}, max {np.nanmax(raster.data):.3g}, "
          f"mean {np.nanmean(raster.data):.3g} {layer.units}")
