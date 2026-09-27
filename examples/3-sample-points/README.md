# 3. Sample points

`Layer.sample()` reads matching latitude and longitude arrays in one call.
This example compares the v1.01 arable and restoration scores at several
places. NaN means the scenario changes no land in that pixel.

```python
from life_metric import open_store

layer = open_store().layer("arable", "0.25")
values = layer.sample([-19.5, 5.6], [47.0, 10.2])
print(values)
```

Run the [script](sample_points.py) with a local store or the published one.

```sh
uv run python examples/3-sample-points/sample_points.py /path/to/v1.01
```

Next, [read a region](../4-read-region/README.md).
