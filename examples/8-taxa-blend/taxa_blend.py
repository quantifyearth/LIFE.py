"""Blend the four class bands from a NumPy score stack."""

import argparse
from pathlib import Path

from life_metric import colour, read

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bounds", nargs=4, type=float, default=[90, -12, 130, 25], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
parser.add_argument("--level", type=int, default=4, help="overview reduction factor")
parser.add_argument("--output", type=Path, default=Path("taxa.png"))
args = parser.parse_args()

values, _ = read("arable_0.25", source=args.source, bounds=args.bounds, taxon=None, level=args.level)
stack = values[1:]  # omit the all-species band
blend = colour.make_blend([colour.percentile_abs(band, 99) for band in stack])
args.output.write_bytes(colour.to_png(blend.rgba(stack)))
for name, rgb in blend.swatches.items():
    print(f"{name:10s} rgb{rgb}")
print("wrote", args.output)
