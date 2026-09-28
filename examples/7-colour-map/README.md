# 7. Colour a map

The colour functions accept NumPy arrays. Red means more expected
extinctions and blue means fewer. Set the colour range from the 99th percentile
so a few large values do not dominate the image.

```python
from life_metric import colour, read

values, _ = read("restore_0.25", bounds=(43, -26, 51, -12))
scale = colour.make_scale(colour.percentile_abs(values, 99))
with open("region.png", "wb") as output:
    output.write(colour.to_png(scale.rgba(values)))
```

Run the [script](colour_map.py) from the repository root.

```sh
uv run python examples/7-colour-map/colour_map.py /path/to/v1.01 --output region.png
```

Next, [blend taxa](../8-taxa-blend/README.md).
