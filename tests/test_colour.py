import numpy as np
import pytest

from life_metric import colour


def test_scale_endpoints_and_hiding() -> None:
    s = colour.make_scale(1e-4, mode="log", polarity="diverging")
    assert s.index(0) == round((s.n - 1) / 2) and s.index(np.nan) == round((s.n - 1) / 2)
    assert s.index(1e-4) == s.n - 1 and s.index(-1e-4) == 0 and s.index(5.0) == s.n - 1
    px = s.rgba(np.array([[1e-4, -1e-4], [0.0, np.nan]]))
    assert px.shape == (2, 2, 4)
    assert tuple(px[0, 0, :3]) == tuple(s.lut[-1, :3]) and tuple(px[0, 1, :3]) == tuple(s.lut[0, :3])
    assert px[1, 0, 3] == 0 and px[1, 1, 3] == 0  # zero hidden, NaN transparent
    assert s.rgba(np.array([0.0]), hide_zeros=False)[0, 3] == 255
    q = colour.make_scale(10, mode="linear", polarity="sequential")
    assert q.index(0) == 0 and q.index(5) == round((q.n - 1) / 2) and q.index(-3) == 0
    assert q.legend(64, 3).shape == (3, 64, 4) and q.ticks() == {"min": 0.0, "max": 10.0}
    with pytest.raises(ValueError):
        colour.make_scale(0)


def test_percentile_abs() -> None:
    assert colour.percentile_abs(np.array([np.nan, 0, -1, 2, 3, 4, 100]), 50) == 3
    assert colour.percentile_abs(np.array([np.nan, 0.0]), 99) == 1.0


def test_blend_semantics() -> None:
    b = colour.make_blend([1, 1, 1, 1], mode="linear")
    sw = b.swatches
    assert b.colour_of([1, 0, 0, 0])[:3] == sw["AMPHIBIA"] and b.colour_of([0.2, 0, 0, 0])[:3] == sw["AMPHIBIA"]
    assert b.colour_of([1, 1, 1, 1])[:3] == b.black and b.colour_of([0.3, 0.3, 0.3, 0.3])[:3] == b.black
    assert max(b.black) < 25
    assert b.colour_of([0.5, 0.5, 0, 0])[:3] == b.pairs["AMPHIBIA+AVES"]
    assert b.colour_of([0, 0, 0, 0])[3] == 0 and b.colour_of([-1, -1, -1, -1])[3] == 0
    assert b.colour_of([1, 0, 0, 0])[3] == 255 and b.colour_of([0.2, 0, 0, 0])[3] == round(255 * 0.2 ** 0.3)
    dom = b.colour_of([1, 0.5, 0.5, 0.5])
    assert dom[1] > 0.8 * sw["AMPHIBIA"][1]
    # all four gels multiply to a neutral floor
    prod = np.prod([b.inks[n] for n in b.names], axis=0)
    assert np.allclose(prod, b.floor)
    # the restore direction weights negative values
    r = colour.make_blend([1e-4] * 4, direction=-1)
    assert r.colour_of([-1e-4, 0, 0, 0])[3] == 255 and r.colour_of([1e-4, 0, 0, 0])[3] == 0


def test_blend_vectorised_matches_pixels() -> None:
    b = colour.make_blend([2, 3, 4, 5])
    rng = np.random.default_rng(1)
    stack = rng.uniform(-1, 5, size=(4, 6, 7)).astype("float32")
    stack[:, 0, 0] = np.nan
    img = b.rgba(stack)
    assert img.shape == (6, 7, 4) and img[0, 0, 3] == 0
    for r, c in ((1, 1), (2, 5), (5, 6)):
        assert tuple(img[r, c]) == b.colour_of(stack[:, r, c])


def test_png() -> None:
    img = colour.make_scale(1.0).rgba(np.linspace(-1, 1, 12).reshape(3, 4))
    png = colour.to_png(img)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and b"IHDR" in png and png.endswith(b"IEND\xaeB`\x82")
    with pytest.raises(ValueError):
        colour.to_png(img[..., :3])
