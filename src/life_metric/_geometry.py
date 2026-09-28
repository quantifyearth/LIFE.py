"""Adapt standard vector geometries to rasterio masks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol, TypeAlias


class GeoInterface(Protocol):
    """A geometry that exposes the standard Python geo interface."""

    @property
    def __geo_interface__(self) -> Mapping[str, Any]: ...


Geometry: TypeAlias = Mapping[str, Any] | GeoInterface


def _geometries(value: Any) -> list[dict[str, Any]]:
    obj = getattr(value, "__geo_interface__", value)
    if isinstance(obj, Mapping):
        kind = obj.get("type")
        if kind == "Feature":
            return _geometries(obj["geometry"])
        if kind == "FeatureCollection":
            return [shape for feature in obj["features"] for shape in _geometries(feature)]
        if kind in ("Polygon", "MultiPolygon"):
            return [dict(obj)]
        raise ValueError("geometry must contain non-empty polygons or multipolygons")
    if isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
        return [shape for item in obj for shape in _geometries(item)]
    raise TypeError("geometry must be GeoJSON, a Shapely geometry, or an iterable of geometries")


def shapes_in_wgs84(value: Geometry | Iterable[Geometry], crs: Any) -> list[dict[str, Any]]:
    """Return validated polygon geometries in the store's CRS."""
    from rasterio.crs import CRS
    from rasterio.features import is_valid_geom
    from rasterio.warp import transform_geom

    shapes = _geometries(value)
    if not shapes or not all(is_valid_geom(shape) for shape in shapes):
        raise ValueError("geometry must contain non-empty polygons")
    source_crs = CRS.from_user_input(crs)
    target_crs = CRS.from_epsg(4326)
    if source_crs != target_crs:
        shapes = [dict(transform_geom(source_crs, target_crs, shape)) for shape in shapes]
    return shapes
