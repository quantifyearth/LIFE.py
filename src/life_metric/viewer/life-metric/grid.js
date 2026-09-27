/** Grid arithmetic shared by every level of a store. */
const EPS = 1e-9;
/** Build a bounding box, checking that the edges are ordered and in range. */
export function bbox(west, south, east, north) {
    if (!(-180 <= west && west < east && east <= 180))
        throw new RangeError(`longitudes must satisfy -180 <= west < east <= 180, got ${west}, ${east}`);
    if (!(-90 <= south && south < north && north <= 90))
        throw new RangeError(`latitudes must satisfy -90 <= south < north <= 90, got ${south}, ${north}`);
    return { west, south, east, north };
}
/**
 * A regular latitude-longitude grid in EPSG:4326.
 *
 * Rows run from the top edge `lat0` southwards and columns run from the
 * left edge `lon0` eastwards, both in steps of `res` degrees. Pixel centres
 * sit half a step inside each edge.
 */
export class Grid {
    width;
    height;
    res;
    lon0;
    lat0;
    constructor(width, height, res, lon0 = -180, lat0 = 90) {
        this.width = width;
        this.height = height;
        this.res = res;
        this.lon0 = lon0;
        this.lat0 = lat0;
    }
    /** The GDAL geotransform `[x0, dx, 0, y0, 0, -dy]`. */
    get transform() {
        return [this.lon0, this.res, 0, this.lat0, 0, -this.res];
    }
    /** The outer edges of the grid. */
    get bounds() {
        return { west: this.lon0, south: this.lat0 - this.height * this.res, east: this.lon0 + this.width * this.res, north: this.lat0 };
    }
    /** Pixel-centre latitude of every row, north to south. */
    latitudes() {
        return Float64Array.from({ length: this.height }, (_, i) => this.lat0 - (i + 0.5) * this.res);
    }
    /** Pixel-centre longitude of every column, west to east. */
    longitudes() {
        return Float64Array.from({ length: this.width }, (_, j) => this.lon0 + (j + 0.5) * this.res);
    }
    /** Row containing `lat`, or -1 when it falls off the grid. */
    row(lat) {
        const r = Math.floor((this.lat0 - lat) / this.res + EPS);
        return r >= 0 && r < this.height ? r : -1;
    }
    /** Column containing `lon`, wrapping around the antimeridian. */
    col(lon) {
        const c = Math.floor((lon - this.lon0) / this.res + EPS);
        return ((c % this.width) + this.width) % this.width;
    }
    /** The smallest window covering `box`, clipped to the grid. Throws when they do not overlap. */
    window(box) {
        const row0 = Math.max(0, Math.floor((this.lat0 - box.north) / this.res + EPS));
        const row1 = Math.min(this.height, Math.ceil((this.lat0 - box.south) / this.res - EPS));
        const col0 = Math.max(0, Math.floor((box.west - this.lon0) / this.res + EPS));
        const col1 = Math.min(this.width, Math.ceil((box.east - this.lon0) / this.res - EPS));
        if (row1 <= row0 || col1 <= col0)
            throw new RangeError(`box does not overlap the grid`);
        return { row0, row1, col0, col1 };
    }
    /** The grid of the pixels inside `w`. */
    sub(w) {
        return new Grid(w.col1 - w.col0, w.row1 - w.row0, this.res, this.lon0 + w.col0 * this.res, this.lat0 - w.row0 * this.res);
    }
}
//# sourceMappingURL=grid.js.map