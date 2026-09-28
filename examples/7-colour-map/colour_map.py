"""Colour a NumPy score array and write a PNG map."""

import argparse
from pathlib import Path

from life_metric import colour, read

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bounds", nargs=4, type=float, default=[43, -26, 51, -12], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
parser.add_argument("--output", type=Path, default=Path("region.png"))
args = parser.parse_args()

values, _ = read("restore_0.25", source=args.source, bounds=args.bounds)
scale = colour.make_scale(colour.percentile_abs(values, 99))
args.output.write_bytes(colour.to_png(scale.rgba(values)))
print("Wrote", args.output)
