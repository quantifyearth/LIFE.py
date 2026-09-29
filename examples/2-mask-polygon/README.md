# 2. Mask a polygon

Pass a Shapely polygon, GeoJSON geometry, or GeoPandas geometry column to
`read()`. Supply its CRS with `crs`. The function crops to the polygon bounds
and returns a NumPy masked array. Pixel centres determine inclusion by default;
`all_touched=True` includes any touched pixel. The returned raster remains in
EPSG:4326. Install `life-metric[geo]` for this step.

```python
from shapely.geometry import box
from life_metric import read

polygon = box(43, -26, 51, -12)
values, transform = read("arable_0.25", geometry=polygon, crs="EPSG:4326")
print(values.mean())
```

Run the [script](mask_polygon.py) from the repository root.

```sh
uv run --extra geo python examples/2-mask-polygon/mask_polygon.py /path/to/v1.01
```

Next, [download a GeoTIFF](../3-download-geotiff/README.md).
