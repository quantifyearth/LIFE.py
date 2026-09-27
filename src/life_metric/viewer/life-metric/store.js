/**
 * Open a store and read its layers. Every byte comes through zarrita.
 *
 * A store is a Zarr group whose root attributes describe the dataset and
 * whose `multiscales` layout lists its resolution levels. Everything a reader
 * needs to know, from what a value means to which scenarios and species
 * groups exist, is read from those attributes, so the objects here describe
 * themselves.
 */
import * as zarr from "zarrita";
import { Grid } from "./grid.js";
/** v1.01 fallback names; use `store.scenarios` for the opened version. */
export const SCENARIOS = ["arable", "restore"];
/** v1.01 fallback curves; use `store.curves` for the opened version. */
export const CURVES = ["0.1", "0.25", "0.5", "1.0", "gompertz"];
export const TAXA = ["all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA"];
/** The published catalogue: `<catalogue>/versions.json` lists releases and `<catalogue>/v<version>` is a store. */
export const DEFAULT_CATALOGUE = "https://data.source.coop/tessera/life";
/** The published v1.01 store, opened when {@link LifeStore.open} is given no source. */
export const DEFAULT_STORE = `${DEFAULT_CATALOGUE}/v1.01`;
/**
 * Read the levels of a zarr-conventions `multiscales` layout.
 *
 * A level's factor is the product of `transform.scale` along its
 * `derived_from` chain; its grid comes from `spatial:transform` and
 * `spatial:shape`, or from `fallback` scaled by the factor.
 */
export function parseLayout(layout, fallback) {
    const factors = new Map();
    const levels = new Map();
    for (const e of layout) {
        const parent = e.derived_from !== undefined ? factors.get(e.derived_from) ?? 1 : 1;
        const factor = Math.round(parent * (e.transform?.scale?.[0] ?? 1));
        factors.set(e.asset, factor);
        const st = e["spatial:transform"], shape = e["spatial:shape"];
        let grid;
        if (st && shape)
            grid = new Grid(shape[1], shape[0], st[0], st[2], st[5]);
        else if (fallback)
            grid = new Grid(Math.ceil(fallback.width / factor), Math.ceil(fallback.height / factor), fallback.res * factor, fallback.lon0, fallback.lat0);
        else
            throw new Error(`level ${e.asset} has no spatial:transform and no fallback grid`);
        levels.set(factor, { factor, path: e.asset, grid, ...(e.resampling_method !== undefined && { resamplingMethod: e.resampling_method }) });
    }
    return levels;
}
function makeRaster(data, grid, bands, layer, level) {
    const size = grid.width * grid.height;
    return {
        data, grid, bands, layer, level,
        band(name) {
            const i = bands.indexOf(name);
            if (i < 0)
                throw new Error(`raster holds ${bands.join(", ")}, not ${name}`);
            return data.subarray(i * size, (i + 1) * size);
        },
    };
}
/**
 * One layer of a store: a score layer for a scenario and curve, or an area
 * layer.
 *
 * A score layer holds one band per species group and gives, per pixel, the
 * change in the expected number of extinctions per km² of land changed. An
 * area layer holds one band giving the area of land that changes. `units`,
 * `longName` and `description` say so in the store's own words. Reads accept
 * a `level`: 1 is the base grid and each higher factor an overview whose
 * pixels average the finite pixels beneath them.
 */
