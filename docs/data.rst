LIFE data and stores
====================

What the scores mean
--------------------

The v1.01 LIFE release maps how land-use changes affect the survival of
30,875 species of amphibians, birds, mammals and reptiles. At each land
pixel, one arc-minute or about 1.9 km across, a score estimates the change
in the expected number of species extinctions over the next century if one
square kilometre there changed use. For example, 0.01 means one hundredth of
an expected extinction more. Positive scores mean more extinctions and
negative scores mean fewer. NaN means the scenario changes nothing at that
pixel.

The ``arable`` scenario converts land from its present state to cropland;
``restore`` restores cropland and pasture to natural vegetation. Each has
five persistence curves, which differ in how fast a species is assumed to
lose its chance of survival as its habitat shrinks. Curve ``0.25`` is the
published result; the others form a sensitivity analysis.

Each score layer has an ``all`` band and separate ``AMPHIBIA``, ``AVES``,
``MAMMALIA`` and ``REPTILIA`` bands. ``all`` is the sum of the four class
bands. Each scenario also has a changed-area layer in square metres. At
source resolution, multiply a score by the changed area divided by one
million to estimate the maximum change in expected extinctions in a pixel:

.. code-block:: python

   score = store.layer("restore", "0.25").read("all", bbox=box).data
   area_m2 = store.area("restore").read(bbox=box).data
   pixel_change = score * (area_m2 / 1_000_000)

Use a bounded region for ordinary reads: the full source grid is large.
The :ref:`read-region` tutorial step shows how to choose a bounding box.

Versions and resolution
-----------------------

``open_store()`` opens the published v1.01 store by default. It also accepts
a local directory, URL or open zarr group. A ``Catalogue`` reads
``versions.json`` at a catalogue root and can open a named release. The
published catalogue also lists ``1.1~beta1``. That beta has six scenarios
(``arable``, ``pasture``, ``urban``, ``restore``,
``restore_agriculture``, ``restore_all``), only curve ``0.25``, and float64
values; v1.01 uses float32. Inspect ``store.scenarios``, ``store.curves``
and ``store.layer_names()`` rather than assuming every release has the same
layers. See :ref:`choose-version`.

The base grid is level 1. Levels 2, 4, 8 and 16 have pixels that many times
wider. An overview pixel averages finite values beneath it for display and
exploration. Use level 1 for area totals or calculations that multiply
scores by changed area. ``store.level(factor)`` gives a level's group path
and grid; levels are selected by reduction factor, not group name.

Store layout and metadata
-------------------------

The Zarr root carries the dataset title, summary, version, citation, terms,
scenario, curve and taxon descriptions, plus a ``data_model`` explaining
array names, units and missing values. Its ``multiscales.layout`` maps
reduction factors to level groups. The package reads these attributes, so
``store.describe()`` and layer descriptions reflect the opened version.

Each level group contains ``lat``, ``lon``, ``taxon``, ``spatial_ref``, score
arrays named ``{scenario}_{curve}`` and area arrays named
``{scenario}_area_changed``. Arrays describe their units, scenario, kind,
and, for scores, their curve and taxon bands. Score arrays have NaN fill;
area arrays have zero fill. Level groups carry CRS and affine placement in
``proj:`` and ``spatial:`` attributes. The ``taxon`` coordinate uses integer
indices with ``flag_values`` and ``flag_meanings`` attributes.

These attributes are also available through zarr-python directly:

.. code-block:: python

   import zarr

   root = zarr.open_group("/path/to/v1.01", mode="r")
   print(root.attrs["data_model"])
   base = root[root.attrs["multiscales"]["layout"][0]["asset"]]
   print(base["arable_0.25"].attrs["description"])

The complete method signatures are in the :doc:`api`. To render scores,
see :ref:`colour-map` and :ref:`blend-taxa`.
