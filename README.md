# LIFE.py - Python access client for LIFE extinction-risk maps

## Synopsis

```python
import numpy as np
from life_metric import read

values, transform = read("arable_0.25", taxon="AVES", bounds=(43, -26, 51, -12))
print(np.nanmean(values))
```

## Description

LIFE.py reads regional LIFE data into NumPy arrays, GeoTIFFs, and native
xarray datasets. Bounds use west, south, east, north. Regional reads return
an array and an `affine.Affine` transform in EPSG:4326. You can use NumPy,
rasterio, Shapely, and xarray without learning a separate raster model.
The library selects dataset versions and reads the requested Zarr pixels.

LIFE maps the change in expected extinctions when land use changes. Scores
are per square kilometre of land changed: positive values mean more expected
extinctions, and negative values mean fewer. Changed area is in square metres;
zero area is valid data. See the [data guide](docs/data.rst) for scenarios,
units, versions, and overview limits. The source pipeline is
[quantifyearth/LIFE](https://github.com/quantifyearth/LIFE).

## Installation

```sh
pip install life-metric
pip install 'life-metric[geo]'     # polygon masking and GeoTIFF export
pip install 'life-metric[xarray]'  # xarray datasets with a rio accessor
```

Reads use the [published v1.01 store](https://data.source.coop/tessera/life/v1.01)
by default. Pass `source="/path/to/v1.01"` for a local store, or
`version="1.1~beta1"` for the beta. `metadata()` returns dataset descriptions
and data terms as a dictionary; `versions()` lists release dictionaries.

## Geospatial workflows

With the `geo` extra installed, pass Shapely or GeoJSON polygons to `read()`.
The result is a NumPy masked array. Geometry coordinates use the supplied
CRS; the returned raster remains in EPSG:4326.

```python
from shapely.geometry import box
from life_metric import read

values, transform = read("arable_0.25", geometry=box(43, -26, 51, -12), crs="EPSG:4326")
print(values.mean())
```

Save a region as a GeoTIFF for an existing rasterio workflow:

```sh
life-metric download region.tif --bbox 43 -26 51 -12 --taxon AVES
```

With the `xarray` extra, use native selection and analysis:

```python
from life_metric import open_dataset

with open_dataset(version="1.1~beta1") as dataset:
    birds = dataset["arable_0.25"].sel(taxon="AVES")
    region = birds.sel(lon=slice(43, 51), lat=slice(-12, -26))
    print(region.to_numpy(), region.rio.crs)
```

`sample()` takes `(longitude, latitude)` point pairs and returns NumPy
values. The CLI's `query` command takes latitude then longitude:

```sh
life-metric query -19.5 47 --scenario arable --curve 0.25 --json
```

## Documentation and examples

- [Data guide](docs/data.rst) explains score meaning, versions, and Zarr layout.
- [Tutorial](docs/tutorial.rst) follows the runnable examples.
- [Python API](docs/api.rst) documents reads, samples, datasets, and downloads.
- [CLI guide](docs/cli.rst) describes queries, downloads, and store maintenance.
- [Numbered examples](examples/README.md) start with NumPy statistics, polygon
  masks, and rasterio, then cover versions, xarray, and colour maps.

Store maintainers can install `life-metric[build]` and use the
`life-metric admin` commands to convert existing GeoTIFFs to Zarr.

## Terms of use

The data may not be used for commercial or revenue-generating purposes, nor
redistributed in their original form, without written permission from IBAT
(ibat@ibat-alliance.org). Read `metadata()["terms_of_reference"]` for the
full terms. GeoTIFF downloads include them in the file's metadata.

## See also

- Eyres A. et al. 2025, *LIFE: A metric for mapping the impact of land-cover change on global extinctions*, Phil. Trans. R. Soc. B 380:20230327,
  <https://doi.org/10.1098/rstb.2023.0327>.
- Data of record: <https://doi.org/10.5281/zenodo.14945383>.
- Published store: <https://source.coop/tessera/life>.
- JavaScript client: <https://github.com/quantifyearth/LIFE.js>.
