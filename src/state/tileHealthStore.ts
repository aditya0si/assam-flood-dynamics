import { create } from 'zustand';
import {
  deriveOverallHealth,
  INITIAL_TILE_HEALTH,
  type TileHealthLevel,
  type TileHealthSnapshot,
} from '../map/tileHealthState';

interface TileHealthState {
  snapshot: TileHealthSnapshot;
  level: TileHealthLevel;
  setSnapshot: (snapshot: TileHealthSnapshot) => void;
  reset: () => void;
}

/**
 * One runtime tile-health record for the whole app. The tracker writes it; the
 * map chip, the status bar and the probe hook read it. No component keeps a
 * second copy.
 */
export const useTileHealthStore = create<TileHealthState>((set) => ({
  snapshot: INITIAL_TILE_HEALTH,
  level: deriveOverallHealth(INITIAL_TILE_HEALTH),
  setSnapshot: (snapshot) => set({ snapshot, level: deriveOverallHealth(snapshot) }),
  reset: () =>
    set({ snapshot: INITIAL_TILE_HEALTH, level: deriveOverallHealth(INITIAL_TILE_HEALTH) }),
}));
