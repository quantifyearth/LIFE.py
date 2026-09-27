"""Colour scales and the taxa blend, vectorised over numpy arrays.

Two ways to colour LIFE values are provided. A :class:`Scale` maps one band
through a lookup table: a diverging blue-grey-red ramp for scores, where red
means more extinctions, or a sequential blue ramp for areas. A :class:`Blend`
paints the four taxonomic classes at once as coloured gels multiplied
together, so the hue shows the dominant class, near-ties mix and darken, and
four equal classes reach black. Both return 8-bit RGBA with alpha 0 where
there is nothing to show, and :func:`to_png` encodes that without any
imaging dependency.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from typing import Literal, cast

import numpy as np
from numpy.typing import ArrayLike, NDArray

Mode = Literal["log", "linear"]
Polarity = Literal["diverging", "sequential"]
Theme = Literal["light", "dark"]

PALETTES: dict[str, dict[str, list[str]]] = {
    "light": {
        "diverging": ["#0d366b", "#1c5cab", "#6da7ec", "#f0efec", "#f1a29d", "#e34948", "#8f1d1d"],
        "sequential": ["#b7d3f6", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    },
    "dark": {
        "diverging": ["#86b6ef", "#3987e5", "#1c5cab", "#383835", "#a12a2a", "#e34948", "#f1a29d"],
        "sequential": ["#104281", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"],
    },
}
"""Ramp stops per theme: a blue-grey-red diverging pair and a blue sequential ramp."""

INKS: dict[str, tuple[float, float, float]] = {
    "AMPHIBIA": (0.12, 0.95, 0.22),
    "AVES": (0.15, 0.5, 1.0),
    "MAMMALIA": (1.0, 0.5, 0.06),
    "REPTILIA": (0.95, 0.12, 0.9),
}
"""Gel transmittance per linear-RGB channel for each class: green, blue, orange, magenta."""


# --- colour space -----------------------------------------------------------


def srgb_to_linear(c: NDArray[np.floating]) -> NDArray[np.float64]:
    """Decode sRGB channels in [0, 1] to linear light."""
    c = np.asarray(c, dtype="float64")
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb8(c: NDArray[np.floating]) -> NDArray[np.uint8]:
    """Encode linear light in [0, 1] as 8-bit sRGB."""
    c = np.clip(np.asarray(c, dtype="float64"), 0, 1)
    v = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)
    return np.clip(np.round(v * 255), 0, 255).astype("uint8")


def hex_to_oklab(hex_colour: str) -> NDArray[np.float64]:
    """Convert a hex sRGB colour to its OKLab coordinates."""
    n = int(hex_colour.lstrip("#"), 16)
    rgb = srgb_to_linear(np.array([(n >> 16) & 255, (n >> 8) & 255, n & 255]) / 255)
    l = np.cbrt(0.4122214708 * rgb[0] + 0.5363325363 * rgb[1] + 0.0514459929 * rgb[2])
    m = np.cbrt(0.2119034982 * rgb[0] + 0.6806995451 * rgb[1] + 0.1073969566 * rgb[2])
    s = np.cbrt(0.0883024619 * rgb[0] + 0.2817188376 * rgb[1] + 0.6299787005 * rgb[2])
    return np.array([
        0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
    ])


def oklab_to_rgb8(lab: NDArray[np.floating]) -> NDArray[np.uint8]:
    """Convert OKLab coordinates to 8-bit sRGB channels."""
    lab = np.asarray(lab, dtype="float64")
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3
    lin = np.stack([
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
    ], axis=-1)
    return linear_to_srgb8(lin)


def ramp_lut(stops: list[str], n: int = 512) -> NDArray[np.uint8]:
    """Interpolate hex stops in OKLab into an ``(n, 4)`` RGBA lookup table."""
    labs = np.array([hex_to_oklab(s) for s in stops])
    t = np.linspace(0, len(stops) - 1, n)
    k = np.minimum(np.floor(t).astype(int), len(stops) - 2)
    u = (t - k)[:, None]
    lab = labs[k] * (1 - u) + labs[k + 1] * u
    lut = np.full((n, 4), 255, dtype="uint8")
    lut[:, :3] = oklab_to_rgb8(lab)
    return lut


# --- single-band scales ---------------------------------------------------------


def percentile_abs(values: ArrayLike, p: float) -> float:
    """Return the ``p``-th percentile of ``|v|`` over finite non-zero values, or 1 if there are none."""
    v = np.asarray(values, dtype="float64").ravel()
    v = np.abs(v[np.isfinite(v) & (v != 0)])
    if v.size == 0:
        return 1.0
    v.sort()
    return float(v[min(v.size - 1, int(p / 100 * v.size))])


@dataclass(frozen=True)
class Scale:
    """A colour scale for one band.

    ``mode`` is ``"log"`` (symmetric log, linear below ``vmax / 1000``) or
    ``"linear"``; ``polarity`` is ``"diverging"`` (centred on zero) or
    ``"sequential"`` (from zero up); values beyond ``vmax`` clamp.
    """

    mode: Mode
    vmax: float
    polarity: Polarity
    theme: Theme = "light"
    lut: NDArray[np.uint8] = field(repr=False, default_factory=lambda: np.zeros((0, 4), dtype="uint8"))

    @property
    def n(self) -> int:
        """Number of entries in the colour lookup table."""
        return int(self.lut.shape[0])

    @property
    def stops(self) -> list[str]:
        """Palette stop colours selected by the scale's theme and polarity."""
        return PALETTES[self.theme][self.polarity]

    def normalise(self, values: ArrayLike) -> NDArray[np.float64]:
        """Return ``|v|`` stretched to [0, 1] by the scale's mode."""
        a = np.abs(np.asarray(values, dtype="float64"))
        if self.mode == "log":
            lin = self.vmax / 1000
            t = np.log10(1 + a / lin) / np.log10(1 + self.vmax / lin)
        else:
            t = a / self.vmax
        return cast(NDArray[np.float64], np.clip(np.nan_to_num(t, nan=0.0), 0, 1))

    def index(self, values: ArrayLike) -> NDArray[np.int64]:
        """Return the lookup-table index of each value."""
        v = np.nan_to_num(np.asarray(values, dtype="float64"), nan=0.0)
        t = self.normalise(v)
        if self.polarity == "diverging":
            pos = (np.sign(v) * t + 1) / 2
        else:
            pos = np.where(v > 0, t, 0.0)
        return cast(NDArray[np.int64], np.round(pos * (self.n - 1)).astype("int64"))

    def rgba(self, values: ArrayLike, *, hide_zeros: bool = True) -> NDArray[np.uint8]:
        """Colour an array of values as ``(..., 4)`` RGBA; NaN, and zero when hidden, get alpha 0."""
        v = np.asarray(values, dtype="float64")
        out = self.lut[self.index(v)].copy()
        blank = ~np.isfinite(v)
        if hide_zeros:
            blank |= v == 0
        out[blank, 3] = 0
        return out

    def legend(self, width: int = 256, height: int = 1) -> NDArray[np.uint8]:
        """Return a ``(height, width, 4)`` gradient bar from the low end to the high end."""
        idx = np.round(np.linspace(0, self.n - 1, width)).astype("int64")
        row = self.lut[idx]
        return np.repeat(row[None, :, :], height, axis=0)

    def ticks(self) -> dict[str, float]:
        """Return the values at the ends and, for a diverging scale, the centre."""
        if self.polarity == "diverging":
            return {"min": -self.vmax, "mid": 0.0, "max": self.vmax}
        return {"min": 0.0, "max": self.vmax}


