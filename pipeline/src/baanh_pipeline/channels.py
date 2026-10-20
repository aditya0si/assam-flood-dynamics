"""Channel rasterisation shared by stage 06 (gate) and stage 07 (burn)."""
from __future__ import annotations

import numpy as np
from rasterio.features import rasterize
from scipy.ndimage import binary_dilation


def rasterize_channels(
    all_geoms,
    main_geoms,
    transform,
    height: int,
    width: int,
    main_width_cells: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(channel_mask, main_mask)`` as uint8, all_touched.

    The main stem is dilated by ``main_width_cells - 1`` cells; every other
    channel stays one cell wide (REVIEW-02 A2.4).
    """
    all_geoms = list(all_geoms)
    main_geoms = list(main_geoms)
    if not all_geoms:
        raise RuntimeError("channel rasterisation: no channel geometries")
    channel = rasterize(
        [(geom, 1) for geom in all_geoms],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    )
    if main_geoms:
        main = rasterize(
            [(geom, 1) for geom in main_geoms],
            out_shape=(height, width),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype="uint8",
        )
    else:
        main = np.zeros((height, width), dtype=np.uint8)
    widen = int(main_width_cells) - 1
    if widen > 0 and main.any():
        main = binary_dilation(main, iterations=widen).astype(np.uint8)
    channel = np.maximum(channel, main)
    return channel, main