export class Layer {
    store;
    name;
    scenario;
    curve;
    kind;
    attrs;
    bands;
    units;
    longName;
    description;
    fillValue;
    statistics;
    arrays = new Map();
    constructor(store, name, scenario, curve, kind, attrs, base) {
        this.store = store;
        this.name = name;
        this.scenario = scenario;
        this.curve = curve;
        this.kind = kind;
        this.attrs = attrs;
        this.arrays.set(1, Promise.resolve(base));
        const labels = (attrs.taxon_labels ?? attrs.source_bands);
        this.bands = kind === "area" ? ["area"] : labels ?? Object.keys(store.taxa);
        this.units = String(attrs.units ?? "");
        this.longName = String(attrs.long_name ?? name);
        this.description = String(attrs.description ?? "");
        const fv = base.fillValue;
        this.fillValue = typeof fv === "number" ? fv : NaN;
        this.statistics = attrs.statistics ?? {};
    }
    /** The store's description of this layer's scenario. */
    get scenarioDescription() {
        return this.store.scenarios[this.scenario] ?? "";
    }
    /** The store's description of this layer's curve, or "" for an area layer. */
    get curveDescription() {
        return this.curve === null ? "" : this.store.curves[this.curve] ?? "";
    }
    /** One plain-language sentence saying what the layer holds. */
    get summary() {
        if (this.kind === "area")
            return `${this.name}: area of land that changes in each pixel (${this.units}) under ${this.scenarioDescription || this.scenario}.`;
        return `${this.name}: change in expected extinctions per km² of land changed (${this.units}) under ${this.scenarioDescription || this.scenario}, with ${this.curveDescription || this.curve}; bands ${this.bands.join(", ")}.`;
    }
    /** The zarrita array of this layer at `level`. */
    array(level = 1) {
        let p = this.arrays.get(level);
        if (!p) {
            p = this.store.arrayAt(this.store.path(level, this.name));
            this.arrays.set(level, p);
        }
        return p;
    }
    /** The array shape at `level`. */
    async shape(level = 1) {
        return (await this.array(level)).shape;
    }
    /** The grid of the layer at `level`. */
    grid(level = 1) {
        return this.store.levelGrid(level);
    }
    /** The band index of `taxon`; throws if the layer lacks it. */
    bandIndex(taxon) {
        const i = this.bands.indexOf(taxon);
        if (i < 0)
            throw new Error(`${this.name} has bands ${this.bands.join(", ")}, not ${taxon}`);
        return i;
    }
    /**
     * Read one band, or every band when `taxon` is null, inside a region.
     *
     * The region is a bounding box in degrees, a window of rows and columns,
     * or, with neither, the whole level.
     */
    async read(opts = {}) {
        const level = opts.level ?? 1;
        const arr = await this.array(level);
        const grid = await this.grid(level);
        if (opts.bbox && opts.window)
            throw new Error("give bbox or window, not both");
        const win = opts.window ?? (opts.bbox ? grid.window(opts.bbox) : { row0: 0, row1: grid.height, col0: 0, col1: grid.width });
        if (![win.row0, win.row1, win.col0, win.col1].every(Number.isInteger) ||
            win.row0 < 0 || win.row0 >= win.row1 || win.row1 > grid.height ||
            win.col0 < 0 || win.col0 >= win.col1 || win.col1 > grid.width) {
            throw new RangeError(`window must be a nonempty block inside the ${grid.height} x ${grid.width} grid`);
        }
        const rows = zarr.slice(win.row0, win.row1), cols = zarr.slice(win.col0, win.col1);
        const taxon = opts.taxon === undefined ? "all" : opts.taxon;
        if (arr.shape.length === 2) {
            const out = await zarr.get(arr, [rows, cols]);
            return makeRaster(out.data, grid.sub(win), this.bands, this.name, level);
        }
        if (taxon === null) {
            const out = await zarr.get(arr, [null, rows, cols]);
            return makeRaster(out.data, grid.sub(win), this.bands, this.name, level);
        }
        const b = this.kind === "area" ? 0 : this.bandIndex(taxon);
        const out = await zarr.get(arr, [b, rows, cols]);
        return makeRaster(out.data, grid.sub(win), [taxon], this.name, level);
    }
    /** The value at a point, NaN off the grid or where there is no data. */
    async value(lat, lon, taxon = "all", level = 1) {
        const v = await this.sample([[lat, lon]], taxon, level);
        return v[0];
    }
    /**
     * The value at each `[lat, lon]` point, NaN off the grid or where there is
     * no data. Points sharing a chunk are served from one chunk read.
     */
    async sample(points, taxon = "all", level = 1) {
        const arr = await this.array(level);
        const grid = await this.grid(level);
        const out = (arr.dtype === "float64" ? new Float64Array(points.length) : new Float32Array(points.length)).fill(NaN);
        const [ch, cw] = arr.chunks.slice(-2);
        const b = arr.shape.length === 2 ? -1 : this.kind === "area" ? 0 : this.bandIndex(taxon);
        const byChunk = new Map();
        const rows = new Int32Array(points.length), cols = new Int32Array(points.length);
        points.forEach(([lat, lon], i) => {
            if (!Number.isFinite(lat) || !Number.isFinite(lon))
                return;
            const r = grid.row(lat);
            if (r < 0)
                return;
            rows[i] = r;
            cols[i] = grid.col(lon);
            const key = `${Math.floor(r / ch)}/${Math.floor(cols[i] / cw)}`;
            (byChunk.get(key) ?? byChunk.set(key, []).get(key)).push(i);
        });
        await Promise.all([...byChunk].map(async ([key, idx]) => {
            const [ci, cj] = key.split("/").map(Number);
            const chunk = await arr.getChunk(b < 0 ? [ci, cj] : [b, ci, cj]);
            for (const i of idx)
                out[i] = chunk.data[(rows[i] - ci * ch) * cw + (cols[i] - cj * cw)];
        }));
        return out;
    }
}
/**
 * A LIFE store: what it is, its resolution levels and its layers.
 *
 * `info` says what the dataset is; `scenarios`, `curves` and `taxa` map each
 * name to the store's description of it; `dataModel` explains array values;
 * `levels` lists the resolution levels
 * by reduction factor, 1 being the base grid. All of it is read from the
 * store's root attributes and `multiscales` layout, so a store from another
 * dataset version is described by its own contents.
 */
