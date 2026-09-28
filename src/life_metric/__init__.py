"""Read LIFE maps into NumPy arrays, GeoTIFFs, and xarray datasets.

Use :func:`read` for a regional NumPy array and Affine transform,
:func:`sample` for longitude-latitude point pairs, and :func:`open_dataset`
for a native xarray Dataset. :func:`metadata` describes the data and
:func:`versions` lists available releases. :func:`download` saves a bounded
GeoTIFF for use with rasterio. All readers use the store's own descriptions.

The ``life-metric`` command queries and downloads data. Its ``admin``
commands convert existing GeoTIFFs using :mod:`life_metric.build`.
"""

from . import colour
from ._access import metadata, open_dataset, read, sample, versions
from ._catalogue import DEFAULT_CATALOGUE
from ._export import download
from ._store import DEFAULT_STORE

__version__ = "0.1.0"
__all__ = [
    "DEFAULT_CATALOGUE", "DEFAULT_STORE", "colour", "download", "metadata",
    "open_dataset", "read", "sample", "versions",
]
