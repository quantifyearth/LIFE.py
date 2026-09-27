"""Read the LIFE maps of extinction risk from land-cover change.

LIFE maps the change in expected extinctions from land-cover change. The
available scenarios and curves depend on the dataset version and are read
from the store's attributes. Open the published v1.01 store with
:func:`open_store`, or select a release through :class:`Catalogue`::

    from life_metric import open_store, BBox

    store = open_store()
    print(store.describe())
    layer = store.layer("arable", "0.25")
    raster = layer.read("all", bbox=BBox(-1, 51.5, 1, 52.5))
    print(layer.value(52.2, 0.1))

:mod:`life_metric.colour` turns rasters into RGBA images. The ``life-metric``
command queries and downloads regions; its ``admin`` commands build stores
from GeoTIFFs using :mod:`life_metric.build` and :mod:`life_metric.dataset`.
"""

from . import colour
from ._catalogue import DEFAULT_CATALOGUE, Catalogue, Release
from ._grid import BBox, Grid, Window
from ._store import (
    DEFAULT_STORE,
    Curve,
    Info,
    Kind,
    Layer,
    Level,
    Raster,
    Scenario,
    Store,
    Taxon,
    open_store,
    parse_layout,
)

__version__ = "0.1.0"
__all__ = [
    "BBox", "Catalogue", "Curve", "DEFAULT_CATALOGUE", "DEFAULT_STORE",
    "Grid", "Info", "Kind", "Layer", "Level", "Raster", "Release",
    "Scenario", "Store", "Taxon", "Window", "colour", "open_store",
    "parse_layout",
]
