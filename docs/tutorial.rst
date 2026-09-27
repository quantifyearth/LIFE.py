Tutorial
========

Install ``life-metric`` and run the numbered examples from the repository
root. Each script accepts a local store or uses the published v1.01 store.
The same sequence, with a short README for each step, is in ``examples/``.

1. Open a store
---------------

Inspect the store's own scenarios, curves, taxa, levels, and layer metadata
before choosing an array. This does not read raster pixels.

.. literalinclude:: ../examples/1-open-store/open_store.py
   :language: python
   :start-at: import sys

Run ``uv run python examples/1-open-store/open_store.py /path/to/v1.01``.

2. Query a point
----------------

``Layer.value()`` takes latitude first and longitude second. The example
reads a score and its matching changed area. A score is the change in
expected extinctions per square kilometre changed. The area is in square
metres. Missing scores are NaN.

.. literalinclude:: ../examples/2-query-point/query_point.py
   :language: python
   :start-at: import sys

Run ``uv run python examples/2-query-point/query_point.py /path/to/v1.01 -19.5 47``.

3. Sample points
----------------

``Layer.sample()`` reads several matching latitude and longitude pairs in
one call per layer. The example compares the two v1.01 scenarios.

.. literalinclude:: ../examples/3-sample-points/sample_points.py
   :language: python
   :start-at: import sys

Run ``uv run python examples/3-sample-points/sample_points.py /path/to/v1.01``.

.. _read-region:

4. Read a region
----------------

``BBox`` takes west, south, east, and north edges. The returned ``Raster``
holds both pixels and their grid. A bounded read avoids loading the globe.

.. literalinclude:: ../examples/4-read-region/read_region.py
   :language: python
   :start-at: import argparse

Run ``uv run python examples/4-read-region/read_region.py /path/to/v1.01``.

.. _choose-version:

5. Choose a version
-------------------

``Catalogue`` lists releases and opens a named version. The v1.1 beta has
different scenarios and float64 arrays, so inspect its metadata before
selecting a layer.

.. literalinclude:: ../examples/5-choose-version/choose_version.py
   :language: python
   :start-at: import argparse

Run ``uv run python examples/5-choose-version/choose_version.py /path/to/catalogue``.

.. _colour-map:

6. Colour a map
---------------

Map one score band to RGBA, then write a PNG. Red means more expected
extinctions and blue means fewer.

.. literalinclude:: ../examples/6-colour-map/colour_map.py
   :language: python
   :start-at: import argparse

Run ``uv run python examples/6-colour-map/colour_map.py /path/to/v1.01``.

.. _blend-taxa:

7. Blend taxa
-------------

Read all score bands at an overview level and blend the four class bands.
The first band, ``all``, is left out of the blend.

.. literalinclude:: ../examples/7-taxa-blend/taxa_blend.py
   :language: python
   :start-at: import argparse

Run ``uv run python examples/7-taxa-blend/taxa_blend.py /path/to/v1.01``.

8. Use xarray
-------------

With ``life-metric[xarray]`` installed, ``Store.to_xarray()`` opens an
overview lazily with named taxa. Overview averages are for display and
exploration; use level 1 for pixel totals.

.. literalinclude:: ../examples/8-xarray-levels/xarray_levels.py
   :language: python
   :start-at: import argparse

Run ``uv run --extra xarray python examples/8-xarray-levels/xarray_levels.py /path/to/v1.01``.

The methods and layer meanings follow `Eyres et al. (2025)
<https://doi.org/10.1098/rstb.2023.0327>`_. Check
``store.info.terms_of_use`` before using the data.
