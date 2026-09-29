"""Open a store and read its layers.

A store is a Zarr group whose root attributes describe the dataset and whose
``multiscales`` layout lists its resolution levels. Everything a reader needs
to know, from what a value means to which scenarios and species groups exist,
is read from those attributes, so the objects here describe themselves.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
import zarr
from numpy.typing import ArrayLike, NDArray

from ._catalogue import DEFAULT_CATALOGUE
from ._grid import BBox, Grid, Window

Kind = Literal["score", "area"]
FloatData = NDArray[np.float32] | NDArray[np.float64]

DEFAULT_STORE = f"{DEFAULT_CATALOGUE}/v1.01"
"""The published v1.01 store, opened when :func:`open_store` is given no source."""


@dataclass(frozen=True)
class Info:
    """What the dataset is, as written in the store's root attributes."""

    title: str
    summary: str
    version: str
    doi: str | None = None
    """DOI of the data of record."""
    concept_doi: str | None = None
    """DOI shared by every version of the data."""
    citation: str | None = None
    source_url: str | None = None
    terms_of_use: str | None = None


@dataclass(frozen=True)
class Level:
    """One resolution level from the store's ``multiscales`` layout."""

    factor: int
    """Reduction factor relative to the base level: 1 for the base."""
    path: str
    """Group path of the level inside the store."""
    grid: Grid
    resampling_method: str | None = None
    """How the level was derived from the one above, for example ``"average"``."""


