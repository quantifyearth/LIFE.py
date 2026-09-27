/** Paint Web Mercator map tiles from a layer, for MapLibre, Leaflet or any XYZ consumer. */
/** Pixel-centre longitudes of tile column `x` at zoom `z`. */
export function tileLons(x, z, size = 256) {
    const scale = 360 / (size * 2 ** z);
    return Float64Array.from({ length: size }, (_, i) => (x * size + i + 0.5) * scale - 180);
}
/** Pixel-centre latitudes of tile row `y` at zoom `z`. */
export function tileLats(y, z, size = 256) {
    const total = size * 2 ** z;
    return Float64Array.from({ length: size }, (_, j) => {
        const t = Math.PI * (1 - (2 * (y * size + j + 0.5)) / total);
        return (Math.atan(Math.sinh(t)) * 180) / Math.PI;
    });
}
/** The largest level whose pixel is no coarser than a tile pixel at zoom `z` and `latitude`; 1 when none is. */
export function pickLevel(z, levels, res, size = 256, latitude = 0) {
    const degPerPx = 360 / (size * 2 ** z) * Math.cos(latitude * Math.PI / 180);
    let best = 1;
    for (const f of levels)
        if (f * res <= degPerPx && f > best)
            best = f;
    return best;
}
/**
 * Paint one XYZ tile of `layer`.
 *
 * The overview level is chosen from the zoom, the covering window is read
 * in one request, and each tile pixel takes its nearest source pixel.
 */
export async function paintTile(layer, opts) {
    const size = opts.size ?? 256;
    if (!Number.isInteger(size) || size <= 0)
        throw new RangeError("tile size must be a positive integer");
    const lats = tileLats(opts.y, opts.z, size), lons = tileLons(opts.x, opts.z, size);
    const furthest = Math.max(Math.abs(lats[0]), Math.abs(lats[size - 1]));
    const level = opts.level ?? pickLevel(opts.z, layer.store.levels, layer.store.grid.res, size, furthest);
    const grid = await layer.grid(level);
    const rows = new Int32Array(size), cols = new Int32Array(size);
    let rmin = Infinity, rmax = -Infinity, cmin = Infinity, cmax = -Infinity;
    for (let j = 0; j < size; j++) {
        const r = grid.row(lats[j]);
        rows[j] = r;
        if (r >= 0) {
            rmin = Math.min(rmin, r);
            rmax = Math.max(rmax, r);
        }
    }
    const data = new Uint8ClampedArray(size * size * 4);
    if (rmin === Infinity)
        return { width: size, height: size, data };
    for (let i = 0; i < size; i++) {
        const c = Math.min(grid.width - 1, Math.max(0, Math.floor((lons[i] - grid.lon0) / grid.res + 1e-9)));
        cols[i] = c;
        cmin = Math.min(cmin, c);
        cmax = Math.max(cmax, c);
    }
    const window = { row0: rmin, row1: rmax + 1, col0: cmin, col1: cmax + 1 };
    const w = window.col1 - window.col0, h = window.row1 - window.row0;
    if (opts.blend) {
        const blend = opts.blend;
        const raster = await layer.read({ taxon: null, window, level });
        const bands = blend.names.map((n) => raster.band(n));
        const values = new Float64Array(bands.length);
        for (let j = 0; j < size; j++) {
            if (rows[j] < 0)
                continue;
            const rr = rows[j] - rmin;
            for (let i = 0; i < size; i++) {
                const idx = rr * w + (cols[i] - cmin);
                for (let k = 0; k < bands.length; k++)
                    values[k] = bands[k][idx];
                blend.paint(values, data, (j * size + i) * 4);
            }
        }
        return { width: size, height: size, data };
    }
    const scale = opts.scale;
    if (!scale)
        throw new Error("paintTile needs a scale or a blend");
    const hideZeros = opts.hideZeros ?? true;
    const raster = await layer.read({ taxon: opts.taxon ?? "all", window, level });
    const src = raster.data;
    if (src.length !== w * h)
        throw new Error("unexpected raster size");
    const { lut } = scale;
    for (let j = 0; j < size; j++) {
        if (rows[j] < 0)
            continue;
        const rr = rows[j] - rmin;
        for (let i = 0; i < size; i++) {
            const v = src[rr * w + (cols[i] - cmin)];
            if (!Number.isFinite(v) || (hideZeros && v === 0))
                continue;
            const k = scale.index(v) * 4, o = (j * size + i) * 4;
            data[o] = lut[k];
            data[o + 1] = lut[k + 1];
            data[o + 2] = lut[k + 2];
            data[o + 3] = 255;
        }
    }
    return { width: size, height: size, data };
}
//# sourceMappingURL=tiles.js.map