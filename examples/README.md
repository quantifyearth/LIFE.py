# Examples

Clone the repository and install the example dependencies.

```sh
git clone https://github.com/quantifyearth/LIFE.py.git
cd LIFE.py
uv sync
```

Run the examples from the repository root, following the numbered steps.
Each example has a short README and a runnable script. Pass a local Zarr
store to work offline. Without a source, reads use the published v1.01 store.

1. [Read a region with NumPy](1-read-region/README.md).
2. [Mask a polygon](2-mask-polygon/README.md).
3. [Download a GeoTIFF](3-download-geotiff/README.md).
4. [Sample points](4-sample-points/README.md).
5. [Choose a version](5-choose-version/README.md).
6. [Use xarray](6-xarray/README.md).
7. [Colour a map](7-colour-map/README.md).
8. [Blend taxa](8-taxa-blend/README.md).

The scripts are exercised against a small local store by the test suite.
Polygon masks and GeoTIFF downloads use `life-metric[geo]`. Native xarray
access uses `life-metric[xarray]`. The separate [`cli.sh`](cli.sh) demonstrates
point queries and GeoTIFF downloads.

Store maintainers can convert existing GeoTIFFs with [`build_store.py`](build_store.py)
or [`build_beta_store.py`](build_beta_store.py). The original LIFE source
pipeline is [quantifyearth/LIFE](https://github.com/quantifyearth/LIFE).
