import assert from 'node:assert/strict';
import test from 'node:test';
import { DEPTH_PRESENTATION, depthPresentationColor, recolorFloodFrame } from './depthPalette.ts';
import type { FrameIndex } from '../data/schemas.ts';

test('depth recolouring preserves classes, dry pixels and alpha', () => {
  const classes = [
    { id: 0, color: '#000000', alpha: 0 },
    { id: 1, color: '#9ecae1', alpha: 235 },
    { id: 2, color: '#4292c6', alpha: 235 },
    { id: 3, color: '#08519c', alpha: 240 },
    { id: 4, color: '#03135e', alpha: 245 },
  ];
  // The actual committed wet PNG pixels are opaque, despite index alpha metadata.
  const pixels = new Uint8ClampedArray([
    0, 0, 0, 0, 158, 202, 225, 255, 66, 146, 198, 255,
    8, 81, 156, 255, 3, 19, 94, 255, 22, 33, 44, 255,
  ]);
  const original = pixels.slice();
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'document');
  let written = false;
  const canvas = {
    width: 0, height: 0,
    getContext: () => ({
      drawImage: () => {},
      getImageData: () => ({ data: pixels }),
      putImageData: () => { written = true; },
    }),
    toDataURL: () => 'data:image/png;verified',
  };
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { createElement: () => canvas } });
  try {
    const index = { classes } as FrameIndex;
    const image = { naturalWidth: 6, naturalHeight: 1 } as HTMLImageElement;
    assert.equal(recolorFloodFrame(image, index), 'data:image/png;verified');
    assert.equal(written, true);
    assert.deepEqual(pixels.slice(0, 4), original.slice(0, 4));
    assert.deepEqual(pixels.slice(20), original.slice(20));
    for (let id = 1; id <= 4; id++) {
      const hex = DEPTH_PRESENTATION[id].color.slice(1);
      const expected = [0, 2, 4].map(offset => Number.parseInt(hex.slice(offset, offset + 2), 16));
      assert.deepEqual(Array.from(pixels.slice(id * 4, id * 4 + 3)), expected);
      assert.equal(pixels[id * 4 + 3], original[id * 4 + 3]);
      assert.equal(depthPresentationColor(id, '#ffffff'), `#${hex}`);
    }
    assert.equal(depthPresentationColor(99, '#123456'), '#123456');
    assert.equal(recolorFloodFrame({ naturalWidth: 0, naturalHeight: 0 } as HTMLImageElement, index), null);
  } finally {
    if (descriptor) Object.defineProperty(globalThis, 'document', descriptor);
    else Reflect.deleteProperty(globalThis, 'document');
  }
});
