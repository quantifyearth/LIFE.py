"""Select a region with xarray and calculate means for named taxa."""

import argparse

from life_metric import open_dataset

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bounds", nargs=4, type=float, default=[33.9, -4.7, 41.9, 5.5], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
parser.add_argument("--level", type=int, default=4, help="overview reduction factor")
args = parser.parse_args()

west, south, east, north = args.bounds
with open_dataset(args.source, level=args.level) as dataset:
    region = dataset["arable_0.25"].sel(lat=slice(north, south), lon=slice(west, east))
    print("Region at level", args.level, dict(region.sizes))
    print("CRS:", region.rio.crs)
    means = region.mean(dim=("lat", "lon"), skipna=True)
    for taxon, value in zip(means["taxon"].values, means.to_numpy()):
        print(f"{taxon:10s} mean {value:.3e} {region.attrs['units']}")
