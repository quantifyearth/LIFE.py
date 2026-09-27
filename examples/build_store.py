"""Convert the published v1.01 GeoTIFFs to a Zarr store and verify it.

Needs the build extra (rasterio) and about 13 GB of disk.
Run from the repository root: uv run --extra build examples/build_store.py DATA_DIR [--workers N]
Generate the original LIFE maps with https://github.com/quantifyearth/LIFE.
"""

import argparse
from pathlib import Path

from life_metric import dataset
from life_metric.build import (Options, build_pyramid, convert_layers, create_pyramid, create_store,
                               download, extract, finalize, verify_layers, write_manifest)

ap = argparse.ArgumentParser()
ap.add_argument("data_dir", type=Path)
ap.add_argument("--workers", type=int, default=8)
args = ap.parse_args()

raw = args.data_dir / "raw"
store = dataset.store_path(args.data_dir)               # <data_dir>/v1.01
zip_path = download(raw)                                 # resumable, md5-checked
extract(zip_path, raw)

opts = Options(workers=args.workers)
layers = list(dataset.LAYERS)
create_store(store, opts, layers, overwrite=True, zip_md5=dataset.ZIP_MD5)
convert_layers(store, raw, layers, opts)
create_pyramid(store, opts, layers)
build_pyramid(store, layers, workers=args.workers)
finalize(store)

results = verify_layers(store, raw, layers, workers=args.workers, gdal=False)
assert all(r.ok for r in results), [r.name for r in results if not r.ok]
write_manifest(args.data_dir, store, released="2024-12-19")
print("built and verified", store)
