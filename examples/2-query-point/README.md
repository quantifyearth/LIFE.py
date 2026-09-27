# 2. Query a point

`Layer.value()` takes latitude first and longitude second. A score is the
change in expected extinctions per square kilometre of land changed. The
matching area layer gives the changed land in square metres. A missing score
is NaN.

```python
from life_metric import open_store

store = open_store()
score = store.layer("arable", "0.25").value(-19.5, 47.0)
area = store.area("arable").value(-19.5, 47.0)
print(score, area)
```

Run the [script](query_point.py) with an optional store, latitude, and
longitude. The script also prints the available scenarios and curves.

```sh
uv run python examples/2-query-point/query_point.py /path/to/v1.01 -19.5 47.0
```

Next, [sample several points](../3-sample-points/README.md).
