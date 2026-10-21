import type { FrameIndex } from '../data/schemas';
import { dataUrl } from '../data/loadData';
import {
  PEAK_EXTENT_ALPHA_FLOOR,
  PEAK_EXTENT_ROW_DENSITY_FLOOR,
  PEAK_EXTENT_SCAN_MAX_WIDTH,
  PEAK_EXTENT_TRIM,
} from './mapConfig';

export interface PeakWetExtent {
  /** WGS84 bounds of the dominant peak-wet core, west/south/east/north. */
  bounds: [number, number, number, number];
  /** Number of wet source pixels in the scan, before trimming. */
  wetPixels: number;
  /** Share of the dominant valley's wet pixels retained by the trim. */
  retainedShare: number;
  /** Which frame supplied the extent (normally the committed peak step). */
  step: number;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.decoding = 'async';
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Unable to decode peak frame ${url}`));
    image.src = url;
  });
}

function pixelToLngLat(
  x: number,
  y: number,
  scanWidth: number,
  scanHeight: number,
  bbox: [number, number, number, number],
): [number, number] {
  const [west, south, east, north] = bbox;
  return [
    west + (x / scanWidth) * (east - west),
    north - (y / scanHeight) * (north - south),
  ];
}

/** First integer coordinate whose cumulative count reaches `target`. */
function quantileCoordinate(counts: Uint32Array, target: number): number {
  let cumulative = 0;
  for (let index = 0; index < counts.length; index += 1) {
    cumulative += counts[index];
    if (cumulative >= target) return index;
  }
  return counts.length - 1;
}

/**
 * B4 camera source: scan the committed peak frame's alpha channel at runtime.
 *
 * The raw alpha bbox of step-07 is nearly the whole state: the Barak valley tail
 * and a handful of western fringe pixels are part of the same PNG. Fitting that
 * box would make the flood smaller, not larger. Instead we keep the dominant
 * contiguous valley band (the Brahmaputra flood body), then trim the outer
 * `PEAK_EXTENT_TRIM` of wet pixels on each axis. That is a robust extent, not a
 * different raster: every wet pixel still comes from the committed frame and no
 * flood value is regenerated.
 */
export async function scanPeakWetExtent(
  frameIndex: FrameIndex,
  peakStep: number,
): Promise<PeakWetExtent | null> {
  const frame = frameIndex.steps[peakStep] ?? frameIndex.steps[0];
  if (!frame) return null;

  const image = await loadImage(dataUrl(`flood/${frame.file}`));
  const sourceWidth = image.naturalWidth;
  const sourceHeight = image.naturalHeight;
  if (sourceWidth <= 0 || sourceHeight <= 0) return null;

  const scanWidth = Math.min(PEAK_EXTENT_SCAN_MAX_WIDTH, sourceWidth);
  const scanHeight = Math.max(1, Math.round((sourceHeight / sourceWidth) * scanWidth));

  const canvas = document.createElement('canvas');
  canvas.width = scanWidth;
  canvas.height = scanHeight;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) return null;
  context.drawImage(image, 0, 0, scanWidth, scanHeight);
  const pixels = context.getImageData(0, 0, scanWidth, scanHeight).data;

  const rowCounts = new Uint32Array(scanHeight);
  const columnCounts = new Uint32Array(scanWidth);
  let wetPixels = 0;
  let maxRowCount = 0;

  for (let y = 0; y < scanHeight; y += 1) {
    for (let x = 0; x < scanWidth; x += 1) {
      if (pixels[(y * scanWidth + x) * 4 + 3] < PEAK_EXTENT_ALPHA_FLOOR) continue;
      wetPixels += 1;
      rowCounts[y] += 1;
      columnCounts[x] += 1;
      if (rowCounts[y] > maxRowCount) maxRowCount = rowCounts[y];
    }
  }
  if (wetPixels === 0 || maxRowCount === 0) return null;

  // The Brahmaputra body is the longest contiguous run of rows with meaningful
  // wet density. This deliberately excludes the separate Barak-valley tail,
  // which would otherwise stretch the camera south and shrink the subject.
  const rowFloor = maxRowCount * PEAK_EXTENT_ROW_DENSITY_FLOOR;
  let bandStart = -1;
  let bestStart = -1;
  let bestEnd = -1;
  for (let y = 0; y <= scanHeight; y += 1) {
    const dense = y < scanHeight && rowCounts[y] >= rowFloor;
    if (dense && bandStart < 0) bandStart = y;
    if (!dense && bandStart >= 0) {
      if (bestStart < 0 || y - bandStart > bestEnd - bestStart) {
        bestStart = bandStart;
        bestEnd = y;
      }
      bandStart = -1;
    }
  }
  if (bestStart < 0) return null;

  let bandWetPixels = 0;
  const bandColumnCounts = new Uint32Array(scanWidth);
  for (let y = bestStart; y < bestEnd; y += 1) {
    const count = rowCounts[y];
    if (count === 0) continue;
    bandWetPixels += count;
    const rowOffset = y * scanWidth;
    for (let x = 0; x < scanWidth; x += 1) {
      if (pixels[(rowOffset + x) * 4 + 3] >= PEAK_EXTENT_ALPHA_FLOOR) bandColumnCounts[x] += 1;
    }
  }
  if (bandWetPixels === 0) return null;

  const trimCount = Math.floor(bandWetPixels * PEAK_EXTENT_TRIM);
  const lowTarget = Math.max(1, trimCount);
  const highTarget = Math.max(1, bandWetPixels - trimCount);
  const x0 = quantileCoordinate(bandColumnCounts, lowTarget);
  const x1 = quantileCoordinate(bandColumnCounts, highTarget);
  const y0 = quantileCoordinate(rowCounts.subarray(bestStart, bestEnd), lowTarget) + bestStart;
  const y1 =
    quantileCoordinate(rowCounts.subarray(bestStart, bestEnd), highTarget) + bestStart;

  let retained = 0;
  for (let y = y0; y <= y1; y += 1) {
    for (let x = x0; x <= x1; x += 1) {
      if (pixels[(y * scanWidth + x) * 4 + 3] >= PEAK_EXTENT_ALPHA_FLOOR) retained += 1;
    }
  }
  if (retained === 0) return null;

  const [west, south] = pixelToLngLat(x0, y1 + 1, scanWidth, scanHeight, frameIndex.bbox);
  const [east, north] = pixelToLngLat(x1 + 1, y0, scanWidth, scanHeight, frameIndex.bbox);
  const bounds: [number, number, number, number] = [
    Math.max(frameIndex.bbox[0], west),
    Math.max(frameIndex.bbox[1], south),
    Math.min(frameIndex.bbox[2], east),
    Math.min(frameIndex.bbox[3], north),
  ];
  if (bounds[0] >= bounds[2] || bounds[1] >= bounds[3]) return null;

  return {
    bounds,
    wetPixels,
    retainedShare: retained / bandWetPixels,
    step: peakStep,
  };
}
