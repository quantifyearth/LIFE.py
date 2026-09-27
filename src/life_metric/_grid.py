"""Grid arithmetic shared by every level of a store."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

_EPS = 1e-9


@dataclass(frozen=True)
class BBox:
    """A geographic bounding box in degrees.

    The box runs from west to east and from south to north. It may not cross
    the antimeridian.
    """

    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        if not -180 <= self.west < self.east <= 180:
            raise ValueError(f"longitudes must satisfy -180 <= west < east <= 180, got {self.west}, {self.east}")
        if not -90 <= self.south < self.north <= 90:
            raise ValueError(f"latitudes must satisfy -90 <= south < north <= 90, got {self.south}, {self.north}")


@dataclass(frozen=True)
class Window:
    """A half-open block of rows and columns of a grid."""

    row0: int
    row1: int
    col0: int
    col1: int

    @property
    def height(self) -> int:
        """Number of rows in the window."""
        return self.row1 - self.row0

    @property
    def width(self) -> int:
        """Number of columns in the window."""
        return self.col1 - self.col0


@dataclass(frozen=True)
class Grid:
    """A regular latitude-longitude grid in EPSG:4326.

    Rows run from the top edge ``lat0`` southwards and columns run from the
    left edge ``lon0`` eastwards, both in steps of ``res`` degrees. Pixel
    centres sit half a step inside each edge.
    """

    width: int
    height: int
    res: float
    lon0: float = -180.0
    lat0: float = 90.0

    @property
    def transform(self) -> tuple[float, float, float, float, float, float]:
        """Return the GDAL geotransform ``(x0, dx, 0, y0, 0, -dy)``."""
        return (self.lon0, self.res, 0.0, self.lat0, 0.0, -self.res)

    @property
    def bounds(self) -> BBox:
        """Return the outer edges of the grid."""
        return BBox(self.lon0, self.lat0 - self.height * self.res, self.lon0 + self.width * self.res, self.lat0)

    def latitudes(self) -> NDArray[np.float64]:
        """Return the pixel-centre latitude of every row, north to south."""
        return self.lat0 - (np.arange(self.height, dtype="float64") + 0.5) * self.res

    def longitudes(self) -> NDArray[np.float64]:
        """Return the pixel-centre longitude of every column, west to east."""
        return self.lon0 + (np.arange(self.width, dtype="float64") + 0.5) * self.res

    def rows(self, lats: ArrayLike) -> NDArray[np.int64]:
        """Return the row of each latitude, or -1 where it falls off the grid."""
        r = np.floor((self.lat0 - np.asarray(lats, dtype="float64")) / self.res + _EPS).astype("int64")
        inside: NDArray[np.int64] = np.where((r >= 0) & (r < self.height), r, -1)
        return inside

    def cols(self, lons: ArrayLike) -> NDArray[np.int64]:
        """Return the column of each longitude, wrapping around the antimeridian."""
        c = np.floor((np.asarray(lons, dtype="float64") - self.lon0) / self.res + _EPS).astype("int64")
        wrapped: NDArray[np.int64] = np.mod(c, self.width)
        return wrapped

    def row(self, lat: float) -> int:
        """Return the row containing ``lat``; raise ValueError off the grid."""
        r = int(self.rows(lat))
        if r < 0:
            raise ValueError(f"latitude {lat} is outside the grid ({self.bounds.south} to {self.bounds.north})")
        return r

    def col(self, lon: float) -> int:
        """Return the column containing ``lon``."""
        return int(self.cols(lon))

    def window(self, bbox: BBox) -> Window:
        """Return the smallest window covering ``bbox``, clipped to the grid."""
        row0 = max(0, math.floor((self.lat0 - bbox.north) / self.res + _EPS))
        row1 = min(self.height, math.ceil((self.lat0 - bbox.south) / self.res - _EPS))
        col0 = max(0, math.floor((bbox.west - self.lon0) / self.res + _EPS))
        col1 = min(self.width, math.ceil((bbox.east - self.lon0) / self.res - _EPS))
        if row1 <= row0 or col1 <= col0:
            raise ValueError(f"{bbox} does not overlap the grid {self.bounds}")
        return Window(row0, row1, col0, col1)

    def sub(self, window: Window) -> Grid:
        """Return the grid of the pixels inside ``window``."""
        return Grid(window.width, window.height, self.res,
                    self.lon0 + window.col0 * self.res, self.lat0 - window.row0 * self.res)
