import type { FrameIndex } from '../data/schemas';

/**
 * Shared, ordered depth presentation: pale cyan to deep indigo.
 * The committed PNG encodes the frame-index source colours, not this ramp.
 * Recolour decoded pixels at runtime; never change class ids, bounds, alpha,
 * depths or public/data. Map paint must not add saturation/contrast to this ramp.
 */
export const DEPTH_PRESENTATION: Readonly<Record<number, { readonly color: string; readonly name: string }>> = {
  1: { color: '#d6f2fb', name: 'Pale cyan' },
  2: { color: '#8fcce3', name: 'Cyan' },
  3: { color: '#5288bd', name: 'Blue' },
  4: { color: '#343d7e', name: 'Deep indigo' },
};

export function depthPresentationColor(classId: number, fallback: string): string {
  return DEPTH_PRESENTATION[classId]?.color ?? fallback;
}

function rgbKey(red: number, green: number, blue: number): string {
  return `${red},${green},${blue}`;
}

function parseHex(hex: string): [number, number, number] | null {
  const value = hex.replace('#', '').trim();
  if (!/^[0-9a-f]{6}$/i.test(value)) return null;
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ];
}

/**
 * Return a data URL with each committed class colour swapped for its shared ramp
 * colour. Returns null when the frame has no mapped wet pixels, so callers can
 * safely fall back to the committed image URL.
 */
export function recolorFloodFrame(image: HTMLImageElement, frameIndex: FrameIndex): string | null {
  const width = image.naturalWidth;
  const height = image.naturalHeight;
  if (width <= 0 || height <= 0) return null;

  const targetBySource = new Map<string, [number, number, number]>();
  for (const frameClass of frameIndex.classes) {
    const target = DEPTH_PRESENTATION[frameClass.id]?.color;
    if (!target || frameClass.alpha === 0) continue;
    const source = parseHex(frameClass.color);
    const rgb = parseHex(target);
    if (!source || !rgb) continue;
    targetBySource.set(rgbKey(source[0], source[1], source[2]), rgb);
  }
  if (targetBySource.size === 0) return null;

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) return null;
  context.drawImage(image, 0, 0);

  const imageData = context.getImageData(0, 0, width, height);
  const pixels = imageData.data;
  let changed = false;
  for (let offset = 0; offset < pixels.length; offset += 4) {
    if (pixels[offset + 3] === 0) continue;
    const target = targetBySource.get(
      rgbKey(pixels[offset], pixels[offset + 1], pixels[offset + 2]),
    );
    if (!target) continue;
    pixels[offset] = target[0];
    pixels[offset + 1] = target[1];
    pixels[offset + 2] = target[2];
    changed = true;
  }
  if (!changed) return null;

  context.putImageData(imageData, 0, 0);
  return canvas.toDataURL('image/png');
}
