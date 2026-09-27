# 4. Read a region

`BBox` orders its edges west, south, east, north. `Layer.read()` returns the
selected pixels and a `Grid` that gives their bounds and pixel centres.
Selecting a region avoids loading the whole global array.

```python
from life_metric import BBox, open_store

layer = open_store().layer("restore", "0.25")
raster = layer.read("all", bbox=BBox(43, -26, 51, -12))
print(raster.data.shape, raster.grid.bounds)
```

Run the [script](read_region.py) for Madagascar, or pass `--bbox` with another
region.

```sh
uv run python examples/4-read-region/read_region.py /path/to/v1.01
```

Next, [choose a version](../5-choose-version/README.md).
