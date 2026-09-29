/** Read LIFE data into typed arrays and GeoJSON masks, or draw it on a canvas or MapLibre map. */
export { open, versions } from "./client.js";
export { DEFAULT_CATALOGUE, DEFAULT_STORE } from "./store.js";
export { INKS, PALETTES, hexToOklab, linearToSrgb8, makeBlend, makeScale, normaliseInks, oklabToRgb8, percentileAbs, rampLut, } from "./colour.js";
export { paintTile, pickLevel, tileLats, tileLons } from "./tiles.js";
export { LifeMapLayer, LifeProtocol, OSM_STYLE, parseTileUrl as parseLifeTileUrl, toImageBitmap, } from "./maplibre.js";
//# sourceMappingURL=index.js.map