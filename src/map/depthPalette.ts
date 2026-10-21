import type { FrameIndex } from '../data/schemas';

/**
 * B4 depth ramp: shallow cyan -> teal -> indigo -> blue. The committed PNG
 * bakes four blues into its pixels, so the controller recolours each decoded
 * frame at runtime. This is a presentation transform: class ids, extents and
 * depths are untouched, and public/data is never rewritten.
 *
 * B8: the deepest band moved from violet to blue. Violet sat in the same
 * magenta family as the very_high risk class (#d95f9b), so one hue carried two
 * meanings; blue is reserved for scenario depth only.
 */
export const DEPTH_PRESENTATION: Record<number, { color: string; name: string }> = {
  1: { color: '#49d6e8', name: 'Cyan' },
  2: { color: '#23b39f', name: 'Teal' },
  3: { color: '#5c63d8', name: 'Indigo' },
  4: { color: '#2f63e6', name: 'Blue' },
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
 * Return a data URL with each committed class colour swapped for its B4 ramp
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
