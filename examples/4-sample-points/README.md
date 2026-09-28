# 4. Sample points

`sample()` takes longitude-latitude pairs in EPSG:4326, as rasterio does,
and returns a NumPy array. The example compares arable conversion and
restoration. NaN means no score is available at that point.

```python
from life_metric import sample

xy = [(47.0, -19.5), (10.2, 5.6)]
values = sample("arable_0.25", xy)
print(values)
```

Run the [script](sample_points.py) from the repository root.

```sh
uv run python examples/4-sample-points/sample_points.py /path/to/v1.01
```

Next, [choose a version](../5-choose-version/README.md).
