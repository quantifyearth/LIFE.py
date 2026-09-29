/** Catalogues: `versions.json` manifests that list released stores. */
import { DEFAULT_CATALOGUE, LifeStore } from "./store.js";
export const MANIFEST = "versions.json";
/** Compare numeric parts of release names numerically, including beta numbers. */
export function compareVersions(a, b) {
    const pa = a.match(/[0-9]+|[^0-9]+/g) ?? [], pb = b.match(/[0-9]+|[^0-9]+/g) ?? [];
    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
        if (i >= pa.length)
            return -1;
        if (i >= pb.length)
            return 1;
        const x = pa[i], y = pb[i];
        const c = /^[0-9]+$/.test(x) && /^[0-9]+$/.test(y) ? Number(x) - Number(y) : x.localeCompare(y);
        if (c !== 0)
            return c;
    }
    return 0;
}
function join(base, path) {
    return new URL(path, base.endsWith("/") ? base : base + "/").href;
}
/**
 * A set of released stores described by a `versions.json` manifest.
 *
 * The manifest lives directly under `base`, a URL, and maps version strings
 * to relative store paths. With no argument the published catalogue on
 * source.coop is used. It is fetched once, when first needed.
 */
export class Catalogue {
    base;
    manifest = null;
    fetchJson;
    opener;
    constructor(base = DEFAULT_CATALOGUE, opts = {}) {
        this.base = base;
        this.fetchJson = opts.fetchJson ?? (async (url) => { const r = await fetch(url); if (!r.ok)
            throw new Error(`${url}: ${r.status}`); return r.json(); });
        this.opener = opts.open ?? ((url) => LifeStore.open(url));
    }
    load() {
        if (!this.manifest) {
            this.manifest = this.fetchJson(join(this.base, MANIFEST)).then((m) => {
                if (!m || typeof m !== "object" || !("versions" in m))
                    throw new Error(`${this.base}/${MANIFEST} is not a catalogue manifest`);
                return m;
            });
        }
        return this.manifest;
    }
    /** Every release in version order. */
    async releases() {
        const m = await this.load();
        return Object.entries(m.versions)
            .map(([version, info]) => {
            const r = { version, path: info.path, url: join(this.base, info.path),
                ...(info.released !== undefined && { released: info.released }),
                ...(info.doi !== undefined && { doi: info.doi }),
                ...(info.description !== undefined && { description: info.description }) };
            return r;
        })
            .sort((a, b) => compareVersions(a.version, b.version));
    }
    /** The release called `version`; throws if absent. */
    async release(version) {
        const all = await this.releases();
        const r = all.find((x) => x.version === version);
        if (!r)
            throw new Error(`version ${version} is not in ${this.base}; have ${all.map((x) => x.version).join(", ")}`);
        return r;
    }
    /** The release the manifest marks as latest, else the highest version. */
    async latest() {
        const m = await this.load();
        if (m.latest !== undefined)
            return this.release(m.latest);
        const all = await this.releases();
        return all[all.length - 1];
    }
    /** Open the store for `version`, or the latest release when omitted. */
    async open(version) {
        const r = version === undefined ? await this.latest() : await this.release(version);
        return this.opener(r.url);
    }
}
//# sourceMappingURL=catalogue.js.map