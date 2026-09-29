LIFE.py
=======

LIFE.py reads LIFE extinction-risk maps from Zarr v3 into NumPy arrays,
GeoTIFFs, and native xarray datasets. Install ``life-metric`` for regional
reads and point samples, ``life-metric[geo]`` for polygon masks and GeoTIFF
export, or ``life-metric[xarray]`` for xarray and rioxarray.

The original pipeline for generating LIFE from source data is in `quantifyearth/LIFE
<https://github.com/quantifyearth/LIFE>`_.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   tutorial
   data
   cli
   api

The dataset is subject to `IBAT terms of reference
<https://source.coop/tessera/life>`_: non-commercial use only, and no
redistribution in its original form without prior permission.
