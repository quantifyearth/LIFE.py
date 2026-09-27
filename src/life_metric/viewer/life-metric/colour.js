/**
 * Colour scales and the taxa blend.
 *
 * A {@link Scale} maps one band through a lookup table: a diverging
 * blue-grey-red ramp for scores, where red means more extinctions, or a
 * sequential blue ramp for areas. A {@link Blend} paints the four taxonomic
 * classes at once as coloured gels multiplied together, so the hue shows the
 * dominant class, near-ties mix and darken, and four equal classes reach
 * black. Both write 8-bit RGBA with alpha 0 where there is nothing to show.
 */
/** Ramp stops per theme: a blue-grey-red diverging pair and a blue sequential ramp. */
export const PALETTES = {
    light: {
        diverging: ["#0d366b", "#1c5cab", "#6da7ec", "#f0efec", "#f1a29d", "#e34948", "#8f1d1d"],
        sequential: ["#b7d3f6", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    },
    dark: {
        diverging: ["#86b6ef", "#3987e5", "#1c5cab", "#383835", "#a12a2a", "#e34948", "#f1a29d"],
        sequential: ["#104281", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"],
    },
};
/** Gel transmittance per linear-RGB channel for each class: green, blue, orange, magenta. */
export const INKS = {
    AMPHIBIA: [0.12, 0.95, 0.22],
    AVES: [0.15, 0.5, 1.0],
    MAMMALIA: [1.0, 0.5, 0.06],
    REPTILIA: [0.95, 0.12, 0.9],
};
// --- colour space --------------------------------------------------------------
function srgbToLinear(c) {
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}
/** Encode linear light in [0, 1] as an 8-bit sRGB channel. */
export function linearToSrgb8(c) {
    const x = Math.min(1, Math.max(0, c));
    const v = x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055;
    return Math.max(0, Math.min(255, Math.round(v * 255)));
}
export function hexToOklab(hex) {
    const n = parseInt(hex.replace("#", ""), 16);
    const r = srgbToLinear(((n >> 16) & 255) / 255), g = srgbToLinear(((n >> 8) & 255) / 255), b = srgbToLinear((n & 255) / 255);
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    return [
        0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
    ];
}
export function oklabToRgb8([L, a, b]) {
    const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
    const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
    const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
    return [
        linearToSrgb8(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
        linearToSrgb8(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
        linearToSrgb8(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
    ];
}
/** Interpolate hex stops in OKLab into an RGBA lookup table of `n` entries (4 bytes each). */
export function rampLut(stops, n = 512) {
    if (stops.length < 2 || !Number.isInteger(n) || n < 2)
        throw new RangeError("need at least two stops and two lookup entries");
    const labs = stops.map(hexToOklab);
    const lut = new Uint8ClampedArray(n * 4);
    for (let i = 0; i < n; i++) {
        const t = (i / (n - 1)) * (labs.length - 1);
        const k = Math.min(Math.floor(t), labs.length - 2), u = t - k;
        const a = labs[k], b = labs[k + 1];
        const [r, g, bl] = oklabToRgb8([a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u]);
        lut.set([r, g, bl, 255], i * 4);
    }
    return lut;
}
// --- single-band scales ------------------------------------------------------------
/** The `p`-th percentile of `|v|` over finite non-zero values, or 1 if there are none. */
export function percentileAbs(values, p) {
    if (!Number.isFinite(p) || p < 0 || p > 100)
        throw new RangeError("percentile must be between 0 and 100");
    const a = [];
    for (let i = 0; i < values.length; i++) {
        const v = values[i];
        if (Number.isFinite(v) && v !== 0)
            a.push(Math.abs(v));
    }
    if (a.length === 0)
        return 1;
    a.sort((x, y) => x - y);
    return a[Math.min(a.length - 1, Math.floor((p / 100) * a.length))];
}
/** Build a {@link Scale} with its lookup table. */
export function makeScale({ vmax, mode = "log", polarity = "diverging", theme = "light", n = 512 }) {
    if (!(vmax > 0))
        throw new RangeError("vmax must be positive");
    const stops = PALETTES[theme][polarity];
    const lut = rampLut(stops, n);
    const lin = vmax / 1000, logMax = Math.log10(1 + vmax / lin);
    const normalise = (v) => {
        const a = Math.abs(v);
        if (!Number.isFinite(a))
            return 0;
        return Math.min(1, mode === "log" ? Math.log10(1 + a / lin) / logMax : a / vmax);
    };
    const index = polarity === "diverging"
        ? (v) => Math.round(((Math.sign(v) * normalise(v) + 1) / 2) * (n - 1))
        : (v) => Math.round((v > 0 ? normalise(v) : 0) * (n - 1));
    const rgba = (v, hideZeros = true) => {
        if (!Number.isFinite(v) || (hideZeros && v === 0))
            return [0, 0, 0, 0];
        const k = index(v) * 4;
        return [lut[k], lut[k + 1], lut[k + 2], 255];
    };
    return {
        mode, vmax, polarity, theme, n, lut, stops, normalise, index, rgba,
        render(values, hideZeros = true) {
            const out = new Uint8ClampedArray(values.length * 4);
            for (let i = 0; i < values.length; i++) {
                const v = values[i];
                if (!Number.isFinite(v) || (hideZeros && v === 0))
                    continue;
                const k = index(v) * 4, o = i * 4;
                out[o] = lut[k];
                out[o + 1] = lut[k + 1];
                out[o + 2] = lut[k + 2];
                out[o + 3] = 255;
            }
            return out;
        },
        legend(width = 256) {
            const out = new Uint8ClampedArray(width * 4);
            for (let i = 0; i < width; i++)
                out.set(lut.subarray(Math.round((i / (width - 1)) * (n - 1)) * 4, Math.round((i / (width - 1)) * (n - 1)) * 4 + 4), i * 4);
            return out;
        },
        ticks: () => (polarity === "diverging" ? { min: -vmax, mid: 0, max: vmax } : { min: 0, max: vmax }),
    };
}
// --- taxa blend ----------------------------------------------------------------------
/** Rescale gel absorbances per channel so all gels together multiply to `floor`. */
export function normaliseInks(inks, floor = 0.006) {
    const names = Object.keys(inks);
    const out = Object.fromEntries(names.map((n) => [n, [0, 0, 0]]));
    for (let ch = 0; ch < 3; ch++) {
        const total = names.reduce((s, n) => s - Math.log(inks[n][ch]), 0);
        const k = -Math.log(floor) / total;
        for (const n of names)
            out[n][ch] = inks[n][ch] ** k;
    }
    return out;
}
/** Build a {@link Blend}. */
export function makeBlend({ vmaxes, mode = "log", direction = 1, names = ["AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA"], contrast = 4, alpha = 0.3, floor = 0.006 }) {
    if (vmaxes.length !== names.length)
        throw new RangeError(`need one vmax per class: ${vmaxes.length} for ${names.join(", ")}`);
    if (vmaxes.some((v) => !(v > 0)))
        throw new RangeError("every vmax must be positive");
    const inks = normaliseInks(Object.fromEntries(names.map((n) => [n, INKS[n] ?? (() => { throw new Error(`no ink for ${n}`); })()])), floor);
    const steps = 256;
    const tables = names.map((n) => {
        const t = new Float32Array(steps * 3);
        for (let q = 0; q < steps; q++)
            for (let ch = 0; ch < 3; ch++)
                t[q * 3 + ch] = inks[n][ch] ** (q / (steps - 1));
        return t;
    });
    const norms = vmaxes.map((vmax) => {
        const lin = vmax / 1000, logMax = Math.log10(1 + vmax / lin);
        return (v) => {
            if (!(v > 0))
                return 0;
            const t = mode === "log" ? Math.log10(1 + v / lin) / logMax : v / vmax;
            return t >= 1 ? 1 : t;
        };
    });
    const gamma = new Uint8ClampedArray(4097);
    for (let i = 0; i <= 4096; i++)
        gamma[i] = linearToSrgb8(i / 4096);
    const toRgb = (lin) => [linearToSrgb8(lin[0]), linearToSrgb8(lin[1]), linearToSrgb8(lin[2])];
    const swatches = Object.fromEntries(names.map((n) => [n, toRgb(inks[n])]));
    const pairs = {};
    for (let i = 0; i < names.length; i++)
        for (let j = i + 1; j < names.length; j++)
            pairs[`${names[i]}+${names[j]}`] = toRgb(inks[names[i]].map((v, ch) => v * inks[names[j]][ch]));
    const w = new Float64Array(names.length);
    const weights = (values) => {
        const out = new Float64Array(names.length);
        for (let i = 0; i < names.length; i++)
            out[i] = norms[i](direction * (values[i] ?? NaN));
        return out;
    };
    const paint = (values, out, o) => {
        let wmax = 0;
        for (let i = 0; i < names.length; i++) {
            w[i] = norms[i](direction * (values[i] ?? NaN));
            if (w[i] > wmax)
                wmax = w[i];
        }
        if (wmax <= 0)
            return;
        let r = 1, g = 1, b = 1;
        for (let i = 0; i < names.length; i++) {
            if (w[i] <= 0)
                continue;
            const q = Math.round((w[i] / wmax) ** contrast * (steps - 1)) * 3, t = tables[i];
            r *= t[q];
            g *= t[q + 1];
            b *= t[q + 2];
        }
        out[o] = gamma[Math.round(r * 4096)];
        out[o + 1] = gamma[Math.round(g * 4096)];
        out[o + 2] = gamma[Math.round(b * 4096)];
        out[o + 3] = Math.round(255 * wmax ** alpha);
    };
    return {
        names, mode, vmaxes, direction, contrast, alpha, floor, inks, swatches, pairs, black: toRgb([floor, floor, floor]),
        weights, paint,
        rgba(values) {
            const px = new Uint8ClampedArray(4);
            paint(values, px, 0);
            return [px[0], px[1], px[2], px[3]];
        },
        render(bands, size) {
            const out = new Uint8ClampedArray(size * 4);
            const values = new Float64Array(names.length);
            for (let p = 0; p < size; p++) {
                for (let i = 0; i < names.length; i++)
                    values[i] = bands[i * size + p];
                paint(values, out, p * 4);
            }
            return out;
        },
    };
}
//# sourceMappingURL=colour.js.map