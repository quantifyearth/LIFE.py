# Examples

Install the package with `uv sync` from the repository root. Run each example
with `uv run python examples/<step>/<script>.py`. Without a store argument,
the reader examples open the published v1.01 store. Pass a local Zarr store
path to work offline.

Each step builds on the previous one:

1. [Open a store](1-open-store/README.md) and inspect its descriptions.
2. [Query a point](2-query-point/README.md) for one score and changed area.
3. [Sample points](3-sample-points/README.md) in one read per layer.
4. [Read a region](4-read-region/README.md) with its pixel grid.
5. [Choose a version](5-choose-version/README.md) from a catalogue.
6. [Colour a map](6-colour-map/README.md) and write a PNG.
7. [Blend taxa](7-taxa-blend/README.md) into one map.
8. [Use xarray](8-xarray-levels/README.md) to explore an overview lazily.

The separate [`cli.sh`](cli.sh) shows the query and download commands.
Store maintainers can use [`build_store.py`](build_store.py) for existing
v1.01 GeoTIFFs or [`build_beta_store.py`](build_beta_store.py) for the beta.
The pipeline that generates LIFE maps from source data is
[quantifyearth/LIFE](https://github.com/quantifyearth/LIFE).
