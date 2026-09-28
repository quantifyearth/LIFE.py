"""Calculate a regional LIFE statistic with NumPy."""

import argparse

import numpy as np

from life_metric import read

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bounds", nargs=4, type=float, default=[43, -26, 51, -12], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
args = parser.parse_args()

values, transform = read("restore_0.25", source=args.source, bounds=args.bounds)
print(f"{values.shape[1]} x {values.shape[0]} pixels, dtype {values.dtype}")
print("Transform:", transform)
if np.isfinite(values).any():
    print("Mean score:", np.nanmean(values), "extinctions per km² changed")
