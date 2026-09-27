"""Colour one score band and write a PNG map."""

import argparse
from pathlib import Path

from life_metric import BBox, colour, open_store

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bbox", nargs=4, type=float, default=[43, -26, 51, -12], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
parser.add_argument("--output", type=Path, default=Path("region.png"))
args = parser.parse_args()

store = open_store(args.source) if args.source else open_store()
layer = store.layer("restore", "0.25")
raster = layer.read("all", bbox=BBox(*args.bbox))
scale = colour.make_scale(colour.percentile_abs(raster.data, 99))
with args.output.open("wb") as output:
    output.write(colour.to_png(scale.rgba(raster.data)))
print("Wrote", args.output)
