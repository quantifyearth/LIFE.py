"""What the LIFE v1.01 dataset is: its Zenodo record, layers, grid and conventions.

The archive holds twelve GeoTIFFs on one shared 1 arc-minute WGS84 grid:

* ten LIFE score layers, one per (scenario, persistence curve), each with
  five float32 bands (all species, then the four taxonomic classes), NaN
  where no land was changed under the scenario;
* two single-band float32 "diff area" layers giving the area of land (m2,
  despite the Zenodo text saying km2) that changes within each pixel under
  the scenario, 0 where nothing changes, with no nodata value.

Everything here is a plain constant so that the converter and the verifier
agree on names, band order and grid geometry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

# --- Zenodo record ----------------------------------------------------------

ZENODO_RECORD = 14945383
ZENODO_DOI = "10.5281/zenodo.14945383"
ZENODO_VERSION = "1.01"
ZENODO_URL = f"https://zenodo.org/records/{ZENODO_RECORD}"
ZENODO_CONCEPT_DOI = "10.5281/zenodo.14188449"
ZENODO_RECORDS = {"1.0": 14188450, "1.01": 14945383}
"""Published releases under the concept DOI; the default converter builds 1.01."""
PUBLISHED_CATALOGUE = "https://data.source.coop/tessera/life"
"""Where the released stores are published; ``<catalogue>/v<version>`` is a store."""


def store_path(data_dir: str | os.PathLike[str], version: str = ZENODO_VERSION) -> Path:
    """Return ``<data_dir>/v<version>``: the store directory, named by its version.

    The same shape is used when the store is published, so the version is
    part of every URL: ``https://data.source.coop/tessera/life/v1.01``.
    """
    return Path(data_dir) / f"v{version}"
ZIP_NAME = "zenodo_eyres_2025.zip"
ZIP_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD}/files/{ZIP_NAME}/content"
ZIP_MD5 = "bfb7afc3fcae222d72e9eda2acc88e18"
ZIP_SIZE = 5_742_657_634
ZIP_PREFIX = "zenodo_eyres_2025/"
TERMS_PDF = "LIFE terms of reference.pdf"

PAPER_DOI = "10.1098/rstb.2023.0327"
PAPER_CITATION = (
    "Eyres A, Ball TS, Dales M, Swinfield T, Arnell A, Baisero D, Durán AP, "
    "Green JMH, Green RE, Madhavapeddy A, Balmford A. 2025 LIFE: A metric for "
    "mapping the impact of land-cover change on global extinctions. "
    "Phil. Trans. R. Soc. B 380: 20230327. https://doi.org/10.1098/rstb.2023.0327"
)
PIPELINE_URL = "https://github.com/quantifyearth/LIFE"
TERMS_OF_REFERENCE = (
    "These data and any derivatives may not be used for commercial or any "
    "revenue generating activities without prior written permission from IBAT. "
    "All forms of reposting, sub-licensing, reselling or other forms of "
    "redistribution of these data in their original format are also prohibited "
    "without prior written permission from IBAT (ibat@ibat-alliance.org)."
)

# --- Grid ---------------------------------------------------------------------
#
# The source rasters are 21600 x 10798 at exactly 1/60 degree: the grid omits
# one row at each pole, so it spans 89°59'N to 89°59'S, and its geotransform
# carries ~1e-12 of floating point noise (origin -180.000000000003581).
#
# The store pads one fill row at each pole, so its base level is the full
# 21600 x 10800 globe from 90N to 90S and every overview level is an exact
# power-of-two reduction of it with the same origin.  Source row r lands in
# store row r + ROW_OFFSET.

WIDTH = 21600
HEIGHT = 10798
"""Rows in the source GeoTIFFs."""
ROW_OFFSET = 1
ROWS = HEIGHT + 2 * ROW_OFFSET
"""Rows in the store's base level: the source plus one fill row at each pole."""
RES = Fraction(1, 60)
LON_MIN = Fraction(-180)
LAT_TOP = Fraction(90)
"""Top edge of the store grid."""
LAT_MAX = LAT_TOP - RES
"""Top edge of the source grid."""
EPSG = 4326
FACTORS = (2, 4, 8, 16)
"""Overview reduction factors; level i is factor 2**i, level 0 the base."""


