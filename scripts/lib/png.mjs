import { inflateSync } from 'node:zlib';

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

const CHANNELS = {
  0: 1, // greyscale
  2: 3, // rgb
  3: 1, // palette index
  4: 2, // greyscale + alpha
  6: 4, // rgba
};

function paeth(left, up, upLeft) {
  const p = left + up - upLeft;
  const pa = Math.abs(p - left);
  const pb = Math.abs(p - up);
  const pc = Math.abs(p - upLeft);
  if (pa <= pb && pa <= pc) return left;
  if (pb <= pc) return up;
  return upLeft;
}

function bitsPerPixel(bitDepth, colorType) {
  return CHANNELS[colorType] * bitDepth;
}

function readSample(row, bitOffset, bitDepth) {
  if (bitDepth === 8) return row[bitOffset >> 3];
  if (bitDepth === 16) return row[bitOffset >> 3] * 256 + row[(bitOffset >> 3) + 1];
  const byte = row[bitOffset >> 3];
  const shift = 8 - bitDepth - (bitOffset & 7);
  return (byte >> shift) & ((1 << bitDepth) - 1);
}

/**
 * Minimal PNG decoder for the committed rasters and Playwright screenshots.
 * Supports non-interlaced 8-bit greyscale/RGB/RGBA and 4/8-bit palette images.
 * Returns RGBA pixels so callers can count transparent vs wet pixels without
 * pulling in an image dependency.
 */
export function decodePng(buffer) {
  if (!Buffer.isBuffer(buffer)) buffer = Buffer.from(buffer);
  if (buffer.length < 8 || !buffer.subarray(0, 8).equals(PNG_SIGNATURE)) {
    throw new Error('not a PNG file');
  }

  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  let interlace = 0;
  let palette = null;
  let transparency = null;
  const idat = [];

  while (offset + 12 <= buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString('latin1', offset + 4, offset + 8);
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (data.length !== length) throw new Error(`truncated PNG chunk ${type}`);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
      const compression = data[10];
      const filter = data[11];
      interlace = data[12];
      if (compression !== 0) throw new Error('unsupported PNG compression method');
      if (filter !== 0) throw new Error('unsupported PNG filter method');
      if (interlace !== 0) throw new Error('interlaced PNG is not supported');
    } else if (type === 'PLTE') {
      palette = Buffer.from(data);
    } else if (type === 'tRNS') {
      transparency = Buffer.from(data);
    } else if (type === 'IDAT') {
      idat.push(data);
    } else if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }

  if (!width || !height) throw new Error('PNG has no IHDR');
  if (colorType === 3 && !palette) throw new Error('palette PNG has no PLTE');
  if (idat.length === 0) throw new Error('PNG has no IDAT');

  const raw = inflateSync(Buffer.concat(idat));
  const bpp = Math.max(1, Math.ceil(bitsPerPixel(bitDepth, colorType) / 8));
  const rowBytes = Math.ceil((width * bitsPerPixel(bitDepth, colorType)) / 8);
  const expected = height * (rowBytes + 1);
  if (raw.length < expected) {
    throw new Error(`truncated PNG pixel data: ${raw.length} < ${expected}`);
  }

  const rows = Buffer.alloc(height * rowBytes);
  let rawOffset = 0;
  for (let y = 0; y < height; y += 1) {
    const filter = raw[rawOffset];
    rawOffset += 1;
    const rowStart = y * rowBytes;
    const prevStart = (y - 1) * rowBytes;
    for (let x = 0; x < rowBytes; x += 1) {
      const value = raw[rawOffset + x];
      const left = x >= bpp ? rows[rowStart + x - bpp] : 0;
      const up = y > 0 ? rows[prevStart + x] : 0;
      const upLeft = y > 0 && x >= bpp ? rows[prevStart + x - bpp] : 0;
      let reconstructed;
      switch (filter) {
        case 0:
          reconstructed = value;
          break;
        case 1:
          reconstructed = value + left;
          break;
        case 2:
          reconstructed = value + up;
          break;
        case 3:
          reconstructed = value + Math.floor((left + up) / 2);
          break;
        case 4:
          reconstructed = value + paeth(left, up, upLeft);
          break;
        default:
          throw new Error(`unsupported PNG filter ${filter} on row ${y}`);
      }
      rows[rowStart + x] = reconstructed & 0xff;
    }
    rawOffset += rowBytes;
  }

  const rgba = new Uint8Array(width * height * 4);
  const channels = CHANNELS[colorType];
  const maxSample = (1 << bitDepth) - 1;
  for (let y = 0; y < height; y += 1) {
    const rowStart = y * rowBytes;
    const row = rows.subarray(rowStart, rowStart + rowBytes);
    for (let x = 0; x < width; x += 1) {
      const out = (y * width + x) * 4;
      if (colorType === 3) {
        const index = readSample(row, x * bitDepth, bitDepth);
        const p = index * 3;
        rgba[out] = palette[p] ?? 0;
        rgba[out + 1] = palette[p + 1] ?? 0;
        rgba[out + 2] = palette[p + 2] ?? 0;
        rgba[out + 3] = transparency && index < transparency.length ? transparency[index] : 255;
      } else if (colorType === 6) {
        const p = rowStart + x * 4;
        rgba[out] = rows[p];
        rgba[out + 1] = rows[p + 1];
        rgba[out + 2] = rows[p + 2];
        rgba[out + 3] = rows[p + 3];
      } else if (colorType === 2) {
        const p = rowStart + x * 3;
        rgba[out] = rows[p];
        rgba[out + 1] = rows[p + 1];
        rgba[out + 2] = rows[p + 2];
        rgba[out + 3] = 255;
      } else if (colorType === 0) {
        const value = readSample(row, x * bitDepth, bitDepth);
        const scaled = bitDepth === 8 ? value : Math.round((value / maxSample) * 255);
        rgba[out] = scaled;
        rgba[out + 1] = scaled;
        rgba[out + 2] = scaled;
        rgba[out + 3] = 255;
      } else if (colorType === 4) {
        const p = rowStart + x * 2;
        rgba[out] = rows[p];
        rgba[out + 1] = rows[p];
        rgba[out + 2] = rows[p];
        rgba[out + 3] = rows[p + 1];
      } else {
        throw new Error(`unsupported PNG colour type ${colorType}`);
      }
    }
  }

  return { width, height, bitDepth, colorType, channels, rgba };
}

export function countOpaquePixels(decoded) {
  const { rgba } = decoded;
  let count = 0;
  for (let i = 3; i < rgba.length; i += 4) {
    if (rgba[i] > 0) count += 1;
  }
  return count;
}

/**
 * Count pixels whose RGB channels differ by more than `threshold` between two
 * same-size images. Alpha is ignored so opaque screenshots compare cleanly.
 */
export function countDifferentPixels(left, right, threshold = 8) {
  if (left.width !== right.width || left.height !== right.height) {
    throw new Error(
      `image size mismatch: ${left.width}x${left.height} vs ${right.width}x${right.height}`,
    );
  }
  let different = 0;
  for (let i = 0; i < left.rgba.length; i += 4) {
    const dr = Math.abs(left.rgba[i] - right.rgba[i]);
    const dg = Math.abs(left.rgba[i + 1] - right.rgba[i + 1]);
    const db = Math.abs(left.rgba[i + 2] - right.rgba[i + 2]);
    if (dr > threshold || dg > threshold || db > threshold) different += 1;
  }
  return different;
}
