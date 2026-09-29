/**
 * Show a layer on a MapLibre GL map.
 *
 * A {@link LifeProtocol} registers a custom `life://` tile protocol with
 * MapLibre and paints each requested tile with {@link paintTile}. A
 * {@link LifeMapLayer} adds a raster source and layer for one tile spec to a
 * map, and can swap the spec, change its opacity, or remove itself. Neither
 * imports maplibre-gl: pass the `maplibregl` module and the map in.
 */
import { paintTile } from "./tiles.js";
/** Parse `life://<spec>/<z>/<x>/<y>`. */
export function parseTileUrl(url, protocol = "life") {
    const m = url.match(new RegExp(`^${protocol}://([^/]+)/(\\d+)/(\\d+)/(\\d+)$`));
    if (!m)
        throw new Error(`not a ${protocol}:// tile url: ${url}`);
    return { id: m[1], z: Number(m[2]), x: Number(m[3]), y: Number(m[4]) };
}
/** Turn a painted tile into an `ImageBitmap`, which MapLibre accepts as tile data. Browser only. */
export function toImageBitmap(image) {
    return createImageBitmap(new ImageData(image.data, image.width, image.height));
}
/**
 * A custom tile protocol that paints LIFE tiles on demand.
 *
 * Register specs to obtain tile URL templates, install the protocol on the
 * `maplibregl` module once, and MapLibre will call back for each tile.
 */
export class LifeProtocol {
    name;
    specs = new Map();
    next = 1;
    constructor(name = "life") {
        this.name = name;
    }
    /** Register the protocol with MapLibre. Call once per page. */
    install(maplibre) {
        maplibre.addProtocol(this.name, this.handler);
        return this;
    }
    /** Remove the protocol from MapLibre. */
    uninstall(maplibre) {
        maplibre.removeProtocol?.(this.name);
    }
    /** The handler MapLibre calls for each tile. */
    handler = async ({ url }, abortController) => {
        abortController.signal.throwIfAborted();
        const { id, z, x, y } = parseTileUrl(url, this.name);
        const spec = this.specs.get(id);
        const size = spec?.tileSize ?? 256;
        if (!spec)
            return { data: await toImageBitmap({ width: size, height: size, data: new Uint8ClampedArray(size * size * 4) }) };
        const tile = await paintTile(spec.client, spec.layer, {
            signal: abortController.signal,
            z, x, y, size,
            ...(spec.taxon !== undefined && { taxon: spec.taxon }),
            ...(spec.scale !== undefined && { scale: spec.scale }),
            ...(spec.blend !== undefined && { blend: spec.blend }),
            ...(spec.hideZeros !== undefined && { hideZeros: spec.hideZeros }),
        });
        const bitmap = await toImageBitmap(tile);
        if (abortController.signal.aborted) {
            bitmap.close();
            abortController.signal.throwIfAborted();
        }
        return { data: bitmap };
    };
    /** Register a spec and return the id that names it in tile URLs. */
    register(spec) {
        if (!spec.scale && !spec.blend)
            throw new Error("a tile spec needs a scale or a blend");
        const id = String(this.next++);
        this.specs.set(id, spec);
        return id;
    }
    /** Forget a registered spec. */
    release(id) {
        this.specs.delete(id);
    }
    /** The tile URL template for a registered spec. */
    template(id) {
        return `${this.name}://${id}/{z}/{x}/{y}`;
    }
    /** A MapLibre raster source for a spec, registering it first. */
    source(spec, opts = {}) {
        const id = this.register(spec);
        return {
            id,
            source: {
                type: "raster", tiles: [this.template(id)], tileSize: spec.tileSize ?? 256,
                minzoom: opts.minzoom ?? 0, maxzoom: opts.maxzoom ?? 11,
                ...(opts.attribution !== undefined && { attribution: opts.attribution }),
            },
        };
    }
}
/**
 * One LIFE raster layer on a MapLibre map.
 *
 * Construct it once the map's style has loaded. `update(spec)` swaps in a
 * new spec, which repaints every tile; `setOpacity` changes the paint
 * property in place; `remove` takes the layer and source off the map.
 */
export class LifeMapLayer {
    map;
    protocol;
    opts;
    id;
    specId = null;
    opacity;
    constructor(map, protocol, spec, opts = {}) {
        this.map = map;
        this.protocol = protocol;
        this.opts = opts;
        this.id = opts.id ?? "life";
        this.opacity = opts.opacity ?? 0.85;
        this.update(spec);
    }
    /** Replace what is drawn. */
    update(spec) {
        const { id, source } = this.protocol.source(spec, {
            ...(this.opts.minzoom !== undefined && { minzoom: this.opts.minzoom }),
            ...(this.opts.maxzoom !== undefined && { maxzoom: this.opts.maxzoom }),
            ...(this.opts.attribution !== undefined && { attribution: this.opts.attribution }),
        });
        this.detach();
        if (this.specId)
            this.protocol.release(this.specId);
        this.specId = id;
        this.map.addSource(this.id, source);
        this.map.addLayer({ id: this.id, type: "raster", source: this.id,
            paint: { "raster-opacity": this.opacity, "raster-resampling": "nearest", "raster-fade-duration": 0 } }, this.before());
    }
    /** Change the opacity of the data over the basemap. */
    setOpacity(opacity) {
        this.opacity = opacity;
        if (this.map.getLayer(this.id))
            this.map.setPaintProperty(this.id, "raster-opacity", opacity);
    }
    /** Take the layer off the map. */
    remove() {
        this.detach();
        if (this.specId)
            this.protocol.release(this.specId);
        this.specId = null;
    }
    detach() {
        if (this.map.getLayer(this.id))
            this.map.removeLayer(this.id);
        if (this.map.getSource(this.id))
            this.map.removeSource(this.id);
    }
    before() {
        if (this.opts.before === "labels")
            return this.map.getStyle()?.layers?.find((l) => l.type === "symbol")?.id;
        return this.opts.before;
    }
}
/** A MapLibre style showing OpenStreetMap's standard raster tiles. Light use only; see the OSM tile usage policy. */
export const OSM_STYLE = {
    version: 8,
    sources: {
        osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            maxzoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        },
    },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
};
//# sourceMappingURL=maplibre.js.map