def level_name(factor: int) -> str:
    """Group name of the level for *factor*: ``"0"`` for the base, ``"1"`` for 2, ..."""
    return str(factor.bit_length() - 1)


def level_res(factor: int) -> Fraction:
    """Return the pixel size in degrees at a reduction factor."""
    return RES * factor


def level_shape(factor: int, rows: int = ROWS, width: int = WIDTH) -> tuple[int, int]:
    """Rows and columns of the level for *factor*; odd sizes round up."""
    return -(-rows // factor), -(-width // factor)


def geotransform(factor: int = 1) -> tuple[float, float, float, float, float, float]:
    """GDAL-style geotransform (x0, dx, 0, y0, 0, dy) of a store level."""
    res = float(level_res(factor))
    return (float(LON_MIN), res, 0.0, float(LAT_TOP), 0.0, -res)


def spatial_transform(factor: int = 1) -> list[float]:
    """The ``spatial:transform`` of a level: ``[a, b, c, d, e, f]`` in Affine order."""
    res = float(level_res(factor))
    return [res, 0.0, float(LON_MIN), 0.0, -res, float(LAT_TOP)]


def source_geotransform() -> tuple[float, float, float, float, float, float]:
    """Geotransform of the source GeoTIFFs, snapped to exact values."""
    return (float(LON_MIN), float(RES), 0.0, float(LAT_MAX), 0.0, -float(RES))


def latitudes(rows: int = ROWS, factor: int = 1) -> np.ndarray:
    """Pixel-centre latitudes of a level, north to south, as float64."""
    res = level_res(factor)
    return np.array(
        [float(LAT_TOP - res * (i + Fraction(1, 2))) for i in range(rows)],
        dtype="float64",
    )


def longitudes(width: int = WIDTH, factor: int = 1) -> np.ndarray:
    """Pixel-centre longitudes of a level, west to east, as float64."""
    res = level_res(factor)
    return np.array(
        [float(LON_MIN + res * (j + Fraction(1, 2))) for j in range(width)],
        dtype="float64",
    )


# --- Zarr conventions ---------------------------------------------------------
#
# The store follows three zarr-conventions extensions: multiscales for the
# overview levels, proj for the CRS and spatial for the affine placement.

CONVENTIONS = {
    "multiscales": {
        "schema_url": "https://raw.githubusercontent.com/zarr-conventions/multiscales/refs/tags/v0.1/schema.json",
        "spec_url": "https://github.com/zarr-conventions/multiscales/blob/v0.1/README.md",
        "uuid": "d35379db-88df-4056-af3a-620245f8e347",
        "name": "multiscales",
        "description": "Multiscale layout of zarr datasets",
    },
    "proj": {
        "schema_url": "https://raw.githubusercontent.com/zarr-conventions/proj/refs/tags/v0.1/schema.json",
        "spec_url": "https://github.com/zarr-conventions/proj/blob/v0.1/README.md",
        "uuid": "f17cb550-5864-4468-aeb7-f3180cfb622f",
        "name": "proj",
        "description": "Coordinate reference system information for geospatial data",
    },
    "spatial": {
        "schema_url": "https://raw.githubusercontent.com/zarr-conventions/spatial/refs/tags/v0.1/schema.json",
        "spec_url": "https://github.com/zarr-conventions/spatial/blob/v0.1/README.md",
        "uuid": "689b58e2-cf7b-45e0-9fff-9cfc0883d6b4",
        "name": "spatial",
        "description": "Spatial coordinate information",
    },
}
RESAMPLING_METHOD = "average"


# --- Layers -------------------------------------------------------------------

TAXA = ("all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA")
TAXA_LONG = {
    "all": "all 30,875 terrestrial vertebrates",
    "AMPHIBIA": "amphibians (7,188 species)",
    "AVES": "birds (9,447 species)",
    "MAMMALIA": "mammals (5,480 species)",
    "REPTILIA": "reptiles (8,760 species)",
}

CURVES = ("0.1", "0.25", "0.5", "1.0", "gompertz")
CURVE_Z = {"0.1": 0.1, "0.25": 0.25, "0.5": 0.5, "1.0": 1.0, "gompertz": None}
CURVE_DESCRIPTION = {
    "0.1": "power-law persistence curve, exponent z = 0.1",
    "0.25": "power-law persistence curve, exponent z = 0.25 (the paper's main analysis)",
    "0.5": "power-law persistence curve, exponent z = 0.5",
    "1.0": "power-law persistence curve, exponent z = 1.0 (linear response to habitat loss)",
    "gompertz": "modified Gompertz persistence curve",
}

SCENARIOS = ("arable", "restore")
SCENARIO_DESCRIPTION = {
    "arable": (
        "conversion to arable: all remaining natural habitat and non-urban "
        "artificial land converted to arable land; values are largely positive "
        "(extinctions increase)"
    ),
    "restore": (
        "reversion to natural: all arable and pasture restored to potential "
        "natural vegetation; values are largely negative (extinctions decrease)"
    ),
}
SCENARIO_SOURCE_AREA = {
    "arable": "convert_to_arable_diff_area.tif",
    "restore": "revert_to_natural_diff_area.tif",
}


@dataclass(frozen=True)
class Layer:
    """One source GeoTIFF and the Zarr array it becomes."""

    name: str
    """Zarr array name within each level group, e.g. ``arable_0.25``."""
    scenario: str
    kind: str
    """``"life"`` for a score layer, ``"area"`` for a diff-area layer."""
    curve: str | None
    source: str
    """File name inside the Zenodo zip, without the directory prefix."""
    bands: tuple[str, ...]
    fill_value: float
    long_name_override: str | None = None
    description_override: str | None = None
    units_override: str | None = None

    @property
    def dims(self) -> tuple[str, ...]:
        """Dimension names in the resulting Zarr array."""
        return ("taxon", "lat", "lon") if self.kind == "life" else ("lat", "lon")

    @property
    def long_name(self) -> str:
        """Human-readable layer name stored with the array."""
        if self.long_name_override is not None:
            return self.long_name_override
        if self.kind == "life" and self.curve is not None:
            return f"LIFE score, {self.scenario} scenario, {CURVE_DESCRIPTION[self.curve]}"
        return f"area of land changed per pixel, {self.scenario} scenario"

    @property
    def units(self) -> str:
        """Array units: extinctions per km² or square metres."""
        if self.units_override is not None:
            return self.units_override
        return "extinctions km-2" if self.kind == "life" else "m2"

    @property
    def description(self) -> str:
        """Explanation stored in the array's attributes."""
        if self.description_override is not None:
            return self.description_override
        if self.kind == "life":
            return (
                "Change in the expected number of extinctions over 100 years per "
                "km2 of land changed within the pixel, summed over species "
                f"({SCENARIO_DESCRIPTION[self.scenario]}). Positive values mean "
                "extinctions increase. NaN where no land changes under the scenario."
            )
        return (
            "Area in m2 of land within the pixel that changes under the scenario "
            f"({SCENARIO_DESCRIPTION[self.scenario]}). The Zenodo description says "
            "km2, but the values are square metres (the pipeline divides by 1e6 "
            "before scaling the scores). Not the pixel area: divide by 1e6 and "
            "multiply by a LIFE score to obtain the maximum change in expected "
            "extinctions possible within the pixel. 0 means no land changes; the "
            "source GeoTIFF has no nodata value."
        )


def _life_layer(scenario: str, curve: str) -> Layer:
    return Layer(
        name=f"{scenario}_{curve}",
        scenario=scenario,
        kind="life",
        curve=curve,
        source=f"scaled_{scenario}_{curve}.tif",
        bands=TAXA,
        fill_value=float("nan"),
    )


def _area_layer(scenario: str) -> Layer:
    return Layer(
        name=f"{scenario}_area_changed",
        scenario=scenario,
        kind="area",
        curve=None,
        source=SCENARIO_SOURCE_AREA[scenario],
        bands=("area",),
        fill_value=0.0,
    )


LAYERS: tuple[Layer, ...] = tuple(
    [_life_layer(s, c) for s in SCENARIOS for c in CURVES]
    + [_area_layer(s) for s in SCENARIOS]
)

LAYERS_BY_NAME = {layer.name: layer for layer in LAYERS}


def layer_by_name(name: str) -> Layer:
    """Return a v1.01 source layer by name, or raise KeyError."""
    try:
        return LAYERS_BY_NAME[name]
    except KeyError:
        raise KeyError(f"unknown layer {name!r}; choose from {list(LAYERS_BY_NAME)}") from None
