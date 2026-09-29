/** Access LIFE data through typed arrays, plain metadata, and GeoJSON. */
import { Catalogue } from "./catalogue.js";
import { bbox } from "./grid.js";
import { geometryBounds, mask, polygons } from "./geometry.js";
import { DEFAULT_CATALOGUE, DEFAULT_STORE, LifeStore } from "./store.js";
function placement(grid) {
    return { width: grid.width, height: grid.height, resolution: grid.res,
        bounds: [grid.bounds.west, grid.bounds.south, grid.bounds.east, grid.bounds.north],
        transform: [grid.res, 0, grid.lon0, 0, -grid.res, grid.lat0], crs: "EPSG:4326" };
}
function region(store, options) {
    if (!options || [options.bounds, options.window, options.geometry].filter((x) => x !== undefined).length !== 1) {
        throw new TypeError("give exactly one of bounds, window, or geometry");
    }
    const level = options.level ?? 1;
    const grid = store.level(level).grid;
    const shapes = options.geometry === undefined ? undefined : polygons(options.geometry);
    const bounds = shapes ? geometryBounds(shapes) : options.bounds;
    let window;
    if (bounds) {
        if (bounds.length !== 4)
            throw new RangeError("bounds must contain west, south, east, north");
        window = grid.window(bbox(...bounds));
    }
    else {
        const input = options.window;
        if (input.length !== 4 || !input.every(Number.isInteger) || input[0] >= input[2] || input[1] >= input[3]) {
            throw new RangeError("window must contain integer column start, row start, column stop, row stop");
        }
        window = { col0: Math.max(0, input[0]), row0: Math.max(0, input[1]),
            col1: Math.min(grid.width, input[2]), row1: Math.min(grid.height, input[3]) };
        if (window.col0 >= window.col1 || window.row0 >= window.row1)
            throw new RangeError("window does not overlap the store grid");
    }
    return { level, window, shapes };
}
/** Open the published v1.01 store, a URL, or a zarrita-readable store. Select a named release with options.version and no source. */
export async function open(source, options = {}) {
    options.signal?.throwIfAborted();
    if (source !== undefined && options.version !== undefined)
        throw new TypeError("give source or version, not both");
    if (options.version !== undefined) {
        source = (await new Catalogue(options.catalogue ?? DEFAULT_CATALOGUE, {
            fetchJson: async (url) => {
                const response = await (options.fetch ?? fetch)(new Request(url, options.signal ? { signal: options.signal } : {}));
                if (!response.ok)
                    throw new Error(`${url}: ${response.status}`);
                return response.json();
            },
        }).release(options.version)).url;
    }
    const store = await LifeStore.open(source ?? DEFAULT_STORE, options);
    const metadata = { ...store.info, ...placement(store.grid), source: store.source,
        scenarios: store.scenarios, curves: store.curves, taxa: store.taxa, dataModel: store.dataModel,
        levels: store.levels.map((factor) => {
            const level = store.level(factor);
            return { factor, ...placement(level.grid), ...(level.resamplingMethod && { resamplingMethod: level.resamplingMethod }) };
        }), layers: store.layerNames(), attributes: store.attrs };
    const client = {
        metadata,
        async layerMetadata(name, opts = {}) {
            const layer = await store.get(name, opts.signal);
            return { name: layer.name, kind: layer.kind, scenario: layer.scenario, curve: layer.curve,
                bands: layer.bands, units: layer.units, longName: layer.longName, description: layer.description,
                scenarioDescription: layer.scenarioDescription, curveDescription: layer.curveDescription,
                fillValue: layer.fillValue, statistics: layer.statistics, attributes: layer.attrs };
        },
        async read(name, opts) {
            opts?.signal?.throwIfAborted();
            const { level, window, shapes } = region(store, opts);
            const layer = await store.get(name, opts.signal);
            const result = await layer.read({ window, level, ...(opts.taxon !== undefined && { taxon: opts.taxon }),
                ...(opts.signal && { signal: opts.signal }) });
            opts.signal?.throwIfAborted();
            const raster = { ...placement(result.grid), data: result.data, bands: result.bands,
                layer: name, level, kind: layer.kind, units: layer.units, description: layer.description,
                source: metadata.source, version: metadata.version, nodata: layer.kind === "score" ? NaN : null,
                ...(metadata.citation && { citation: metadata.citation }), ...(metadata.termsOfUse && { termsOfUse: metadata.termsOfUse }) };
            return shapes || opts.masked ? { ...raster, valid: mask(raster, shapes, opts.signal) } : raster;
        },
        async sample(name, points, opts = {}) {
            opts.signal?.throwIfAborted();
            if (!points.every((xy) => xy.length === 2 && xy.every(Number.isFinite))) {
                throw new RangeError("points must be finite longitude, latitude pairs");
            }
            const layer = await store.get(name, opts.signal);
            const values = await layer.sample(points.map(([lon, lat]) => [lat, lon]), opts.taxon ?? "all", opts.level ?? 1, opts.signal);
            opts.signal?.throwIfAborted();
            return values;
        },
        async download(name, opts) {
            opts?.signal?.throwIfAborted();
            const { window } = region(store, opts);
            const layer = await store.get(name, opts.signal);
            const bands = opts.taxon === null && layer.kind === "score" ? layer.bands.length : 1;
            if ((window.row1 - window.row0) * (window.col1 - window.col0) * bands > 16_000_000) {
                throw new RangeError("the region is too large for one download; select a smaller region");
            }
            const raster = await client.read(name, opts);
            const { toGeoTIFF } = await import("./geotiff.js");
            return toGeoTIFF(raster, opts.signal ? { signal: opts.signal } : {});
        },
    };
    return client;
}
/** List catalogue releases as plain objects in version order. Requests accept an AbortSignal and custom fetch handler. */
export async function versions(catalogue = DEFAULT_CATALOGUE, options = {}) {
    options.signal?.throwIfAborted();
    const cat = new Catalogue(catalogue, { fetchJson: async (url) => {
            const response = await (options.fetch ?? fetch)(new Request(url, options.signal ? { signal: options.signal } : {}));
            if (!response.ok)
                throw new Error(`${url}: ${response.status}`);
            return response.json();
        } });
    const releases = await cat.releases();
    if (!releases.length)
        return [];
    const latest = (await cat.latest()).version;
    return releases.map((release) => ({ ...release, latest: release.version === latest }));
}
//# sourceMappingURL=client.js.map