export class LifeStore {
    source;
    root;
    attrs;
    listing;
    version;
    info;
    /** Scenario name to the store's description of it. */
    scenarios;
    /** Curve name to the store's description of it. */
    curves;
    /** Species group name to the store's description of it. */
    taxa;
    /** The store's explanation of array names, values and overview use. */
    dataModel;
    grid;
    levels;
    levelMap;
    layerCache = new Map();
    arrayCache = new Map();
    constructor(source, root, attrs, listing) {
        this.source = source;
        this.root = root;
        this.attrs = attrs;
        this.listing = listing;
        this.version = String(attrs.version ?? "unknown");
        this.info = {
            title: String(attrs.title ?? "LIFE"), summary: String(attrs.summary ?? ""), version: this.version,
            ...(typeof attrs.source_doi === "string" && { doi: attrs.source_doi }),
            ...(typeof attrs.concept_doi === "string" && { conceptDoi: attrs.concept_doi }),
            ...(typeof attrs.references === "string" && { citation: attrs.references }),
            ...(typeof attrs.source_url === "string" && { sourceUrl: attrs.source_url }),
            ...(typeof attrs.terms_of_reference === "string" && { termsOfUse: attrs.terms_of_reference }),
        };
        this.scenarios = descriptions(attrs.scenarios, SCENARIOS);
        this.curves = descriptions(attrs.curves, CURVES);
        this.taxa = descriptions(attrs.taxa, TAXA);
        this.dataModel = attrs.data_model && typeof attrs.data_model === "object" && !Array.isArray(attrs.data_model)
            ? Object.fromEntries(Object.entries(attrs.data_model).map(([k, v]) => [k, String(v)])) : {};
        const layout = attrs.multiscales?.layout;
        if (!layout)
            throw new Error(`${source}: the root group has no multiscales layout`);
        this.levelMap = parseLayout(layout);
        const base = this.levelMap.get(1);
        if (!base)
            throw new Error(`${source}: the multiscales layout has no base level`);
        this.grid = base.grid;
        this.levels = [...this.levelMap.keys()].sort((a, b) => a - b);
    }
    /** The level with reduction `factor`; throws if absent. */
    level(factor) {
        const l = this.levelMap.get(factor);
        if (!l)
            throw new RangeError(`level ${factor} is not in the store; have ${this.levels.join(", ")}`);
        return l;
    }
    /** The store path of array `name` at `level`. */
    path(level, name) {
        const base = this.level(level).path;
        return base ? `${base}/${name}` : name;
    }
    /**
     * Open a store from a URL or from any store zarrita can read; with no
     * argument, the published v1.01 store on source.coop.
     *
     * A URL is fetched through zarrita's `FetchStore`, with its bytes cached
     * unless `cache` is false, and its consolidated metadata is used to list
     * layers when present. A store object is used as given; wrap it with
     * zarrita's `withByteCaching` or `withConsolidatedMetadata` yourself if
     * you want those.
     */
    static async open(source = DEFAULT_STORE, opts = {}) {
        let store;
        let listing = null;
        if (typeof source === "string") {
            const base = new zarr.FetchStore(source);
            const cached = opts.cache === false ? base : zarr.withByteCaching(base);
            const maybe = await zarr.withMaybeConsolidatedMetadata(cached);
            if ("contents" in maybe)
                listing = new Set((await maybe.contents()).map((c) => c.path));
            store = maybe;
        }
        else {
            store = source;
            if ("contents" in source && typeof source.contents === "function") {
                listing = new Set((await source.contents()).map((c) => c.path));
            }
        }
        const root = zarr.root(store);
        const group = await zarr.open.v3(root, { kind: "group" });
        return new LifeStore(typeof source === "string" ? source : "store", root, group.attrs, listing);
    }
    /** Open a float32 or float64 array by path inside the store, once. */
    arrayAt(path) {
        let p = this.arrayCache.get(path);
        if (!p) {
            p = zarr.open.v3(this.root.resolve(path), { kind: "array" }).then((a) => {
                if (a.dtype !== "float32" && a.dtype !== "float64")
                    throw new Error(`${path} is ${a.dtype}, expected float32 or float64`);
                return a;
            });
            this.arrayCache.set(path, p);
        }
        return p;
    }
    has(path) {
        return this.listing === null || this.listing.has("/" + path);
    }
    /** The names of the layers present, score layers first. */
    layerNames() {
        const scenarios = Object.keys(this.scenarios), curves = Object.keys(this.curves);
        const names = scenarios.flatMap((s) => curves.map((c) => `${s}_${c}`)).concat(scenarios.map((s) => `${s}_area_changed`));
        return names.filter((n) => this.has(this.path(1, n)));
    }
    /** Every layer present in the store. */
    layers() {
        return Promise.all(this.layerNames().map((n) => this.get(n)));
    }
    /** The layer called `name`; rejects if absent. */
    get(name) {
        let p = this.layerCache.get(name);
        if (!p) {
            p = this.arrayAt(this.path(1, name)).then((arr) => {
                const attrs = arr.attrs;
                if (name.endsWith("_area_changed")) {
                    const scenario = typeof attrs.scenario === "string" ? attrs.scenario : name.slice(0, -"_area_changed".length);
                    return new Layer(this, name, scenario, null, "area", attrs, arr);
                }
                const scenario = typeof attrs.scenario === "string" ? attrs.scenario :
                    Object.keys(this.scenarios).sort((a, b) => b.length - a.length).find((s) => name.startsWith(`${s}_`)) ?? "";
                const curve = typeof attrs.curve === "string" ? attrs.curve : name.slice(scenario.length + 1);
                return new Layer(this, name, scenario, curve, "score", attrs, arr);
            });
            this.layerCache.set(name, p);
        }
        return p;
    }
    /** The score layer for a scenario and persistence curve. */
    layer(scenario, curve = "0.25") {
        return this.get(`${scenario}_${curve}`);
    }
    /** The area-changed layer for a scenario. */
    area(scenario) {
        return this.get(`${scenario}_area_changed`);
    }
    /** The grid of a level; level 1 is the base grid. */
    levelGrid(level) {
        return Promise.resolve(this.level(level).grid);
    }
    /** A plain-language summary of the store: what it is, its levels, scenarios, curves, groups and layers. */
    describe() {
        const list = (title, items) => [`${title}:`, ...Object.entries(items).map(([k, v]) => `  ${k.padEnd(10)} ${v}`)];
        return [
            `${this.info.title} (version ${this.version}) from ${this.source}`, this.info.summary, "",
            `grid ${this.grid.width} x ${this.grid.height} pixels at ${this.grid.res} degrees, levels ` +
                this.levels.map((f) => { const l = this.level(f); return `${f} (group ${l.path || "."}, ${l.grid.width} x ${l.grid.height})`; }).join(", "),
            ...list("scenarios", this.scenarios), ...list("curves", this.curves), ...list("species groups", this.taxa),
            ...(Object.keys(this.dataModel).length ? list("data model", this.dataModel) : []),
            `layers: ${this.layerNames().join(", ")}`,
            ...(this.info.termsOfUse ? ["", `terms of use: ${this.info.termsOfUse}`] : []),
        ].join("\n");
    }
}
function descriptions(v, fallback) {
    if (v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length) {
        return Object.fromEntries(Object.entries(v).map(([k, d]) => [k, String(d)]));
    }
    return Object.fromEntries(fallback.map((k) => [k, ""]));
}
//# sourceMappingURL=store.js.map