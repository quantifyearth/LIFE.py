"""Open an overview lazily with xarray and average a bounded region."""

import argparse

from life_metric import open_store

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", nargs="?", help="store directory or URL; default: published v1.01")
parser.add_argument("--bbox", nargs=4, type=float, default=[33.9, -4.7, 41.9, 5.5], metavar=("WEST", "SOUTH", "EAST", "NORTH"))
parser.add_argument("--level", type=int, default=4, help="overview reduction factor")
args = parser.parse_args()

store = open_store(args.source) if args.source else open_store()
ds = store.to_xarray(level=args.level)
west, south, east, north = args.bbox
region = ds["arable_0.25"].sel(lat=slice(north, south), lon=slice(west, east))
print("Region at level", args.level, dict(region.sizes))
means = region.mean(dim=("lat", "lon"), skipna=True).compute()
for taxon, value in zip(means["taxon"].values, means.values):
    print(f"{taxon:10s} mean {value:.3e} {ds['arable_0.25'].attrs.get('units', '')}")
