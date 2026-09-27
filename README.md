# LIFE.py - Python access client for LIFE extinction-risk maps

## Synopsis

```python
from life_metric import BBox, open_store

store = open_store()  # published v1.01 store
print(store.describe())

layer = store.layer("arable", "0.25")
raster = layer.read("all", bbox=BBox(43, -26, 51, -12))  # west, south, east, north
value = layer.value(-19.5, 47.0, "AVES")  # latitude, longitude
```

## Description

LIFE.py reads local or published LIFE Zarr stores through the `life-metric`
Python package and command. LIFE maps the change in expected extinctions when
land use changes. The v1.01 release covers 30,875 species of amphibians,
birds, mammals and reptiles. Its scores are per square kilometre of land
changed: positive values mean more expected extinctions, and negative values
mean fewer. See [the data guide](docs/data.rst) for the scenarios, units,
versions, resolution levels and store layout. The original pipeline for
generating LIFE from source data is [quantifyearth/LIFE](https://github.com/quantifyearth/LIFE).

## Installation

```sh
pip install life-metric
```

Install `life-metric[xarray]` for xarray access or `life-metric[build]` to
convert existing LIFE GeoTIFFs to Zarr. `open_store()` uses the [published
v1.01 store](https://data.source.coop/tessera/life/v1.01) by default, but there
is also a v1.1~beta we are working on. You can also pass a local store path to work offline.

## Documentation and examples

- [Data guide](docs/data.rst): score meaning, versions, overview limits and Zarr layout.
- [Tutorial](docs/tutorial.rst): a walkthrough using the runnable examples.
- [Python API](docs/api.rst): stores, layers, grids, catalogues and colours.
- [CLI guide](docs/cli.rst): queries, downloads and store management.
- [Numbered examples](examples/README.md): short READMEs and scripts for
  opening a store, querying points, reading regions, choosing versions,
  drawing maps and using xarray.

For a quick command-line query:

```sh
life-metric query -19.5 47 --scenario arable --curve 0.25 --json
```

## Terms of use

The data may not be used for commercial or revenue-generating purposes, nor
redistributed in their original form, without written permission from IBAT
(ibat@ibat-alliance.org). The full text is in `store.info.terms_of_use`.

## See also

- Eyres A. et al. 2025, *LIFE: A metric for mapping the impact of land-cover change on global extinctions*, Phil. Trans. R. Soc. B 380:20230327,
<https://doi.org/10.1098/rstb.2023.0327>.
- Data of record: <https://doi.org/10.5281/zenodo.14945383>.
- Published store: <https://source.coop/tessera/life>.
- JavaScript client: <https://github.com/quantifyearth/LIFE.js>.
