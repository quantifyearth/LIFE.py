life-metric(1)
==============

NAME
----

life-metric — query and download LIFE Zarr data.

SYNOPSIS
--------

``life-metric query LAT LON [SOURCE] [--json]``

``life-metric download OUTPUT [SOURCE] --bbox WEST SOUTH EAST NORTH``

DESCRIPTION
-----------

``life-metric`` reads LIFE Zarr stores. Install it with
``pip install life-metric``. Run ``life-metric --help`` for the command list.

QUERY
-----

``query`` reads one score at a latitude and longitude. The default layer is
``arable_0.25`` and the default band is ``all``. Use ``--area`` to read
changed area instead. A store may be a local directory or a URL.

The query and download example below is kept in ``examples/cli.sh`` and
is run against a test store by the test suite.

.. literalinclude:: ../examples/cli.sh
   :language: shell

The first coordinate is latitude. ``--json`` writes one object with the
version, layer, coordinates, value and units. Missing scores become JSON
``null``. ``--level`` selects a resolution factor; ``1`` is source resolution.

DOWNLOAD
--------

``download`` saves one bounded layer as a compressed NumPy ``.npz`` file.
It includes ``data``, pixel-centre ``lat`` and ``lon`` arrays, and a JSON
``metadata`` string. The output must end in ``.npz``. The command requires a
bounding box and refuses to replace an existing file unless
``--overwrite`` is given.

``--all-bands`` includes every species group. ``--area`` selects changed
area in square metres. Large regions should be split into smaller boxes;
the command reads at most 16 million values per file.

INFO AND RELEASES
-----------------

``info`` describes a store from its own attributes. ``releases`` lists the
versions in a ``versions.json`` catalogue. Both accept ``--json``.

.. code-block:: shell

   life-metric info /path/to/v1.01
   life-metric releases
   life-metric releases --catalogue /path/to/catalogue --json

ADMIN
-----

Install ``life-metric[build]`` to convert the existing v1.01 Zenodo GeoTIFFs
to Zarr. These commands are for people maintaining a store. To regenerate
LIFE from source data, use `quantifyearth/LIFE
<https://github.com/quantifyearth/LIFE>`_.

.. code-block:: shell

   life-metric admin download-zenodo --data-dir data
   life-metric admin convert --data-dir data
   life-metric admin pyramid --data-dir data
   life-metric admin verify --data-dir data
   life-metric admin catalogue --data-dir data --released 2024-12-19

The beta has a separate converter in ``examples/build_beta_store.py``.
The methods and meaning of the scores are described by `Eyres et al. (2025)
<https://doi.org/10.1098/rstb.2023.0327>`_. The store carries its terms of use.
