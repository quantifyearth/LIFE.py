"""Paint the four species groups together at an overview level."""

import argparse
from pathlib import Path

from life_metric import BBox, colour, open_store

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bbox", nargs=4, type=float, default=[90, -12, 130, 25], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
parser.add_argument("--level", type=int, default=4, help="overview reduction factor")
parser.add_argument("--output", type=Path, default=Path("taxa.png"))
args = parser.parse_args()

store = open_store(args.source) if args.source else open_store()
layer = store.layer("arable", "0.25")
raster = layer.read(None, bbox=BBox(*args.bbox), level=args.level)
stack = raster.data[1:]                                            # the four class bands
blend = colour.make_blend([colour.percentile_abs(b, 99) for b in stack], direction=+1)
with args.output.open("wb") as f:
    f.write(colour.to_png(blend.rgba(stack)))
for name, rgb in blend.swatches.items():
    print(f"{name:10s} rgb{rgb}")
print("all four together:", blend.black)
print("wrote", args.output)