def make_scale(vmax: float, *, mode: Mode = "log", polarity: Polarity = "diverging",
               theme: Theme = "light", n: int = 512) -> Scale:
    """Build a :class:`Scale` with its lookup table."""
    if not vmax > 0:
        raise ValueError("vmax must be positive")
    return Scale(mode, float(vmax), polarity, theme, ramp_lut(PALETTES[theme][polarity], n))


# --- taxa blend -------------------------------------------------------------------


def _rgb(lin: NDArray[np.floating]) -> tuple[int, int, int]:
    r, g, b = (int(x) for x in linear_to_srgb8(lin))
    return r, g, b


def normalise_inks(inks: dict[str, tuple[float, float, float]], floor: float = 0.006) -> dict[str, NDArray[np.float64]]:
    """Rescale gel absorbances per channel so all gels together multiply to ``floor``."""
    names = list(inks)
    arr = np.array([inks[n] for n in names], dtype="float64")
    total = -np.log(arr).sum(axis=0)
    k = -np.log(floor) / total
    scaled = arr ** k
    return {n: scaled[i] for i, n in enumerate(names)}


@dataclass(frozen=True)
class Blend:
    """A multiplicative blend of the four taxonomic classes.

    Each class's value is stretched to its own range ``vmaxes[i]`` in the
    scale's ``mode``, in the direction ``direction`` (+1 counts increases in
    extinctions, -1 decreases). The class with the largest weight applies its
    gel in full; every other class applies its gel raised to
    ``(weight / largest) ** contrast``. Opacity is ``largest ** alpha``.
    """

    names: tuple[str, ...]
    mode: Mode
    vmaxes: tuple[float, ...]
    direction: int = 1
    contrast: float = 4.0
    alpha: float = 0.3
    floor: float = 0.006
    inks: dict[str, NDArray[np.float64]] = field(default_factory=dict, repr=False)

    @property
    def swatches(self) -> dict[str, tuple[int, int, int]]:
        """Return the pure colour of each class."""
        return {n: _rgb(self.inks[n]) for n in self.names}

    @property
    def pairs(self) -> dict[str, tuple[int, int, int]]:
        """Return the colour of each equal pair of classes, keyed ``"A+B"``."""
        out: dict[str, tuple[int, int, int]] = {}
        for i, a in enumerate(self.names):
            for b in self.names[i + 1:]:
                out[f"{a}+{b}"] = _rgb(self.inks[a] * self.inks[b])
        return out

    @property
    def black(self) -> tuple[int, int, int]:
        """Return the colour reached when all classes are equal."""
        return _rgb(np.full(3, self.floor))

    def weights(self, stack: ArrayLike) -> NDArray[np.float64]:
        """Return each class's weight in [0, 1]; ``stack`` is ``(classes, ...)``."""
        v = self.direction * np.asarray(stack, dtype="float64")
        v = np.where(np.isfinite(v) & (v > 0), v, 0.0)
        out = np.empty_like(v)
        for i, vmax in enumerate(self.vmaxes):
            if self.mode == "log":
                lin = vmax / 1000
                t = np.log10(1 + v[i] / lin) / np.log10(1 + vmax / lin)
            else:
                t = v[i] / vmax
            out[i] = np.clip(t, 0, 1)
        return out

    def rgba(self, stack: ArrayLike) -> NDArray[np.uint8]:
        """Colour a ``(classes, ...)`` stack as ``(..., 4)`` RGBA."""
        w = self.weights(stack)
        wmax = w.max(axis=0)
        safe = np.where(wmax > 0, wmax, 1.0)
        rel = (w / safe) ** self.contrast
        log_ink = np.array([np.log(self.inks[n]) for n in self.names])  # (classes, 3)
        lin = np.exp(np.tensordot(rel, log_ink, axes=(0, 0)))  # (..., 3)
        out = np.empty(wmax.shape + (4,), dtype="uint8")
        out[..., :3] = linear_to_srgb8(lin)
        out[..., 3] = np.where(wmax > 0, np.round(255 * wmax ** self.alpha), 0).astype("uint8")
        return out

    def colour_of(self, values: ArrayLike) -> tuple[int, int, int, int]:
        """Return the RGBA of one pixel given its class values."""
        px = self.rgba(np.asarray(values, dtype="float64")[:, None])[0]
        return int(px[0]), int(px[1]), int(px[2]), int(px[3])


def make_blend(vmaxes: ArrayLike, *, mode: Mode = "log", direction: int = 1,
               names: tuple[str, ...] = ("AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA"),
               contrast: float = 4.0, alpha: float = 0.3, floor: float = 0.006) -> Blend:
    """Build a :class:`Blend`; ``vmaxes`` gives one range per class in ``names``."""
    vm = tuple(float(v) for v in np.asarray(vmaxes, dtype="float64"))
    if len(vm) != len(names):
        raise ValueError(f"need one vmax per class: {len(vm)} for {names}")
    if any(not v > 0 for v in vm):
        raise ValueError("every vmax must be positive")
    inks = normalise_inks({n: INKS[n] for n in names}, floor)
    return Blend(tuple(names), mode, vm, direction, contrast, alpha, floor, inks)


# --- output -------------------------------------------------------------------------


def to_png(rgba: NDArray[np.uint8]) -> bytes:
    """Encode a ``(height, width, 4)`` RGBA array as a PNG file."""
    a = np.ascontiguousarray(rgba, dtype="uint8")
    if a.ndim != 3 or a.shape[2] != 4:
        raise ValueError("expected (height, width, 4) uint8")
    h, w = a.shape[:2]
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
