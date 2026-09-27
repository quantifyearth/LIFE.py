"""Inspect a store's descriptions without reading raster pixels."""

import sys

from life_metric import open_store

store = open_store(*sys.argv[1:2])
print(store.describe())
print()
