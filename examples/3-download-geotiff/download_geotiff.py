"""Download a region as GeoTIFF and open it with rasterio."""

import argparse
from pathlib import Path

import rasterio

from life_metric import download

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bounds", nargs=4, type=float, default=[43, -26, 51, -12], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
parser.add_argument("--output", type=Path, default=Path("region.tif"))
parser.add_argument("--overwrite", action="store_true")
args = parser.parse_args()

path = download("restore_0.25", args.output, source=args.source,
                bounds=args.bounds, overwrite=args.overwrite)
with rasterio.open(path) as dataset:
    values = dataset.read(1, masked=True)
    print("CRS:", dataset.crs)
    print("Bounds:", dataset.bounds)
    print("Mean score:", values.mean(), dataset.units[0])
    print("Terms:", dataset.tags().get("terms_of_use"))
print("Saved", path)
