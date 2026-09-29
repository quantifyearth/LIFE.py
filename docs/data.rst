LIFE data
=========

Scores and changed area
-----------------------

LIFE scores estimate the change in expected extinctions per square kilometre
of land changed. Positive values mean more extinctions, and negative values
mean fewer. Missing scores are NaN. Arable layers also contain valid zero
scores over the ocean. Use the changed-area layer to identify where a
scenario affects land.

A score layer is named ``{scenario}_{curve}``. It has an ``all`` band and
separate ``AMPHIBIA``, ``AVES``, ``MAMMALIA``, and ``REPTILIA`` bands. The
``all`` band is the sum of the four classes. In v1.01, ``arable`` converts
land to cropland and ``restore`` restores cropland and pasture to natural
vegetation. Curve ``0.25`` is the main result; the other curves are a
sensitivity analysis. Read the descriptions in ``metadata()`` when choosing
a scenario or curve.

Changed-area layers are named ``{scenario}_area_changed`` and use square
metres. Zero area is valid data. At native resolution, multiply a score by
changed area divided by one million to estimate the change in expected
extinctions for a pixel.

Versions and resolution
-----------------------

Reads use the published v1.01 store by default. Pass ``source`` for a local
store or URL, or ``version`` for a named release. ``versions()`` lists the
catalogue entries. The catalogue also includes ``1.1~beta1``, which has six
scenarios, curve ``0.25``, and float64 values. v1.01 uses float32 values.
Inspect ``metadata()["scenarios"]`` and ``metadata()["curves"]`` for the
selected version. See :ref:`choose-version`.

``level=1`` selects native resolution. Levels 2, 4, 8, and 16 have pixels
that many times wider. Overviews average finite values for display and
exploration. Use level 1 for area totals or calculations that multiply
scores by changed area. Multiplying overview averages does not preserve
those totals.

Coordinates and metadata
------------------------

The raster CRS is EPSG:4326. Bounds use west, south, east, north, and point
pairs use longitude, latitude. Returned transforms describe pixel edges.
xarray coordinates describe pixel centres, with latitude decreasing from
north to south. Split regions at the antimeridian before reading them.

``metadata()`` returns the store's dataset attributes, including scenario,
curve, and taxon descriptions, the citation, and data terms. xarray datasets
carry these in ``dataset.attrs``. The :doc:`api` and :doc:`tutorial` describe
how to read them.

The methods are described by `Eyres et al. (2025)
<https://doi.org/10.1098/rstb.2023.0327>`_. The data are subject to IBAT terms:
non-commercial use only, and no redistribution in their original form
without written permission. Read ``metadata()["terms_of_reference"]`` for
the full terms.
