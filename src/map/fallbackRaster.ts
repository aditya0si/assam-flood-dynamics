import type { ImageSourceSpecification } from 'maplibre-gl';
import { dataUrl } from '../data/loadData';
import { FALLBACK_SOURCE_ID, bboxCoordinates } from './mapConfig';

/**
 * The committed hillshade is not georeferenced in the file. It is positioned with
 * the AOI corners from manifest.json, as DATA-PIPELINE.md §6.17 requires.
 */
export function fallbackHillshadeSource(bbox: [number, number, number, number]): ImageSourceSpecification {
  return {
    type: 'image',
    url: dataUrl('basemap/assam-hillshade.webp'),
    coordinates: bboxCoordinates(bbox),
  };
}

export { FALLBACK_SOURCE_ID };
