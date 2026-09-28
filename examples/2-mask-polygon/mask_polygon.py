"""Mask a Shapely polygon and calculate its mean score."""

import argparse

from shapely.geometry import Polygon

from life_metric import read

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bounds", nargs=4, type=float, default=[43, -26, 51, -12], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
args = parser.parse_args()

west, south, east, north = args.bounds
polygon = Polygon([(west, south), (east, south), ((west + east) / 2, north)])
values, transform = read("arable_0.25", source=args.source, geometry=polygon, crs="EPSG:4326")
print("Included pixels:", values.count())
print("Mean score:", values.mean(), "extinctions per km² changed")
print("Transform:", transform)
