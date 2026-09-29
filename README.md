# LIFE.py

## NAME

life-metric reads LIFE extinction-risk maps into NumPy arrays and GeoTIFFs.

## SYNOPSIS

```python
import numpy as np
from life_metric import read

values, transform = read("arable_0.25", taxon="AVES", bounds=(43, -26, 51, -12))
print(np.nanmean(values))
```

## DESCRIPTION

LIFE.py reads regions and samples points from LIFE Zarr v3 stores. Regional
reads return a NumPy array and an Affine transform in EPSG:4326. Polygon
reads return NumPy masked arrays. The library also opens native xarray
Datasets with a rioxarray accessor.

Scores measure the change in expected extinctions per square kilometre of
land changed. Positive scores mean more extinctions, and negative scores mean
fewer. Missing scores are NaN. Changed-area layers use square metres; zero
scores and zero area are valid data.

## INSTALLATION

```sh
pip install life-metric
```

Python 3.11 or newer is required. Install `life-metric[geo]` for Shapely
polygon masks and GeoTIFF downloads, or `life-metric[xarray]` for xarray
and rioxarray.

## USAGE

Reads use the published v1.01 store by default. Pass `source` to open a local
store or URL. `metadata()` describes its scenarios, curves, taxa, and terms.
`versions()` lists releases, and `version` selects one of them.

`read()` requires bounds, a rasterio pixel window, or a Shapely or GeoJSON
polygon. Bounds use `(west, south, east, north)` in WGS84 degrees.
`sample()` takes `(longitude, latitude)` pairs. Use native resolution for
calculations; coarser levels are intended for display.

The CLI queries points and downloads bounded regions. Its query coordinates
are latitude followed by longitude. Missing scores become JSON `null`.

```sh
life-metric query -19.5 47 --taxon AVES --json
life-metric download region.tif --bbox 43 -26 51 -12 --taxon AVES
```

GeoTIFF downloads retain the CRS, units, citation, and data terms. They
require the `geo` extra and are limited to 16 million values per file.
Run `life-metric --help` for the command list.

## DOCUMENTATION

The [tutorial](https://github.com/quantifyearth/LIFE.py/blob/main/docs/tutorial.rst)
and [numbered examples](https://github.com/quantifyearth/LIFE.py/tree/main/examples)
cover NumPy, polygons, rasterio, point samples, xarray, and colour maps.
The [API reference](https://github.com/quantifyearth/LIFE.py/blob/main/docs/api.rst),
[CLI guide](https://github.com/quantifyearth/LIFE.py/blob/main/docs/cli.rst), and
[data guide](https://github.com/quantifyearth/LIFE.py/blob/main/docs/data.rst)
describe the options and data meanings.

## TERMS OF USE

The code is MIT licensed. The data may not be used for commercial or
revenue-generating purposes, nor redistributed in their original form,
without written permission from IBAT (ibat@ibat-alliance.org).
Read `metadata()["terms_of_reference"]` for the full terms.

## SEE ALSO

The method is described by [Eyres et al. (2025), *LIFE: A metric for mapping the impact of land-cover change on global extinctions*](https://doi.org/10.1098/rstb.2023.0327).
The [data of record](https://doi.org/10.5281/zenodo.14945383) and
[published stores](https://source.coop/tessera/life) are available separately.
See [LIFE.js](https://github.com/quantifyearth/LIFE.js) for the JavaScript client
and [quantifyearth/LIFE](https://github.com/quantifyearth/LIFE) to regenerate
LIFE from source data.
