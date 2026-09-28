# 1. Read a region with NumPy

`read()` returns a NumPy array and an Affine transform in EPSG:4326.
Bounds are west, south, east, north. Pixels that intersect the bounds are
included. Use NumPy to calculate statistics directly; missing scores are NaN.
The returned transform describes the actual pixel edges.

```python
from life_metric import read
import numpy as np

values, transform = read("restore_0.25", bounds=(43, -26, 51, -12))
print(np.nanmean(values), transform)
```

Run the [script](read_region.py) from the repository root.

```sh
uv run python examples/1-read-region/read_region.py /path/to/v1.01
```

Next, [mask a polygon](../2-mask-polygon/README.md).
