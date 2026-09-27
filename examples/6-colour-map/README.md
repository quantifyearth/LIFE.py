# 6. Colour a map

`colour.make_scale()` maps one score band to RGBA pixels. Red means more
expected extinctions and blue means fewer. The 99th percentile sets the
colour range so a few large values do not dominate the image.

```python
from life_metric import BBox, colour, open_store

raster = open_store().layer("restore", "0.25").read("all", bbox=BBox(43, -26, 51, -12))
scale = colour.make_scale(colour.percentile_abs(raster.data, 99))
open("region.png", "wb").write(colour.to_png(scale.rgba(raster.data)))
```

Run the [script](colour_map.py) to write `region.png`. Use `--output` to
choose another path.

```sh
uv run python examples/6-colour-map/colour_map.py /path/to/v1.01 --output region.png
```

Next, [blend the taxa](../7-taxa-blend/README.md).
