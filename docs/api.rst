Python API
==========

Data access
-----------

Regional reads return a NumPy array and ``affine.Affine`` transform, as in
rasterio's masking functions. Point samples return a NumPy array. Coordinates
are EPSG:4326; bounds use west, south, east, north, and point pairs use
longitude, latitude. ``open_dataset`` returns a native xarray Dataset with
named taxa and a rioxarray accessor.

.. autofunction:: life_metric.read

.. autofunction:: life_metric.sample

.. autofunction:: life_metric.open_dataset

GeoTIFF download
----------------

.. autofunction:: life_metric.download

Dataset descriptions and releases
---------------------------------

.. autofunction:: life_metric.metadata

.. autofunction:: life_metric.versions

Colour
------

These functions accept ordinary NumPy arrays.

.. autofunction:: life_metric.colour.make_scale

.. autoclass:: life_metric.colour.Scale
   :members:

.. autofunction:: life_metric.colour.make_blend

.. autoclass:: life_metric.colour.Blend
   :members:

.. autofunction:: life_metric.colour.percentile_abs

.. autofunction:: life_metric.colour.to_png
