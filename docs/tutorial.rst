Tutorial
========

Install ``life-metric`` and run the examples from the repository root.
Each script accepts a local Zarr store, or uses the published v1.01 store.
Install ``life-metric[geo]`` for polygon masks and GeoTIFF export, and
``life-metric[xarray]`` for xarray and rioxarray. In a checkout, ``uv sync``
installs the dependencies needed by the examples.

.. _read-region:

1. Read a region with NumPy
---------------------------

``read()`` returns a NumPy array and an Affine transform in EPSG:4326.
Bounds are west, south, east, north. Pixels that intersect the bounds are
included. Use NumPy to calculate statistics directly; missing scores are NaN.
The returned transform describes the actual pixel edges.

.. literalinclude:: ../examples/1-read-region/read_region.py
   :language: python
   :start-at: import argparse

Run ``uv run python examples/1-read-region/read_region.py /path/to/v1.01``.

2. Mask a polygon
-----------------

Pass a Shapely polygon, GeoJSON geometry, or GeoPandas geometry column to
``read()``. Supply its CRS with ``crs``. The function crops to the polygon bounds
and returns a NumPy masked array. Pixel centres determine inclusion by default;
``all_touched=True`` includes any touched pixel. The returned raster remains in
EPSG:4326. Install ``life-metric[geo]`` for this step.

.. literalinclude:: ../examples/2-mask-polygon/mask_polygon.py
   :language: python
   :start-at: import argparse

Run ``uv run --extra geo python examples/2-mask-polygon/mask_polygon.py /path/to/v1.01``.

3. Download a GeoTIFF
---------------------

``download()`` saves a bounded GeoTIFF with the values, CRS, transform, units,
band labels, citation, and data terms. Open the file with rasterio and use
your usual workflow. Install ``life-metric[geo]`` for this step. The example
refuses to replace an existing output unless ``--overwrite`` is given.

.. literalinclude:: ../examples/3-download-geotiff/download_geotiff.py
   :language: python
   :start-at: import argparse

Run ``uv run --extra geo python examples/3-download-geotiff/download_geotiff.py /path/to/v1.01 --output region.tif``.

4. Sample points
----------------

``sample()`` takes longitude-latitude pairs in EPSG:4326, as rasterio does,
and returns a NumPy array. The example compares arable conversion and
restoration. NaN means no score is available at that point.

.. literalinclude:: ../examples/4-sample-points/sample_points.py
   :language: python
   :start-at: import sys

Run ``uv run python examples/4-sample-points/sample_points.py /path/to/v1.01``.

.. _choose-version:

5. Choose a version
-------------------

``versions()`` returns dictionaries for the releases in a catalogue.
``metadata()`` reads the selected store's attributes without reading pixels.
Inspect its scenario and curve descriptions before selecting a layer; the
v1.1 beta differs from v1.01.

.. literalinclude:: ../examples/5-choose-version/choose_version.py
   :language: python
   :start-at: import argparse

Run ``uv run python examples/5-choose-version/choose_version.py /path/to/catalogue --version 1.1~beta1``.

6. Use xarray
-------------

``open_dataset()`` returns a native xarray Dataset with named taxa, dataset
attributes, and CRS metadata for its ``.rio`` accessor. Use ``.sel()`` and NumPy
conversion as usual. Latitude coordinates decrease from north to south.
Install ``life-metric[xarray]`` for this step. Overview means are for exploration;
use level 1 for pixel totals.

.. literalinclude:: ../examples/6-xarray/xarray_example.py
   :language: python
   :start-at: import argparse

Run ``uv run --extra xarray python examples/6-xarray/xarray_example.py /path/to/v1.01``.

.. _colour-map:

7. Colour a map
---------------

The colour functions accept NumPy arrays. Red means more expected
extinctions and blue means fewer. Set the colour range from the 99th percentile
so a few large values do not dominate the image.

.. literalinclude:: ../examples/7-colour-map/colour_map.py
   :language: python
   :start-at: import argparse

Run ``uv run python examples/7-colour-map/colour_map.py /path/to/v1.01 --output region.png``.

.. _blend-taxa:

8. Blend taxa
-------------

Set ``taxon=None`` to read every score band into a NumPy stack. The first band
is ``all``, followed by amphibians, birds, mammals, and reptiles. Omit ``all``
from the blend and give each class its own colour range. The map shows the
strongest class and darkens places where classes are similarly affected.

.. literalinclude:: ../examples/8-taxa-blend/taxa_blend.py
   :language: python
   :start-at: import argparse

Run ``uv run python examples/8-taxa-blend/taxa_blend.py /path/to/v1.01 --output taxa.png``.

Polygon masks use `rasterio's geometry rules
<https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html>`_. The
methods and layer meanings follow `Eyres et al. (2025)
<https://doi.org/10.1098/rstb.2023.0327>`_. Read ``metadata()["terms_of_reference"]``
before using the data.