def parse_layout(layout: list[dict[str, Any]], fallback: Grid | None = None) -> dict[int, Level]:
    """Read the levels of a zarr-conventions ``multiscales`` layout.

    A level's factor is the product of ``transform.scale`` along its
    ``derived_from`` chain; its grid comes from ``spatial:transform`` and
    ``spatial:shape``, or from *fallback* scaled by the factor.
    """
    factors: dict[str, int] = {}
    levels: dict[int, Level] = {}
    for entry in layout:
        asset = str(entry["asset"])
        parent = factors.get(str(entry.get("derived_from", "")), 1)
        scale = (entry.get("transform") or {}).get("scale") or [1.0]
        factor = int(round(parent * float(scale[0])))
        factors[asset] = factor
        st, shape = entry.get("spatial:transform"), entry.get("spatial:shape")
        if st and shape:
            grid = Grid(int(shape[1]), int(shape[0]), float(st[0]), float(st[2]), float(st[5]))
        elif fallback is not None:
            rows, cols = -(-fallback.height // factor), -(-fallback.width // factor)
            grid = Grid(cols, rows, fallback.res * factor, fallback.lon0, fallback.lat0)
        else:
            raise ValueError(f"level {asset!r} has no spatial:transform and no fallback grid")
        method = entry.get("resampling_method")
        levels[factor] = Level(factor, asset, grid, str(method) if method else None)
    return levels


def _array_at(group: zarr.Group, path: str) -> zarr.Array[Any]:
    node = group[path]
    if not isinstance(node, zarr.Array):
        raise TypeError(f"{path} is not an array")
    return node


def open_store(source: str | os.PathLike[str] | zarr.Group = DEFAULT_STORE, *,
               storage_options: dict[str, Any] | None = None) -> Store:
    """Open a LIFE store from a directory, a URL or an already opened group.

    With no argument it opens the published v1.01 store on source.coop. The
    store is opened read-only and its consolidated metadata is used when
    present.
    """
    if isinstance(source, zarr.Group):
        return Store(source, str(source.store))
    group = zarr.open_group(str(source), mode="r", zarr_format=3, storage_options=storage_options)
    return Store(group, str(source))


@dataclass(frozen=True)
class Raster:
    """Pixels read from one layer, with the grid that places them.

    ``data`` is ``(height, width)`` for one band or ``(bands, height, width)``
    for a stack, in the layer's float32 or float64 dtype. Missing scores are
    NaN; areas use zero where no land changes.
    """

    data: FloatData
    grid: Grid
    bands: tuple[str, ...]
    layer: str
    level: int

    @property
    def is_stack(self) -> bool:
        """Whether this raster holds more than one band."""
        return self.data.ndim == 3

    def band(self, name: str) -> FloatData:
        """Return the 2-D array of one band by name."""
        if not self.is_stack:
            if name != self.bands[0]:
                raise KeyError(f"raster holds only {self.bands[0]!r}")
            data: FloatData = self.data
            return data
        band: FloatData = self.data[self.bands.index(name)]
        return band


class Layer:
    """One layer of a store: a score layer for a scenario and curve, or an area layer.

    A score layer holds one band per species group and gives, per pixel, the
    change in the expected number of extinctions per km² of land changed. An
    area layer holds one band giving the area of land that changes. ``units``,
    ``long_name`` and ``description`` say so in the store's own words. Reads
    accept a ``level``: 1 is the base grid and each higher factor an overview
    whose pixels average the finite pixels beneath them.
    """

    def __init__(self, store: Store, name: str, scenario: str, curve: str | None, kind: Kind) -> None:
        self.store = store
        self.name = name
        self.scenario = scenario
        self.curve = curve
        self.kind: Kind = kind
        self._arrays: dict[int, zarr.Array[Any]] = {}
        base = self._array(1)
        self.attrs: dict[str, Any] = dict(base.attrs)
        labels = self.attrs.get("taxon_labels") or self.attrs.get("source_bands")
        self.bands: tuple[str, ...] = tuple(labels) if kind == "score" and labels else (("area",) if kind == "area" else tuple(store.taxa))
        self.units: str = str(self.attrs.get("units", ""))
        self.long_name: str = str(self.attrs.get("long_name", name))
        self.description: str = str(self.attrs.get("description", ""))
        fv = base.fill_value
        self.fill_value: float = float("nan") if fv is None else float(fv)
        self.statistics: dict[str, dict[str, Any]] = dict(self.attrs.get("statistics", {}))

    def __repr__(self) -> str:
        return f"Layer({self.name!r}, bands={self.bands}, shape={self.shape()})"

    @property
    def scenario_description(self) -> str:
        """Return the store's description of this layer's scenario."""
        return self.store.scenarios.get(self.scenario, "")

    @property
    def curve_description(self) -> str:
        """Return the store's description of this layer's curve, or "" for an area layer."""
        return self.store.curves.get(self.curve or "", "")

    @property
    def summary(self) -> str:
        """Return one plain-language sentence saying what the layer holds."""
        if self.kind == "area":
            return f"{self.name}: area of land that changes in each pixel ({self.units}) under {self.scenario_description or self.scenario}."
        return (f"{self.name}: change in expected extinctions per km² of land changed "
                f"({self.units}) under {self.scenario_description or self.scenario}, "
                f"with {self.curve_description or self.curve}; bands {', '.join(self.bands)}.")

    def _array(self, level: int) -> zarr.Array[Any]:
        if level not in self._arrays:
            self._arrays[level] = _array_at(self.store._group, self.store.path(level, self.name))
        return self._arrays[level]

    def shape(self, level: int = 1) -> tuple[int, ...]:
        """Return the array shape at ``level``."""
        return tuple(self._array(level).shape)

    def grid(self, level: int = 1) -> Grid:
        """Return the grid of the layer at ``level``."""
        return self.store.level_grid(level)

    def band_index(self, taxon: str) -> int:
        """Return the band index of ``taxon``; raise KeyError if the layer lacks it."""
        try:
            return self.bands.index(taxon)
        except ValueError:
            raise KeyError(f"{self.name} has bands {self.bands}, not {taxon!r}") from None

    def read(self, taxon: str | None = "all", *, bbox: BBox | None = None, window: Window | None = None,
             level: int = 1) -> Raster:
        """Read one band, or every band when ``taxon`` is None, inside a region.

        The region is a bounding box in degrees or a window of rows and
        columns; with neither, the whole level is read. Area layers ignore
        ``taxon``.
        """
        arr = self._array(level)
        grid = self.grid(level)
        if bbox is not None and window is not None:
            raise ValueError("give bbox or window, not both")
        win = window if window is not None else grid.window(bbox) if bbox is not None else Window(0, grid.height, 0, grid.width)
        rows, cols = slice(win.row0, win.row1), slice(win.col0, win.col1)
        if self.kind == "area" or arr.ndim == 2:
            data = cast(FloatData, np.asarray(arr[rows, cols]))
            return Raster(data, grid.sub(win), self.bands, self.name, level)
        if taxon is None:
            data = cast(FloatData, np.asarray(arr[:, rows, cols]))
            return Raster(data, grid.sub(win), self.bands, self.name, level)
        b = self.band_index(taxon)
        data = cast(FloatData, np.asarray(arr[b, rows, cols]))
        return Raster(data, grid.sub(win), (taxon,), self.name, level)

    def value(self, lat: float, lon: float, taxon: str = "all", *, level: int = 1) -> float:
        """Return the value at a point, NaN where there is no data."""
        return float(self.sample([lat], [lon], taxon, level=level)[0])

    def sample(self, lats: ArrayLike, lons: ArrayLike, taxon: str = "all", *, level: int = 1) -> FloatData:
        """Return the value at each point, NaN off the grid or where there is no data."""
        arr = self._array(level)
        grid = self.grid(level)
        rows, cols = grid.rows(lats), grid.cols(lons)
        out = cast(FloatData, np.full(rows.shape, np.nan, dtype=arr.dtype))
        ok = rows >= 0
        if not ok.any():
            return out
        if arr.ndim == 2:
            vals = arr.vindex[rows[ok], cols[ok]]
        else:
            b = 0 if self.kind == "area" else self.band_index(taxon)
            vals = arr.vindex[np.full(int(ok.sum()), b), rows[ok], cols[ok]]
        out[ok] = vals
        return out


def _descriptions(value: Any, name: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value or not all(
            isinstance(v, str) and v.strip() for v in value.values()):
        raise ValueError(f"the store has no valid {name} descriptions")
    return dict(value)


class Store:
    """A LIFE store: what it is, its resolution levels and its layers.

    ``info`` says what the dataset is; ``scenarios``, ``curves`` and ``taxa``
    map each name to the store's description of it; ``data_model`` explains
    the arrays and their values; ``levels`` lists the
    resolution levels by reduction factor, 1 being the base grid. All of it is
    read from the store's root attributes and ``multiscales`` layout, so a
    store from another dataset version is described by its own contents.
    """

    def __init__(self, group: zarr.Group, source: str) -> None:
        self._group = group
        self.source = source
        self.attrs: dict[str, Any] = dict(group.attrs)
        a = self.attrs
        self.version: str = str(a.get("version", "unknown"))
        self.info = Info(
            title=str(a.get("title", "LIFE")), summary=str(a.get("summary", "")), version=self.version,
            doi=a.get("source_doi"), concept_doi=a.get("concept_doi"), citation=a.get("references"),
            source_url=a.get("source_url"), terms_of_use=a.get("terms_of_reference"),
        )
        self.scenarios: dict[str, str] = _descriptions(a.get("scenarios"), "scenario")
        """Scenario name to the store's description of it."""
        self.curves: dict[str, str] = _descriptions(a.get("curves"), "curve")
        """Curve name to the store's description of it."""
        self.taxa: dict[str, str] = _descriptions(a.get("taxa"), "taxon")
        """Species group name to the store's description of it."""
        self.data_model: dict[str, str] = {str(k): str(v) for k, v in (a.get("data_model") or {}).items()}
        """The store's explanation of array names, values and overview use."""
        layout = (self.attrs.get("multiscales") or {}).get("layout")
        if not layout:
            raise ValueError(f"{source}: the root group has no multiscales layout")
        self._levels = parse_layout(layout)
        if 1 not in self._levels:
            raise ValueError(f"{source}: the multiscales layout has no base level")
        self.levels: tuple[int, ...] = tuple(sorted(self._levels))
        self.grid = self._levels[1].grid
        self._layers: dict[str, Layer] = {}

    def __repr__(self) -> str:
        return f"Store({self.source!r}, version={self.version!r}, levels={self.levels})"

    def level(self, factor: int) -> Level:
        """Return the level with reduction *factor*; raise ValueError if absent."""
        try:
            return self._levels[factor]
        except KeyError:
            raise ValueError(f"level {factor} is not in the store; have {self.levels}") from None

    def level_grid(self, level: int) -> Grid:
        """Return the grid of a level; level 1 is the base grid."""
        return self.level(level).grid

    def path(self, level: int, name: str) -> str:
        """Return the store path of array *name* at *level*."""
        base = self.level(level).path
        return f"{base}/{name}" if base else name

    def _has(self, path: str) -> bool:
        return path in self._group

    def layer_names(self) -> list[str]:
        """Return the names of the layers present, score layers first."""
        names = [f"{s}_{c}" for s in self.scenarios for c in self.curves] + [f"{s}_area_changed" for s in self.scenarios]
        return [n for n in names if self._has(self.path(1, n))]

    def layers(self) -> list[Layer]:
        """Return every layer present in the store."""
        return [self.get(n) for n in self.layer_names()]

    def get(self, name: str) -> Layer:
        """Return the layer called ``name``; raise KeyError if absent."""
        if name not in self._layers:
            if not self._has(self.path(1, name)):
                raise KeyError(f"{name!r} is not in {self.source}; have {self.layer_names()}")
            attrs = _array_at(self._group, self.path(1, name)).attrs
            if name.endswith("_area_changed"):
                scenario = str(attrs.get("scenario") or name[: -len("_area_changed")])
                self._layers[name] = Layer(self, name, scenario, None, "area")
            else:
                scenario = str(attrs.get("scenario") or next((s for s in sorted(self.scenarios, key=len, reverse=True)
                                                              if name.startswith(f"{s}_")), ""))
                curve = str(attrs.get("curve") or name[len(scenario) + 1:])
                self._layers[name] = Layer(self, name, scenario, curve, "score")
        return self._layers[name]

    def layer(self, scenario: str, curve: str = "0.25") -> Layer:
        """Return the score layer for a scenario and persistence curve."""
        return self.get(f"{scenario}_{curve}")

    def area(self, scenario: str) -> Layer:
        """Return the area-changed layer for a scenario."""
        return self.get(f"{scenario}_area_changed")

    def describe(self) -> str:
        """Return a plain-language summary of the store: what it is, its levels, scenarios, curves, groups and layers."""
        lines = [f"{self.info.title} (version {self.version}) from {self.source}", self.info.summary, "",
                 f"grid {self.grid.width} x {self.grid.height} pixels at {self.grid.res:g} degrees, "
                 + "levels " + ", ".join(f"{f} (group {self._levels[f].path or '.'}, {self._levels[f].grid.width} x {self._levels[f].grid.height})" for f in self.levels)]
        for title, items in (("scenarios", self.scenarios), ("curves", self.curves), ("species groups", self.taxa)):
            lines.append(f"{title}:")
            lines += [f"  {k:10s} {v}" for k, v in items.items()]
        if self.data_model:
            lines.append("data model:")
            lines += [f"  {k}: {v}" for k, v in self.data_model.items()]
        lines.append("layers:")
        lines += [f"  {layer.name:22s} {str(layer.shape()):22s} {layer.units:18s} {layer.long_name}" for layer in self.layers()]
        if self.info.terms_of_use:
            lines += ["", f"terms of use: {self.info.terms_of_use}"]
        return "\n".join(lines)
