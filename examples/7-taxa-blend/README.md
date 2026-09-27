# 7. Blend the taxa

A score layer has `all` followed by the four taxonomic classes. Read the
bands together, skip `all`, and give each class its own colour range.
`make_blend()` colours the strongest class and darkens places where classes
are similarly affected.

```python
from life_metric import BBox, colour, open_store

raster = open_store().layer("arable", "0.25").read(None, bbox=BBox(90, -12, 130, 25), level=4)
stack = raster.data[1:]
blend = colour.make_blend([colour.percentile_abs(b, 99) for b in stack])
open("taxa.png", "wb").write(colour.to_png(blend.rgba(stack)))
```

Run the [script](taxa_blend.py) to write `taxa.png` from an overview. Use
`--level`, `--bbox`, and `--output` to change the result.

```sh
uv run python examples/7-taxa-blend/taxa_blend.py /path/to/v1.01 --output taxa.png
```

Next, [use xarray](../8-xarray-levels/README.md).
