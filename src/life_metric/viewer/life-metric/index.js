/**
 * Read the LIFE maps of extinction risk from land-cover change.
 *
 * LIFE gives, for every 1 arc-minute pixel of land on Earth, the change in
 * the expected number of species extinctions over the next century if one
 * square kilometre of that pixel were converted to cropland, or restored to
 * natural vegetation. Open the published store with {@link LifeStore.open},
 * or a release through a {@link Catalogue}, then read a layer by region or by
 * point. The colour functions turn rasters into RGBA with the same scales and
 * taxa blend the reference viewer uses, and {@link paintTile} produces XYZ
 * map tiles.
 */
export { bbox, Grid } from "./grid.js";
export { Catalogue, compareVersions, MANIFEST } from "./catalogue.js";
export { CURVES, DEFAULT_CATALOGUE, DEFAULT_STORE, Layer, LifeStore, SCENARIOS, TAXA, parseLayout, } from "./store.js";
export { INKS, PALETTES, hexToOklab, linearToSrgb8, makeBlend, makeScale, normaliseInks, oklabToRgb8, percentileAbs, rampLut, } from "./colour.js";
export { paintTile, pickLevel, tileLats, tileLons } from "./tiles.js";
export { LifeMapLayer, LifeProtocol, OSM_STYLE, parseTileUrl as parseLifeTileUrl, toImageBitmap, } from "./maplibre.js";
//# sourceMappingURL=index.js.map